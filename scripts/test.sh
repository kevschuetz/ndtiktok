#!/usr/bin/env bash
# Run pytest inside the nd-content container. Usage: bash scripts/test.sh [pytest args]
set -euo pipefail
cd "$(dirname "$0")/.."
docker compose build -q ndc
docker compose run --rm --entrypoint uv ndc run --no-sync pytest -q "$@"
