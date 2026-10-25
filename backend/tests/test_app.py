import os
from datetime import date, datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from app.db import Base, get_db
from app.models import Movie, Snapshot, Genre
from app.main import app
from app.ingest import transform, upsert, TMDB

@pytest.fixture
def db():
    engine = create_engine('sqlite://', connect_args={'check_same_thread':False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()

@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()

def seed(db):
    today = date(2026, 1, 3)
    db.add(Genre(id=1, name='Drama'))
    for i, title in enumerate(['Alpha', 'Beta', 'New', 'Missing'], 1):
        m = Movie(id=i, title=title, release_date=date(2025,1,1))
        db.add(m)
        db.flush()
        if i == 1:
            m.genres = [db.get(Genre,1)]
        for day, p in [(today-timedelta(days=2),10),(today,20 if i < 3 else None)]:
            if i == 3 and day != today:
                continue
            db.add(Snapshot(movie_id=i,day=day,collected_at=datetime.now(timezone.utc),popularity=p,rating=8 if i==1 else None,vote_count=100 if i==1 else None))
    db.commit()

def test_transform_preserves_missing():
    m,s=transform({'id':1,'title':'Film','release_date':''},{'secure_base_url':'https://image.tmdb.org/t/p/','poster_sizes':['w500']})
    assert m['release_date'] is None and m['poster_url'] is None
    assert s == {'popularity':None,'rating':None,'vote_count':None}

@pytest.mark.parametrize('value',[-1,float('nan'),float('inf'),'5',True])
def test_invalid_metric(value):
    with pytest.raises(ValueError):
        transform({'id':1,'title':'Film','popularity':value},{'secure_base_url':'x','poster_sizes':['w500']})

def test_empty_and_validation(client):
    assert client.get('/summary').json()['movies']==0
    assert client.get('/rising').json()['items']==[]
    for query in ['page=0','page_size=100','sort=unsafe','year=1','min_votes=-1']:
        assert client.get('/movies?'+query).status_code==422
    assert client.get('/movies/42').status_code==404
    assert client.get('/movies/42/history').status_code==404
    assert client.post('/ingest').status_code==404

def test_filter_sort_pagination_and_summary(client,db):
    seed(db)
    assert client.get('/movies?q=alp').json()['total']==1
    assert client.get('/movies?genre=1').json()['total']==1
    assert client.get('/movies?year=2024').json()['total']==0
    assert client.get('/movies?min_votes=50').json()['total']==1
    data=client.get('/movies?sort=rating&page_size=1&page=2').json()
    assert data['total']==4 and data['items'][0]['id']==2
    assert client.get('/movies?q=%25').json()['total']==0
    stats=client.get('/summary').json()
    assert stats['movies']==4 and stats['average_rating']==8 and stats['total_votes']==100
    assert len(client.get('/movies/1/history').json())==2

def test_trends_only_shared_movies(client,db):
    seed(db)
    data=client.get('/rising').json()
    assert data['from_day']=='2026-01-01' and data['to_day']=='2026-01-03'
    assert [m['id'] for m in data['items']]==[1,2]
    assert data['items'][0]['change']==10 and data['items'][0]['percent_change']==100

def test_single_day_not_rising(client,db):
    db.add(Movie(id=1,title='New'))
    db.flush()
    db.add(Snapshot(movie_id=1,day=date.today(),collected_at=datetime.now(timezone.utc),popularity=10))
    db.commit()
    assert client.get('/rising').json()['items']==[]

@pytest.mark.skipif(not os.getenv('TEST_DATABASE_URL'), reason='Requires separate PostgreSQL test database')
def test_postgres_daily_upsert():
    engine=create_engine(os.environ['TEST_DATABASE_URL'])
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        try:
            upsert(db,Movie,dict(id=99999999,title='TEST ONLY'),['id'])
            for score in [10,20]:
                upsert(db,Snapshot,dict(movie_id=99999999,day=date(2000,1,1),collected_at=datetime.now(timezone.utc),popularity=score,rating=None,vote_count=None),['movie_id','day'])
            assert db.scalar(select(func.count()).select_from(Snapshot).where(Snapshot.movie_id==99999999))==1
            assert db.scalar(select(Snapshot.popularity).where(Snapshot.movie_id==99999999))==20
        finally:
            db.rollback()
    engine.dispose()

def test_retry_and_raw_archive(tmp_path,monkeypatch):
    import httpx
    sleeps=[]
    monkeypatch.setattr('app.ingest.time.sleep',sleeps.append)
    calls=[]
    def handler(req):
        calls.append(req)
        return httpx.Response(429,headers={'Retry-After':'1'}) if len(calls)==1 else httpx.Response(200,json={'results':[]})
    tmdb=TMDB('test-token',tmp_path)
    tmdb.client.close()
    tmdb.client=httpx.Client(base_url='https://api.themoviedb.org/3/',transport=httpx.MockTransport(handler))
    assert tmdb.get('movie/popular',page=1)=={'results':[]}
    assert sleeps==[1] and len(list(tmp_path.glob('*.json')))==1
    tmdb.client.close()

@pytest.mark.skipif(not os.getenv('TEST_DATABASE_URL'), reason='Requires separate PostgreSQL test database')
def test_ingestion_rerun_and_rollback(tmp_path,monkeypatch):
    from sqlalchemy.orm import sessionmaker
    from types import SimpleNamespace
    from app import ingest as module
    from app.models import PipelineRun
    engine=create_engine(os.environ['TEST_DATABASE_URL'])
    factory=sessionmaker(engine)
    config=SimpleNamespace(tmdb_token='test-only',raw_data_dir=str(tmp_path))
    monkeypatch.setattr(module,'settings',lambda:config)
    monkeypatch.setattr(module,'Session',factory)
    bad=[False]
    class FakeTMDB:
        def __init__(self,*args):
            self.client=SimpleNamespace(close=lambda:None)
        def get(self,path,**kwargs):
            if path=='configuration':
                return {'images':{'secure_base_url':'https://image.tmdb.org/t/p/','poster_sizes':['w500']}}
            if path=='genre/movie/list':
                return {'genres':[]}
            if path=='movie/popular':
                return {'results':[{'id':99999998}],'total_pages':1}
            return {'id':99999998,'title':'TEST PIPELINE ONLY','popularity':-1 if bad[0] else 25,'genres':[]}
    monkeypatch.setattr(module,'TMDB',FakeTMDB)
    try:
        module.ingest(1)
        module.ingest(1)
        with factory() as db:
            assert db.scalar(select(func.count()).select_from(Snapshot).where(Snapshot.movie_id==99999998))==1
        bad[0]=True
        with pytest.raises(RuntimeError):
            module.ingest(1)
        with factory() as db:
            assert db.scalar(select(Snapshot.popularity).where(Snapshot.movie_id==99999998))==25
            assert db.scalar(select(PipelineRun.status).order_by(PipelineRun.id.desc()).limit(1))=='failed'
    finally:
        with factory.begin() as db:
            db.execute(Snapshot.__table__.delete().where(Snapshot.movie_id==99999998))
            db.execute(Movie.__table__.delete().where(Movie.id==99999998))
        engine.dispose()
