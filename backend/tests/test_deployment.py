"""Deployment behavior without network credentials or a cloud deployment."""
import gzip
import json
import time
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool, NullPool
from app.db import Base, database_url, create_db_engine, require_direct_connection, get_db
from app.main import app as api
from app.models import RawResponse, PipelineRun
from app.ingest import TMDB, archive_response
from index import app

@pytest.mark.parametrize('scheme', ['postgres', 'postgresql', 'postgresql+psycopg'])
def test_neon_url_preserves_ssl(scheme):
    value=database_url(f'{scheme}://user:placeholder@ep-test.neon.tech/db?sslmode=require&channel_binding=require')
    assert value.startswith('postgresql+psycopg://')
    assert value.endswith('?sslmode=require&channel_binding=require')

def test_runtime_connections_and_direct_guard():
    engine=create_db_engine('postgresql://user:placeholder@localhost/test')
    assert isinstance(engine.pool, NullPool)
    assert engine.hide_parameters
    engine.dispose()
    with pytest.raises(RuntimeError,match='DIRECT'):
        require_direct_connection('postgresql://user:placeholder@ep-test-pooler.us-east-1.aws.neon.tech/test')
    require_direct_connection('postgresql://user:placeholder@ep-test.us-east-1.aws.neon.tech/test')

def test_api_mount_preserves_query_and_docs():
    engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory=sessionmaker(engine)
    def db():
        with factory() as s:
            yield s
    api.dependency_overrides[get_db]=db
    try:
        with TestClient(app) as client:
            r=client.get('/api/movies?q=Iron+Man&page_size=2')
            assert r.status_code==200 and r.json()['page_size']==2
            assert client.get('/api/summary').json()['movies']==0
            assert client.get('/api/health').json()=={'status':'ok'}
            assert '/api/openapi.json' in client.get('/api/docs').text
            assert client.get('/api/openapi.json').status_code==200
            assert client.post('/api/ingest').status_code==404
            assert client.options('/api/movies', headers={
                'Origin':'https://untrusted.example',
                'Access-Control-Request-Method':'GET'}).status_code==400
    finally:
        api.dependency_overrides.clear()
        engine.dispose()

def test_database_raw_archive_survives_other_rollback(monkeypatch):
    engine=create_engine('sqlite://')
    Base.metadata.create_all(engine)
    factory=sessionmaker(engine)
    monkeypatch.setattr('app.ingest.Session',factory)
    with factory.begin() as db:
        run=PipelineRun(started_at=datetime.now(timezone.utc),status='running',movie_count=0)
        db.add(run); db.flush(); run_id=run.id
    archive_response(run_id,'movie/1_0',{'id':1,'title':'Test é'})
    with factory() as db:
        db.get(PipelineRun,run_id).status='success'
        db.rollback()
        row=db.scalar(select(RawResponse))
        assert json.loads(gzip.decompress(row.payload_gzip))=={'id':1,'title':'Test é'}
        assert db.get(PipelineRun,run_id).status=='running'
    engine.dispose()

def test_database_archive_does_not_write_local_files(tmp_path):
    import httpx
    archived=[]
    client=TMDB('test-only',None,archive=lambda path,data:archived.append((path,data)))
    client.client.close()
    client.client=httpx.Client(base_url='https://api.themoviedb.org/3/',transport=httpx.MockTransport(lambda req:httpx.Response(200,json={'id':1})))
    try:
        client.get('movie/1')
        assert archived==[('movie/1_0',{'id':1})]
        assert list(tmp_path.iterdir())==[]
    finally:
        client.client.close()

def test_deadline_fails_before_request_or_long_backoff():
    client=TMDB('test-only',None)
    try:
        client.deadline=time.monotonic()-1
        with pytest.raises(RuntimeError,match='time budget'):
            client.get('movie/1')
        client.deadline=time.monotonic()+1
        with pytest.raises(RuntimeError,match='time budget'):
            client.pause(60)
    finally:
        client.client.close()

@pytest.mark.skipif(not __import__('os').getenv('TEST_DATABASE_URL'), reason='Requires disposable PostgreSQL database')
def test_full_database_archive_pipeline(monkeypatch, tmp_path):
    import os
    import httpx
    from types import SimpleNamespace
    from app import ingest as module
    from app.models import Movie, Snapshot
    engine=create_engine(os.environ['TEST_DATABASE_URL'])
    factory=sessionmaker(engine)
    config=SimpleNamespace(database_url=os.environ['TEST_DATABASE_URL'], tmdb_token='test-only',
        raw_archive_mode='database', raw_data_dir=str(tmp_path/'must-not-exist'))
    monkeypatch.setattr(module,'settings',lambda:config)
    monkeypatch.setattr(module,'Session',factory)
    original=TMDB.__init__
    def init(self,*args,**kwargs):
        original(self,*args,**kwargs)
        self.client.close()
        def handler(req):
            path=req.url.path
            if path.endswith('/configuration'):
                data={'images':{'secure_base_url':'https://image.tmdb.org/t/p/','poster_sizes':['w500']}}
            elif path.endswith('/genre/movie/list'):
                data={'genres':[]}
            elif path.endswith('/movie/popular'):
                data={'results':[{'id':99999997}],'total_pages':1}
            else:
                data={'id':99999997,'title':'Archive integration test','genres':[],'popularity':25}
            return httpx.Response(200,json=data)
        self.client=httpx.Client(base_url='https://api.themoviedb.org/3/',transport=httpx.MockTransport(handler))
    monkeypatch.setattr(TMDB,'__init__',init)
    with factory() as db:
        before=list(db.scalars(select(PipelineRun.id)))
    try:
        module.ingest(1)
        with factory() as db:
            run=db.scalar(select(PipelineRun).where(PipelineRun.id.not_in(before)).order_by(PipelineRun.id.desc()))
            assert run.status=='success'
            raw=list(db.scalars(select(RawResponse).where(RawResponse.run_id==run.id)))
            assert len(raw)==4
            assert any(json.loads(gzip.decompress(r.payload_gzip)).get('id')==99999997 for r in raw)
            assert db.get(Movie,99999997)
            assert not (tmp_path/'must-not-exist').exists()
    finally:
        with factory.begin() as db:
            db.execute(RawResponse.__table__.delete().where(RawResponse.run_id.not_in(before)))
            db.execute(Snapshot.__table__.delete().where(Snapshot.movie_id==99999997))
            db.execute(Movie.__table__.delete().where(Movie.id==99999997))
        engine.dispose()
