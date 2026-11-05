"""Run with python -m app.ingest --pages 5. No public HTTP trigger."""
import argparse
import gzip
import json
import logging
import math
import time
from datetime import date, datetime, timezone
from pathlib import Path
from uuid import uuid4
import httpx
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert
from .config import settings
from .db import Session, require_direct_connection
from .models import Movie, Genre, MovieGenre, Snapshot, PipelineRun, RawResponse

log = logging.getLogger('cinemetrics')

def number(value, maximum=None, integer=False):
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or value < 0 or (maximum is not None and value > maximum) or (integer and int(value) != value):
        raise ValueError('Invalid numeric field')
    return int(value) if integer else float(value)

def transform(raw, images):
    if not isinstance(raw.get('id'), int) or raw['id'] <= 0 or not isinstance(raw.get('title'), str) or not raw['title'].strip():
        raise ValueError('Invalid movie identity')
    released = date.fromisoformat(raw['release_date']) if raw.get('release_date') else None
    poster = raw.get('poster_path')
    if poster and (not poster.startswith('/') or '..' in poster):
        raise ValueError('Invalid poster path')
    sizes = images['poster_sizes']
    size = 'w500' if 'w500' in sizes else sizes[-1]
    metadata = dict(id=raw['id'], title=raw['title'], overview=raw.get('overview'), release_date=released, original_language=raw.get('original_language'), poster_url=images['secure_base_url'] + size + poster if poster else None)
    metrics = dict(popularity=number(raw.get('popularity')), rating=number(raw.get('vote_average'), 10), vote_count=number(raw.get('vote_count'), integer=True))
    return metadata, metrics

class TMDB:
    def __init__(self, token, folder, archive=None):
        self.folder = folder
        self.archive = archive
        self.deadline = None
        self.client = httpx.Client(base_url='https://api.themoviedb.org/3/', headers={'Authorization': f'Bearer {token}'}, timeout=20)

    def remaining(self):
        if self.deadline is None:
            return 20
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise RuntimeError('Ingestion time budget exhausted')
        return remaining

    def pause(self, delay):
        if self.deadline is not None and delay >= self.remaining():
            raise RuntimeError('Ingestion time budget exhausted')
        time.sleep(delay)

    def get(self, path, **params):
        for attempt in range(5):
            try:
                response = self.client.get(path, params=params, timeout=min(20, self.remaining()))
                if response.status_code == 429 or response.status_code >= 500:
                    if attempt == 4:
                        raise RuntimeError(f'TMDB retry limit reached (HTTP {response.status_code})')
                    try:
                        delay = float(response.headers.get('Retry-After', 2**attempt))
                    except ValueError:
                        delay = 2**attempt
                    self.pause(min(max(delay, 1), 60))
                    continue
                if response.status_code != 200:
                    raise RuntimeError(f'TMDB request failed (HTTP {response.status_code})')
                data = response.json()
                resource = path + '_' + str(params.get('page', 0))
                if self.archive:
                    self.archive(resource, data)
                else:
                    target = self.folder / (resource.replace('/', '_') + '.json')
                    target.write_text(json.dumps(data, ensure_ascii=False))
                return data
            except httpx.TransportError:
                if attempt == 4:
                    raise RuntimeError('TMDB network request failed') from None
                self.pause(2**attempt)
        raise RuntimeError('TMDB unavailable')

def upsert(db, model, values, keys):
    stmt = insert(model).values(**values)
    db.execute(stmt.on_conflict_do_update(index_elements=keys, set_={k: getattr(stmt.excluded, k) for k in values if k not in keys}))

def archive_response(run_id, resource, data):
    # Commit each archive independently: failed transformations still have evidence.
    payload = gzip.compress(json.dumps(data, ensure_ascii=False).encode('utf-8'))
    with Session.begin() as db:
        db.add(RawResponse(run_id=run_id, resource=resource,
            collected_at=datetime.now(timezone.utc), payload_gzip=payload))

def ingest(pages, max_seconds=1200):
    config = settings()
    if not config.tmdb_token:
        raise RuntimeError('Set TMDB_TOKEN in backend/.env (API Read Access Token).')
    require_direct_connection(config.database_url)
    now = datetime.now(timezone.utc)
    with Session() as lock_db:
        # Session-level lock also covers network work and prevents out-of-order reruns.
        if not lock_db.scalar(text('SELECT pg_try_advisory_lock(7741201)')):
            raise RuntimeError('Another ingestion is running')
        try:
            with Session.begin() as db:
                run = PipelineRun(started_at=now, status='running', movie_count=0)
                db.add(run)
                db.flush()
                run_id = run.id
            client = None
            try:
                if getattr(config, 'raw_archive_mode', 'file') == 'database':
                    client = TMDB(config.tmdb_token, None,
                        archive=lambda resource, data: archive_response(run_id, resource, data))
                else:
                    folder = Path(config.raw_data_dir) / (now.strftime('%Y%m%dT%H%M%SZ') + '-' + uuid4().hex)
                    folder.mkdir(parents=True)
                    client = TMDB(config.tmdb_token, folder)
                client.deadline = time.monotonic() + max_seconds
                images = client.get('configuration')['images']
                genres = client.get('genre/movie/list', language='en-US')['genres']
                records = {}
                for page in range(1, pages+1):
                    result = client.get('movie/popular', language='en-US', page=page)
                    for movie in result['results']:
                        detail = client.get(f"movie/{movie['id']}", language='en-US')
                        if not detail.get('adult', False):
                            records[detail['id']] = detail
                    if page >= result['total_pages']:
                        break
                with Session.begin() as db:
                    for genre in genres:
                        upsert(db, Genre, dict(id=genre['id'], name=genre['name']), ['id'])
                    for raw in records.values():
                        metadata, metrics = transform(raw, images)
                        upsert(db, Movie, metadata, ['id'])
                        db.execute(MovieGenre.__table__.delete().where(MovieGenre.movie_id == metadata['id']))
                        for genre in raw.get('genres', []):
                            upsert(db, Genre, dict(id=genre['id'], name=genre['name']), ['id'])
                            db.add(MovieGenre(movie_id=metadata['id'], genre_id=genre['id']))
                        upsert(db, Snapshot, dict(movie_id=metadata['id'], day=now.date(), collected_at=now, **metrics), ['movie_id', 'day'])
                    run = db.get(PipelineRun, run_id)
                    run.status, run.finished_at, run.movie_count = 'success', datetime.now(timezone.utc), len(records)
                log.info('Collected %s movies; UTC snapshot %s', len(records), now.date())
            except Exception as exc:
                with Session.begin() as db:
                    run = db.get(PipelineRun, run_id)
                    run.status, run.finished_at = 'failed', datetime.now(timezone.utc)
                    # Never store response bodies, URLs, or exception strings containing secrets.
                    run.error = f'{type(exc).__name__}: ingestion failed; check credentials, connectivity, raw files and database.'
                raise RuntimeError('Ingestion failed; see pipeline_runs and raw files. No movie changes committed.') from None
            finally:
                if client:
                    client.client.close()
        finally:
            lock_db.execute(text('SELECT pg_advisory_unlock(7741201)'))

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')
    parser = argparse.ArgumentParser()
    parser.add_argument('--pages', type=int, default=5)
    parser.add_argument('--max-seconds', type=int, default=1200)
    args = parser.parse_args()
    if not 30 <= args.max_seconds <= 21600:
        parser.error('--max-seconds must be between 30 and 21600')
    if not 1 <= args.pages <= 500:
        parser.error('--pages must be between 1 and 500')
    try:
        ingest(args.pages, args.max_seconds)
    except RuntimeError as exc:
        log.error('%s', exc)
        raise SystemExit(1)
