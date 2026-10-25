# CineMetrics

A movie popularity tracker with a Next.js/TypeScript/Tailwind interface, FastAPI, PostgreSQL, and a private Python ingestion CLI. No authentication or extra processing services. All product data comes from PostgreSQL; there is no demo dataset.

For a student-friendly walkthrough and interview practice, read the [CineMetrics Study Guide](docs/STUDY_GUIDE.md).

## Quick start (Docker)

Install Docker Desktop and start it. From this repository:

```sh
cp .env.example .env
```

Set `TMDB_TOKEN` in `.env` to your **API Read Access Token** from https://www.themoviedb.org/settings/api (not an API key). Keep it private. The default database password is for local development only.

```sh
docker compose up -d db
docker compose build
docker compose run --rm backend alembic upgrade head
docker compose run --rm backend python -m app.ingest --pages 5
docker compose up -d backend frontend
```

Open http://localhost:3000. API documentation: http://localhost:8000/docs. Run the ingestion command again safely any time. Omit ingestion to explore honest empty states. Collect again on a later UTC day to unlock charts and rising rankings.

```sh
docker compose logs -f backend
docker compose down
```

Named volumes retain database and raw responses across restarts. `docker compose down -v` permanently deletes them; ordinary shutdown should omit `-v`. Credentials containing URL-reserved characters need percent-encoding in DATABASE_URL; the supplied Compose interpolation is intended for simple local credentials.

## Native development

Use Node 22 and Python 3.11 or 3.12. macOS's system Python 3.9 is too old for these dependencies.

```sh
docker compose up -d db
cd backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit backend/.env: configure your TMDB_TOKEN.
alembic upgrade head
python -m app.ingest --pages 5
uvicorn app.main:app --reload --port 8000
```

In another terminal:

```sh
cd frontend
cp .env.example .env.local
npm ci
npm run dev
```

The frontend API URL must be reachable by the user's browser. Never use `http://backend:8000` in NEXT_PUBLIC_API_URL. This URL is compiled at build time: rebuild after changing it. TMDB_TOKEN belongs only on the backend.

## How data travels

1. `backend/app/ingest.py` reads TMDB configuration, genre names, popular movie pages, and each movie's details in English. `--pages` accepts 1–500; a page normally contains up to 20 movies. It stops at TMDB's last available page. Adult titles are excluded.
2. Each successful JSON response is archived under `RAW_DATA_DIR/<UTC timestamp>-<UUID>/` before transformation. Files contain response bodies, never request authorization headers.
3. The transformer validates identity, dates and finite nonnegative metrics. Missing metrics remain SQL NULL. Invalid records fail the run rather than silently changing the dataset.
4. One database transaction upserts genres, metadata, associations and daily snapshots. A PostgreSQL advisory lock prevents concurrent runs. Success is recorded atomically with movie changes; failure is recorded separately. Raw files survive failed runs for diagnosis.
5. FastAPI reads stored snapshots. The browser requests the API for every search, filter, sort, page and detail chart.

The CLI uses a 20-second request timeout and five bounded attempts, exponential backoff for transport errors/5xx, and Retry-After for 429 (wait capped at 60 seconds). Persistent failure ends the run. Logs/errors avoid response bodies and credentials. An abruptly killed process can leave a `running` run; inspect it before marking it failed manually. No partial movie transaction is committed.

## Database and migrations

- `movies`: TMDB ID primary key, title, overview, release date, original language, configured poster URL. Indexes on title and release date. Leading wildcard title search is suitable for this bounded portfolio dataset; use pg_trgm if it grows large.
- `genres`: TMDB ID and name.
- `movie_genres`: composite primary key, foreign keys and genre index.
- `movie_snapshots`: primary key `(movie_id, day)`, UTC date, collected timestamp, nullable popularity/rating/vote count. Checks enforce nonnegative scores/counts and rating 0–10. Index on day.
- `pipeline_runs`: start/end time, status, count, sanitized error.

Alembic migration `001` creates the schema. Apply with `alembic upgrade head`; no tables are created by API startup. Back up PostgreSQL using your hosting provider's backups or pg_dump. Raw JSON is an audit archive, not a substitute for database backups.

## API

Interactive OpenAPI at `/docs`, machine schema at `/openapi.json`.

| GET endpoint                | Behavior                                                                                                                                                  |
| --------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `/health`                   | Database/schema readiness; 503 when unavailable                                                                                                           |
| `/summary`                  | Movie count, averages, vote sum, collection range, latest successful refresh                                                                              |
| `/genres`                   | Stored genre options                                                                                                                                      |
| `/movies`                   | `q`, `genre` ID, `year` (1870–2200), `min_votes` (>=0), `sort` (`popularity`, `rating`, `release_date`), `page` (1–10000), `page_size` (1–60, default 12) |
| `/movies/{tmdb_id}`         | Metadata + latest snapshot; 404 if not collected                                                                                                          |
| `/movies/{tmdb_id}/history` | All stored daily observations, ascending date                                                                                                             |
| `/rising?limit=20`          | Positive absolute gains, max 60, shared movies on latest two distinct collection days                                                                     |

Queries use SQLAlchemy bindings; search wildcard characters are escaped. Sort values are an allowlist, with TMDB ID as deterministic tiebreaker and missing values last. API responses return missing values as JSON null. Frontend displays an em dash. CORS permits only configured origins and GET; there is no ingestion HTTP route.

## Metric definitions and limits

**Popularity** is TMDB's own score, not streaming views, audience size, box office or revenue. **Rating** is TMDB vote_average out of 10, and **vote count** is TMDB vote_count.

All overview metrics use each movie's latest stored snapshot, including older observations for titles that have left the fetched popular pages. Average rating/popularity is the unweighted arithmetic mean of non-null values; vote total sums non-null counts and is null if none exist. Movie count includes all collected movies with a snapshot. Filters use those same latest observations. No vote-weighted rating or inferred zero is used.

Rankings describe the accumulated collected dataset, not all of TMDB. Movies aren't deleted when they leave popular pages, and their scores can become stale; every detail page shows its snapshot date. `last_refresh` is the finish time of the latest successful full run, not a claim that every movie was refreshed then.

One snapshot per UTC movie/day: a same-day rerun replaces that day's observation. Older days remain. History begins when you start collecting; TMDB's current endpoint cannot supply this app's past history. Charts display actual dates and do not connect missing metric values. The table below each chart provides accessible exact values.

Rising uses the newest two distinct snapshot dates across the database (which may be more than one calendar day apart), inner-joins movies present on both, excludes null scores, and sorts positive absolute difference descending. Percentage is `(new-old)/old*100`; it is null for a zero baseline. Newly discovered movies cannot rise from an invented zero. The dates are always shown, and the result is not TMDB's own trending endpoint.

## Verification

```sh
cd backend
.venv/bin/python -m pytest -q
```

To include the real PostgreSQL constraint/upsert test, create a **separate disposable test database** first:

```sh
docker compose exec db createdb -U cinemetrics cinemetrics_test
cd backend
TEST_DATABASE_URL=postgresql+psycopg://cinemetrics:cinemetrics@localhost:5433/cinemetrics_test .venv/bin/python -m pytest -q
```

The snapshot constraint test rolls back its movie changes. The pipeline integration test commits within the disposable test database to exercise real transactions, removes its test movie afterward, and leaves test pipeline-run records there. Tests use fixtures only in tests, never product data. They cover validation, missing values, search escaping, filters, pagination, summary calculations, trend comparisons, HTTP errors, bounded retry handling/raw archives, and PostgreSQL same-day upserts.

```sh
cd frontend
npm run typecheck
npm run build
```

Manual live acceptance after supplying credentials:

```sh
docker compose run --rm backend python -m app.ingest --pages 1
docker compose exec db psql -U cinemetrics -d cinemetrics -c 'SELECT day, count(*) FROM movie_snapshots GROUP BY day;'
docker compose run --rm backend python -m app.ingest --pages 1
docker compose exec db psql -U cinemetrics -d cinemetrics -c 'SELECT movie_id, day, count(*) FROM movie_snapshots GROUP BY movie_id, day HAVING count(*) > 1;'
curl http://localhost:8000/summary
curl 'http://localhost:8000/movies?page_size=2&sort=rating'
```

The last SQL query must return no rows. Check title search, genre/year/vote filters, both pagination directions, direct movie URLs, poster fallback, unavailable API states, keyboard navigation, and a 390px viewport. After collecting on another UTC day, verify charts and rising comparison dates. See VERIFICATION.md for checks actually performed during implementation.

## Deployment (no deployment performed)

A straightforward option is a single Linux VM with Docker Compose, persistent disk and cron, behind an HTTPS reverse proxy. It keeps ingestion next to the raw archive. The VM, disk, backups and domain can incur costs. Do not expose PostgreSQL publicly; the supplied port binding is localhost only. Restrict the backend's port with your firewall or proxy. Use unique production DB credentials and HTTPS for both origins. Configure `CORS_ORIGINS=https://your-frontend.example`, and `NEXT_PUBLIC_API_URL=https://your-api.example` before building. Keep `.env` out of Git and grant access only to the service account. Apply migrations before rolling out the API. For a VM deployment, arrange automatic service startup and backups; Docker volumes are local, not highly available.

Install a daily private job on that VM using `crontab -e` (UTC schedule, or use a UTC-configured host):

```cron
CRON_TZ=UTC
15 2 * * * /absolute/path/to/cinemetrics/scripts/ingest-daily.sh /absolute/path/to/cinemetrics >> /absolute/path/to/ingestion.log 2>&1
```

Cron's PATH must include Docker (set PATH explicitly where needed). The Docker daemon must be running. Rotate the log; monitor failed/running pipeline_runs and health checks. `CRON_TZ` support varies by cron implementation; configuring the host to UTC is the portable choice. Raw JSON lives in the `raw_data` volume; back it up and provision space for daily details responses. Choose retention based on your audit needs; no automatic deletion is included.

Managed alternative: Render web services + Render PostgreSQL. Create PostgreSQL, use its private connection URL with SQLAlchemy's `postgresql+psycopg://` scheme. Frontend root `frontend`, Node 22, build `npm ci && npm run build`, start `npm start -- --port $PORT`. Backend root `backend`, Python 3.12, build `pip install -r requirements.txt`, pre-deploy `alembic upgrade head`, start `uvicorn app.main:app --host 0.0.0.0 --port $PORT`, health `/health`. Configure the public browser API URL at build time and exact frontend origin on backend CORS. Migrations must run once per release, not per worker. Keep secrets in provider environment settings.

A Render cron job cannot access a persistent disk, including the API service's disk. This CLI writes raw JSON locally, so **do not run it on ephemeral Render cron storage if you need those archives**. Use the VM cron setup above, or implement object-storage archival before using an isolated managed cron job. Paid services, persistent disks, database storage/backups, and cron execution have separate charges. Free web services have cold starts and no persistent disk; free database offerings have limits and are unsuitable as an assumed durable production tier. Check current plan details rather than relying on a permanently free deployment.

Official docs reviewed for this implementation:

- [Next.js installation](https://nextjs.org/docs/app/getting-started/installation), [Tailwind with Next.js](https://tailwindcss.com/docs/installation/framework-guides/nextjs)
- [FastAPI containers](https://fastapi.tiangolo.com/deployment/docker/), [PostgreSQL constraints](https://www.postgresql.org/docs/current/ddl-constraints.html)
- [TMDB popular movies](https://developer.themoviedb.org/reference/movie-popular-list), [image configuration](https://developer.themoviedb.org/docs/image-basics), [rate limiting](https://developer.themoviedb.org/docs/rate-limiting), [popularity](https://developer.themoviedb.org/docs/popularity-and-trending), [attribution and API terms](https://developer.themoviedb.org/docs/faq)
- [Render Next.js](https://render.com/docs/deploy-nextjs-app), [FastAPI](https://render.com/docs/deploy-fastapi), [cron](https://render.com/docs/cronjobs), [disks](https://render.com/docs/disks), [free service limits](https://render.com/docs/free), [pricing](https://render.com/pricing)

## Attribution

The Credits footer identifies TMDB and displays its required notice. TMDB images are loaded using configuration from the API and the stored poster path. No invented posters or images are bundled. Noncommercial developer usage requires attribution; commercial usage requires discussing licensing with TMDB. See their [FAQ](https://developer.themoviedb.org/docs/faq) and [approved logos](https://www.themoviedb.org/about/logos-attribution). Check that your public use meets their current terms.

## Troubleshooting

- **503 / empty dashboard:** start PostgreSQL, apply migrations, and check `/health`. An empty successful database needs the first CLI run.
- **Ingestion exits:** check token (Read Access Token, no `Bearer ` prefix), network and pipeline_runs. Raw files show how far fetching progressed. Failed runs preserve previous good movie data.
- **No trends:** same-day reruns don't create history; wait until a different UTC day.
- **Browser fetch fails:** ensure the public API URL is correct, HTTPS matches the frontend, and CORS exactly matches scheme/host/port. Rebuild frontend after changing the API URL.
- **Docker connection error:** launch Docker Desktop and wait for its engine.
- **Native dependency error on macOS:** use Python 3.11+ instead of `/usr/bin/python3`.
