# Deploy CineMetrics with Vercel and Neon

This configuration keeps the Next.js frontend and Python 3.12 FastAPI backend in **one Vercel Hobby project**. Neon stores movie data, daily snapshots, pipeline runs, and compressed raw JSON. GitHub Actions runs the private ingestion CLI. No deployment, cloud migration, or repository push is performed by preparing these files.

## Architecture and plan fit

```text
Browser → https://your-project.vercel.app/        → Next.js
Browser → https://your-project.vercel.app/api/*   → FastAPI → Neon pooled connection
GitHub Actions → TMDB → Neon direct connection (snapshots + compressed raw JSON)
```

Official documentation checked November 6, 2026:

- [Vercel Services](https://vercel.com/docs/services) is in beta on all plans, including Hobby. The current configuration uses `services` with service-targeted rewrites; earlier `experimentalServices`/`routePrefix` examples are not used.
- [Services routing](https://vercel.com/docs/services/routing) retains the original incoming path. `backend/index.py` mounts the API at `/api`, so `/api/movies`, `/api/docs`, and `/api/openapi.json` resolve correctly. The Next.js `/movies/{id}` page stays separate. An explicit `/` service lookup targets the generated `/index` page, preserving the browser URL `/`; non-root paths retain their own route lookup.
- [FastAPI on Vercel](https://vercel.com/docs/frameworks/backend/fastapi) supports a single function for the application. [Python configuration](https://vercel.com/docs/functions/runtimes/python) supports `.python-version` and `requirements.txt`; the repository selects Python 3.12.
- [Hobby](https://vercel.com/docs/plans/hobby) is intended for personal, noncommercial use. [Function limits](https://vercel.com/docs/functions/limitations) currently cap Hobby Node/Python requests at 300 seconds with Fluid Compute. This API explicitly uses a 60-second maximum. Function responses have a 4.5 MB limit; the current bounded collection is small, but unbounded movie history may eventually need pagination.
- [Function filesystem restrictions](https://vercel.com/docs/functions/runtimes) provide temporary scratch space, not persistent application storage. The API never ingests or writes raw files.
- [Vercel cron](https://vercel.com/docs/cron-jobs/usage-and-pricing) on Hobby permits daily scheduling with coarse timing, but invokes functions under their runtime limits. This application's sequential requests and bounded retries do not have a reliable five-minute upper bound. There is deliberately no public ingestion or cron endpoint.

**Smallest practical alternative for collection:** the included GitHub Actions job, rather than another paid server. Five pages usually mean approximately 100 detail requests plus list/configuration requests. The CLI has a 20-minute collection budget; the workflow allows 30 minutes for dependencies, collection, and cleanup. The deadline stops network work and records failure instead of relying on a serverless request staying alive. DB timeouts and a runner termination can still interrupt cleanup; inspect a stale `running` record before retrying.

## Vercel project settings

Use the **existing frontend project**, preserving its domain. When you are ready to deploy:

| Setting | Value |
| --- | --- |
| Git repository | `ragna0112/CineMetrics` |
| Production branch | `main` |
| Root Directory | Repository root `.`; remove the existing `frontend` root setting |
| Application mode | Services when detected; let root `vercel.json` define each service |
| Root framework/build/install/output overrides | Clear the old Next.js overrides; do not apply one global frontend build to both services |
| Node.js version | 22.x |
| Backend Python | 3.12 via `backend/.python-version` |
| Frontend service | `frontend`, root `frontend`, Next.js, install `npm ci`, build `npm run build` |
| Backend service | `backend`, root `backend`, FastAPI, entrypoint `index:app` |
| Backend install | Automatically installs `backend/requirements.txt` |
| Backend start override | None. Vercel invokes ASGI; do not configure a continuously running uvicorn service |
| Backend function limit | 60 seconds, configured under the service's `index.py` function |
| Region | Choose the available single function region nearest your Neon database |
| Fluid Compute | Enabled; keep within Hobby limits |
| Vercel cron jobs | None |

If an old project-level Framework Preset prevents Services detection, clear that override/use Other as appropriate in the current UI and reimport with root `.` if needed. Keep the old working frontend deployment available until the new configuration passes checks. Do not change custom-domain DNS until you know which project owns the domain.

The committed Dockerfiles are for local Docker; the Vercel configuration selects native Next.js/FastAPI frameworks, not the container runtime. `.vercelignore` excludes local secrets, dependencies, generated builds, and raw data from upload.

### Separate project fallback

Use this only if Services beta is unavailable in your account or the existing project cannot be converted. Keep the frontend project root `frontend`; create a FastAPI project with root `backend`, Python 3.12 and normal auto-detection of `index.py`. Keep `requirements.txt` as the dependency manifest; an entrypoint-only `pyproject.toml` would take precedence without declaring the runtime dependencies. Both use their directory as project root, so the repository-root Services configuration is not applied. The backend still exposes `/api/*` through `index.py`.

Set the frontend's `NEXT_PUBLIC_API_URL=https://your-backend.vercel.app/api`, set the backend's `CORS_ORIGINS=https://your-frontend.vercel.app`, and set the backend's pooled `DATABASE_URL`. Redeploy the frontend after setting the URL. Cross-project preview frontend URLs require exact CORS entries and a reachable backend deployment; do not solve this by permitting all origins. Two projects add setup and cross-origin requests, so the one-project configuration is preferred.

## Environment variables

Enter real credentials directly into the hosting dashboards. Do not paste them into chat, commit `.env`, or put credentials in `NEXT_PUBLIC_*` variables.

| Variable | Platform and scope | Value or purpose |
| --- | --- | --- |
| `DATABASE_URL` | Vercel Production, server only | Neon **pooled** connection URL, with its SSL query parameters intact |
| `DATABASE_URL` | Vercel Preview, server only | Pooled URL for a separate Neon preview/development branch |
| `NEXT_PUBLIC_API_URL` | Vercel Production and Preview | `/api` for Services; safe public routing path |
| `CORS_ORIGINS` | Vercel Production | Exact frontend origin, e.g. `https://your-project.vercel.app`; comma-separate any actual custom origins, no trailing slash or wildcard |
| `CORS_ORIGINS` | Vercel Preview | Exact allowed external origins only if needed. Same-origin `/api` requests do not require a CORS grant |
| `RAW_ARCHIVE_MODE` | Vercel Production and Preview | `database`; API itself does no archival, this documents the cloud storage mode |
| `TMDB_TOKEN` | GitHub repository Actions **secret** | TMDB API Read Access Token, without a `Bearer ` prefix; not required in Vercel's read-only API |
| `NEON_DATABASE_URL_DIRECT` | GitHub repository Actions **secret** | Neon **direct**, non-pooler connection URL for production ingestion and migrations |
| `ENABLE_DAILY_INGESTION` | GitHub repository Actions **variable**, not secret | `true` only after migration and first ingestion pass; unset/false disables scheduled work |
| `DATABASE_URL` | GitHub job environment, set automatically by workflow | Uses `NEON_DATABASE_URL_DIRECT`; never echoed |
| `RAW_ARCHIVE_MODE` | GitHub job environment, set automatically | `database` |
| `RAW_DATA_DIR` | Local Docker/native only | Durable local directory or named volume; unused in database archive mode |

Services share project environment settings, but only `NEXT_PUBLIC_API_URL` is referenced by browser code. Do not name the database URL or TMDB token with a public prefix. Do not supply production database credentials to untrusted preview code. Only enable trusted previews with their separate database branch.

Neon supplies `postgresql://...` connection strings. The code normalizes both that form and `postgres://...` to SQLAlchemy's psycopg 3 driver; existing `postgresql+psycopg://...` URLs still work. Preserve `sslmode=require` and any supplied `channel_binding=require` parameters. Keep URL-encoded credentials encoded. Examples intentionally omit real credentials.

## Database connections and migrations

The API uses SQLAlchemy `NullPool`, closing physical connections after each session, plus pre-ping, a 10-second connection timeout, and disabled psycopg automatic prepared statements. Neon provides server-side pooling. Cold starts and Neon scale-to-zero can add latency.

The CLI holds a **session-level advisory lock** across fetching and writing. [Neon transaction pooling](https://neon.com/docs/connect/connection-pooling) does not support that lock; use a **direct connection** for ingestion and migrations. A guard rejects Neon `-pooler` hosts for these operations.

Migrations are explicit operations, never build steps, startup hooks, or actions on every user request:

- `001` creates the original five tables on a fresh database.
- `002` adds `raw_responses` and an index without deleting or rewriting existing movie/snapshot rows.
- `alembic upgrade head` applies pending revisions; rerunning after success is safe.

Before changing an existing Neon database, take an available backup/snapshot or test on a Neon branch. If it contains manually created tables but no Alembic version history, stop and compare its schema to the migrations. Do not drop tables or blindly stamp it as migrated. This setup does not upload or replace your old local Docker dataset; Neon starts with whatever already exists there, then receives new observations.

### Recommended initial setup through GitHub Actions

These steps take effect only after you choose to push this prepared code. Pushing to a Vercel-linked branch may automatically deploy; pause automatic deployments first if you want to stage setup privately.

1. GitHub repository → **Settings → Secrets and variables → Actions → Secrets → New repository secret**. Add `NEON_DATABASE_URL_DIRECT` and `TMDB_TOKEN` directly there.
2. Ensure the workflow is on `main` and Actions is enabled. Keep `ENABLE_DAILY_INGESTION` unset.
3. **Actions → Collect TMDB snapshots → Run workflow**. Select branch `main`, operation **migrate**, then run. This executes:

   ```sh
   cd backend
   pip install -r requirements.txt
   alembic upgrade head
   ```

4. Confirm success before continuing. In Neon's SQL Editor, inspect:

   ```sql
   SELECT version_num FROM alembic_version;
   SELECT count(*) FROM movies;
   SELECT count(*) FROM raw_responses;
   ```

   Revision should be `002`; existing movie counts must not have been cleared.

5. Run the workflow again with operation **ingest**, pages **1** for a small first run. It executes:

   ```sh
   cd backend
   python -m app.ingest --pages 1 --max-seconds 1200
   ```

6. Check `pipeline_runs` for success, then run the same operation again and confirm daily uniqueness:

   ```sql
   SELECT id, status, movie_count, started_at, finished_at FROM pipeline_runs ORDER BY id DESC LIMIT 5;
   SELECT movie_id, day, count(*) FROM movie_snapshots GROUP BY movie_id, day HAVING count(*) > 1;
   SELECT count(*), sum(octet_length(payload_gzip)) AS compressed_bytes FROM raw_responses;
   ```

   The duplicate query should return no rows. Additional raw responses/run records on a rerun are expected; the unique daily snapshot remains one per movie/day.

7. You may run ingestion with five pages, then add Actions **Variables → New repository variable → `ENABLE_DAILY_INGESTION=true`**. Daily work collects five pages by default.

### Optional private local initialization

For a trusted local terminal instead of GitHub's manual workflow, create an ignored `backend/.env.neon` by copying `backend/.env.neon.example`. Enter the direct Neon `DATABASE_URL` and `TMDB_TOKEN` in your editor, set `RAW_ARCHIVE_MODE=database`, and never print the file. With a prepared Python 3.12 virtual environment:

```sh
cd backend
.venv/bin/python - <<'PY'
from dotenv import load_dotenv
from subprocess import run
import os
load_dotenv('.env.neon', override=True)
assert os.environ.get('DATABASE_URL'), 'Set DATABASE_URL in .env.neon'
# Inherits configuration without putting the URL in process arguments.
run(['.venv/bin/alembic', 'upgrade', 'head'], check=True)
PY
```

For the first collection use the same loader, replacing the `run` line with:

```python
run(['.venv/bin/python', '-m', 'app.ingest', '--pages', '1', '--max-seconds', '1200'], check=True)
```

Keep `.env.neon` separate from local Docker/native configuration. The supplied local Compose stack continues to use its own database, unprefixed API URLs, and durable raw-data volume.

## Raw JSON durability and storage limits

In `file` mode the original local timestamp/UUID directory archive remains. In `database` mode every successful response is JSON-encoded, gzip-compressed, and committed to `raw_responses` with a pipeline-run foreign key, collection timestamp, and resource identifier. It stores response data, never authorization headers. These archive commits are separate from the final movie transaction, so failed transformations retain their source evidence.

No local folder or `/tmp` is needed by cloud ingestion, and restarting an Actions runner does not remove the Neon archive. Repeated resource fetches are separate archive records. The public API exposes no raw-archive endpoint. To inspect a saved payload through a trusted database session, `gzip.decompress(row.payload_gzip)` returns its UTF-8 JSON bytes.

The tradeoff is database storage and writes. There is no automatic archive deletion. Monitor Neon storage and `pg_total_relation_size('raw_responses')`, including indexes/overhead. Neon Free has finite storage, compute and egress; it also suspends after inactivity. [Current Neon limits](https://neon.com/docs/introduction/plans) must fit your account's usage, and indefinite daily archival cannot be promised on any fixed free quota. Before approaching a limit, export archives to storage you control and verify the backup, or pause collection; object storage is a possible later extension. Do not delete historical snapshots to disguise a quota problem.

## Scheduling reliability and cost controls

The workflow uses a standard `ubuntu-latest` runner, read-only repository permission, no persisted Git credentials, fixed page choices, and a shared concurrency group for manual and scheduled work. Ingestion additionally takes its existing database lock. A manual migration does not fetch TMDB. A scheduled run never migrates automatically.

Schedule: **02:23 UTC daily**, normally **10:23 AM Asia/Manila**. [GitHub schedules](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule) run on the default branch and can be delayed or dropped; public-repository schedules can be disabled after 60 days without activity. Monitor run status and the dashboard's latest successful refresh. Use manual triggering to recover; history only reflects actual collection dates.

[Standard GitHub-hosted runners are free for public repositories](https://docs.github.com/en/billing/concepts/product-billing/github-actions). Private repositories consume included compute usage and can incur charges if additional usage is allowed. Use a zero-spend/stop-usage budget where available and avoid paid runners. No artifact storage is required because archives are in Neon. Vercel, Neon, and GitHub free quotas are shared with your other usage; this is a bounded portfolio setup, not unlimited production capacity.

## Deployment acceptance checks

After you explicitly deploy, replace the example domain below with your actual domain:

```sh
curl --fail https://your-project.vercel.app/api/health
curl --fail https://your-project.vercel.app/api/summary
curl --fail 'https://your-project.vercel.app/api/movies?page_size=2'
```

Open `/api/docs` and the frontend. Verify search against a collected title, filters, pagination, details, poster fallbacks, and charts after a second UTC collection day. Browser network requests must target `/api/*`, never `localhost`. Check that an uncollected title stays honestly absent. No old snapshots are fabricated or imported by this deployment configuration.

If previews are protected, inspect them while signed in; public checks may receive a protection page. Same-origin Services previews keep API calls on the preview deployment. Database branches are configured separately and not automatically created by this repository.

## Local verification for this change

See the deployment preparation entry in `VERIFICATION.md` for executed checks. Schema validation and local tests cannot prove Vercel account availability, a cloud build, Neon SSL connectivity, Actions scheduling, or a successful public deployment. Those require the user's dashboards and credentials after approval to deploy.

## Production routing regression and dependency discovery

The first Services deployment served `/discover` and the generated overview at `/index` but returned Vercel NOT_FOUND at `/`. The explicit root rewrite uses `destination.path=/index` to select the built overview artifact while leaving the public URL unchanged. Source `frontend/app/page.tsx` remains the homepage; no duplicate page or client redirect is needed.

The removed backend `pyproject.toml` only declared an entrypoint. Vercel's Python dependency discovery selected it with no dependencies instead of converting `requirements.txt`. The Services entrypoint remains `index:app` in root configuration, and Python 3.12 remains in `.python-version`. Local Docker, Actions, and Vercel now use the same requirements list.

After every deployment, run the public HTTP check rather than relying on Ready status:

```sh
python3 scripts/verify-deployment.py https://cine-metrics-theta.vercel.app
```

This performs only GET requests to the homepage and `/api/health`; it never runs collection or migrations.
