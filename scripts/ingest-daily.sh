#!/bin/sh
set -eu
# Pass the absolute repository path as the first argument.
cd "${1:?Usage: ingest-daily.sh /absolute/path/to/cinemetrics}"
docker compose run --rm -T backend python -m app.ingest --pages 5
