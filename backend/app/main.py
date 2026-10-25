from datetime import date
from typing import Literal
from fastapi import FastAPI, Depends, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select, func, extract, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, aliased
from .config import settings
from .db import get_db
from .models import Movie, Snapshot, Genre, PipelineRun

app = FastAPI(title='CineMetrics API', version='1.0.0', description='Stored TMDB data. History begins on first collection. No ingestion endpoints.')
app.add_middleware(CORSMiddleware, allow_origins=[s.strip() for s in settings().cors_origins.split(',') if s.strip()], allow_methods=['GET'], allow_headers=['Accept'])

@app.exception_handler(SQLAlchemyError)
async def database_error(request, exc):
    return JSONResponse(status_code=503, content={'detail': 'Database unavailable or migrations pending. See README setup.'})

def latest():
    return select(Snapshot.movie_id, func.max(Snapshot.day).label('day')).group_by(Snapshot.movie_id).subquery()

def movie_json(m, s):
    return dict(id=m.id, title=m.title, overview=m.overview, poster_url=m.poster_url, release_date=m.release_date, original_language=m.original_language, genres=[dict(id=g.id, name=g.name) for g in m.genres], popularity=s.popularity, rating=s.rating, vote_count=s.vote_count, snapshot_day=s.day)

def current_query():
    l = latest()
    return select(Movie, Snapshot).join(Snapshot, Movie.id == Snapshot.movie_id).join(l, (l.c.movie_id == Snapshot.movie_id) & (l.c.day == Snapshot.day))

@app.get('/health')
def health(db: Session = Depends(get_db)):
    db.execute(text('SELECT 1 FROM movie_snapshots LIMIT 1'))
    return {'status': 'ok'}

@app.get('/genres')
def genres(db: Session = Depends(get_db)):
    return [dict(id=g.id, name=g.name) for g in db.scalars(select(Genre).order_by(Genre.name))]

@app.get('/movies')
def movies(q: str = Query('', max_length=200), genre: int | None = Query(None, gt=0), year: int | None = Query(None, ge=1870, le=2200), min_votes: int = Query(0, ge=0), sort: Literal['popularity', 'rating', 'release_date'] = 'popularity', page: int = Query(1, ge=1, le=10000), page_size: int = Query(12, ge=1, le=60), db: Session = Depends(get_db)):
    query = current_query()
    if q.strip():
        query = query.where(Movie.title.ilike('%' + q.strip().replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%', escape='\\'))
    if genre:
        query = query.where(Movie.genres.any(Genre.id == genre))
    if year:
        query = query.where(extract('year', Movie.release_date) == year)
    if min_votes:
        query = query.where(Snapshot.vote_count >= min_votes)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    column = {'popularity': Snapshot.popularity, 'rating': Snapshot.rating, 'release_date': Movie.release_date}[sort]
    rows = db.execute(query.order_by(column.desc().nulls_last(), Movie.id).offset((page-1)*page_size).limit(page_size))
    return dict(items=[movie_json(m,s) for m,s in rows], total=total, page=page, page_size=page_size)

@app.get('/movies/{movie_id}')
def movie(movie_id: int, db: Session = Depends(get_db)):
    row = db.execute(current_query().where(Movie.id == movie_id)).first()
    if not row:
        raise HTTPException(404, 'Movie has not been collected.')
    return movie_json(*row)

@app.get('/movies/{movie_id}/history')
def history(movie_id: int, db: Session = Depends(get_db)):
    if not db.get(Movie, movie_id):
        raise HTTPException(404, 'Movie has not been collected.')
    return [dict(day=s.day, popularity=s.popularity, rating=s.rating, vote_count=s.vote_count) for s in db.scalars(select(Snapshot).where(Snapshot.movie_id == movie_id).order_by(Snapshot.day))]

@app.get('/summary')
def summary(db: Session = Depends(get_db)):
    rows = current_query().subquery()
    stats = db.execute(select(func.count(), func.avg(rows.c.rating), func.avg(rows.c.popularity), func.sum(rows.c.vote_count)).select_from(rows)).one()
    run = db.scalar(select(PipelineRun).where(PipelineRun.status == 'success').order_by(PipelineRun.finished_at.desc()).limit(1))
    return dict(movies=stats[0], average_rating=stats[1], average_popularity=stats[2], total_votes=stats[3], first_day=db.scalar(select(func.min(Snapshot.day))), latest_day=db.scalar(select(func.max(Snapshot.day))), last_refresh=run.finished_at if run else None)

@app.get('/rising')
def rising(limit: int = Query(20, ge=1, le=60), db: Session = Depends(get_db)):
    days = list(db.scalars(select(Snapshot.day).distinct().order_by(Snapshot.day.desc()).limit(2)))
    if len(days) < 2:
        return dict(from_day=None, to_day=days[0] if days else None, items=[])
    old = aliased(Snapshot)
    delta = Snapshot.popularity - old.popularity
    query = select(Movie, Snapshot, old.popularity, delta).join(Snapshot, Snapshot.movie_id == Movie.id).join(old, (old.movie_id == Movie.id) & (old.day == days[1])).where(Snapshot.day == days[0], delta > 0).order_by(delta.desc(), Movie.id).limit(limit)
    return dict(from_day=days[1], to_day=days[0], items=[dict(**movie_json(m,s), previous_popularity=p, change=d, percent_change=d/p*100 if p else None) for m,s,p,d in db.execute(query)])
