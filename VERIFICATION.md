# Verification — 2026-10-23

## Passed

- Installed frontend dependencies; npm audit reported 0 vulnerabilities at install time.
- Python 3.11 dependency installation. Python 3.9 initially failed because current Alembic requires a newer Python; README explicitly requires 3.11+.
- Started Docker Desktop and PostgreSQL 18. Default port 5432 was occupied, so this project's local database port is 5433.
- Applied Alembic migration 001 against real PostgreSQL; queried alembic_version and confirmed 001.
- 13 pytest tests passed, including real PostgreSQL same-day snapshot upsert, full CLI orchestration with a test-only mock TMDB client, rerun uniqueness, and rollback on invalid data. Other tests cover filters, search escaping, pagination, null-preserving summaries, comparable-day trends, missing movie errors, validation, retries and raw JSON archival.
- Test fixtures are confined to backend/tests and a separate cinemetrics_test database. No fixtures were inserted into the product database.
- Running API: /health returned ok; /summary reported zero movies and null metrics; /movies and /rising returned empty collections.
- `docker compose config --quiet` passed. Both application Docker images built successfully; the frontend production build also passed inside its Node 22 container.
- Containerized `alembic upgrade head` completed successfully against PostgreSQL.
- `npm run typecheck` passed.
- `npm run build` passed (Next.js 16.4.2).
- Browser opened the real local frontend: honest empty collection, zero count, null scores shown as dashes, discovery navigation, typing into search, and rising insufficient-history state confirmed. Narrow browser viewport was 568px wide; header/navigation and summary grid visibly adapted. The Docker production frontend was also inspected at 1280px, with correct empty-database responses and desktop layout. Screenshot: docs/preview.png.
- Missing-token CLI exits with a clear instruction and no invented data.

## Warnings / initial failures resolved

- Pytest emits one upstream Starlette/AnyIO deprecation warning. It does not fail tests.
- Python 3.9 dependency installation failed; switched to Python 3.11.
- Database port conflict resolved by using port 5433.

## Not verified

- Real TMDB fetch/ingestion and live same-day rerun: no token was available. The rerun mechanism was tested using mocked input against real PostgreSQL, not claimed as a live TMDB integration test.
- Populated movie cards, genre options, result pagination, detail pages and history charts in the browser: require collected data. Query behavior and trend arithmetic are tested with test-only fixtures.
- Exact 390px phone viewport and comprehensive keyboard/screen-reader audit.
- Public deployment, HTTPS, production CORS origin, scheduler execution and backup restore. No services were purchased or published.
- TMDB official attribution/logo page and logo asset fetch returned robots/HTTP 403 in this environment. The footer includes the required notice, Credits landmark, and official logo asset URL. Confirm the approved logo loads and current brand terms before public deployment. Poster URLs are built from TMDB configuration; real poster loading requires ingestion.

## Running locally after implementation

PostgreSQL container is running on localhost:5433. Dockerized API and frontend are running on ports 8000 and 3000; the native verification servers were stopped. Product database is empty. Follow README for reproducible startup and token setup; no .env secrets were created.

## Live TMDB follow-up — 2026-10-23 (Asia/Manila)

The user subsequently supplied a Read Access Token. Stored only in the root .env file (mode 0600, covered by .gitignore). Successfully ingested five popular pages: 96 distinct movies. A one-page same-day rerun succeeded; PostgreSQL still had 96 movies and 96 snapshots, with zero duplicate movie/day groups. UTC collection day: 2026-10-22.

Live API title search for Inception, genre/min-votes/rating filters, second-page results, movie details and snapshot history succeeded. Browser title search returned Inception with its real poster and score; its detail URL loaded real metadata and an honest one-day-history state. The TMDB attribution logo also loaded in the browser. These checks supersede the earlier missing-token and poster/logo limitations above. Multi-day charts and rising gains still require a later UTC collection day; no older observations were fabricated.

## Vercel and Neon preparation on November 6 2026

This entry describes local preparation, not a cloud deployment.

- Inspected actual configuration, migrations, request paths, ingestion, archive handling, and test fixtures before choosing one Vercel Services project.
- Checked current official Vercel Services/Hobby/FastAPI/Python/runtime/filesystem/cron documentation, Neon connection pooling and free-plan limits, and GitHub scheduling/billing docs. Sources and exact settings are in docs/DEPLOYMENT.md.
- Root vercel.json validated against the live official Vercel JSON schema. This is configuration-schema validation, not a Vercel cloud build.
- GitHub workflow YAML structurally validated: only manual/scheduled triggers, read-only contents permission, main-branch condition, opt-in schedule, concurrency group with no cancellation, and a bounded 30-minute job. No Actions workflow was dispatched.
- Fresh disposable local PostgreSQL database: migration 001, insert an existing test movie, upgrade to 002, repeat upgrade to head. Existing movie remained and revision was 002. No production database was migrated.
- 22 backend tests passed on native Python 3.11 and the existing Python 3.12.15 container runtime with current source mounted read-only and a disposable PostgreSQL database. Coverage includes URL normalization/SSL preservation, connection pooling choice, direct-host guard, /api routes/docs, missing ingestion route, raw archive persistence, no filesystem writes in database mode, deadlines, complete mocked TMDB ingestion with PostgreSQL archives, plus prior query/trend/upsert tests. One upstream Starlette/AnyIO deprecation warning remains.
- Production Next.js build passed with NEXT_PUBLIC_API_URL=/api; TypeScript check passed. Inspected frontend calls: all use the central request helper; localhost is only a development fallback and the explicit local Docker setting.
- Docker Compose configuration validation and git diff whitespace check passed. Existing local startup commands and file-archive defaults retained.
- An optional fresh backend image build stalled during Docker registry metadata resolution and was canceled; current-source tests were run successfully using the already available Python 3.12 backend image instead. A first test container launch with a nested read-only mount failed before execution; corrected the bind target and the test run passed. This does not verify a new image build or Vercel package bundle.

Not checked: actual Vercel Services beta availability/settings for the account, Vercel build/runtime, Neon credentials/SSL connection, public URLs/CORS at the CDN, GitHub secret entry or scheduled execution, and multi-day cloud observations. No secrets were read into the output, no cloud resources created, no public deployment performed, and no commit/push made (a connected branch push could trigger deployment). User must enter cloud secrets directly in provider dashboards.

## Production Services routing and packaging fix

Before the fix, direct public HTTP checks found `/` returning Vercel NOT_FOUND (404), `/discover` and `/index` serving CineMetrics HTML (200), and `/api/health` and `/api/docs` failing function invocation (500). The Next.js production output contained the overview at `server/app/index.html` and a prerender entry for `/`.

Official Vercel Python package discovery (CLI 65.12.1) selected the entrypoint-only backend/pyproject.toml with no project dependencies. After removing it, the same discovery selected requirements.txt with all required API dependencies. The entrypoint remains in vercel.json. An explicit `/` service rewrite selects `/index` without changing the public request URL. No database changes, resets, migration jobs, or collection jobs were run for this fix.

Local checks: production frontend build passed with NEXT_PUBLIC_API_URL=/api; Vercel schema validation and homepage artifact check passed; backend tests: 19 passed, 3 PostgreSQL tests skipped, one upstream deprecation warning. Added scripts/verify-deployment.py to check real public homepage HTML and database health using GET requests.

Authenticated Vercel dashboard access was unavailable (browser required login, no local Vercel auth). Public GitHub commit statuses provide deployment progress, while HTTP responses determine actual acceptance. The user was asked for runtime/frontend build logs if the code fixes do not restore service. Live acceptance results are recorded separately after redeployment.
