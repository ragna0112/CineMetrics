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
