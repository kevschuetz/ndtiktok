---
phase: 01-market-decision-content-foundation
plan: 01
subsystem: infra
tags: [uv, typer, sqlite, docker, walking-skeleton]
requires: []
provides:
  - "ndc Typer CLI with topic/check/scan sub-apps + doctor"
  - "Database class: sole DDL owner, numbered schema/NNN_*.sql migrations in schema_migrations, WAL"
  - "topic + llm_run tables (001_core.sql)"
  - "nd-content compose project: ndc service, 1g mem cap, no ports, /home/nd-content-volumes/data:/data"
  - "scripts/test.sh (pytest inside the container)"
affects: [01-02, 01-03, 01-04, 01-05, 01-06, 01-10, phase-2, phase-3]
tech-stack:
  added: [typer 0.27.3, sqlite-utils 4.2.1, pydantic 2.14.1, pyyaml 6.0.3, python-dotenv 1.2.4, rich 15.0.0, httpx 0.28.1, tenacity 9.2.1, simplemma 2.0.0, yt-dlp 2026.10.21 (extra scan), pytest 9.1.1, ruff 0.17.2, pytest-recording 0.14.0]
  patterns:
    - "Sub-apps registered once in cli.py; later plans edit only their sub-app module"
    - "Migrations: add src/ndc/schema/NNN_*.sql (numbers reserved per plan); never DDL in .py"
    - "Tests isolate via NDC_DB=tmp, NDC_ENV_FILE=nonexistent (autouse fixture)"
key-files:
  created:
    - pyproject.toml
    - uv.lock
    - Dockerfile
    - docker-compose.yml
    - scripts/test.sh
    - src/ndc/cli.py
    - src/ndc/config.py
    - src/ndc/db.py
    - src/ndc/schema/001_core.sql
    - src/ndc/schema/_tracking.sql
    - src/ndc/topics.py
    - src/ndc/topics_cli.py
    - src/ndc/checks/cli.py
    - src/ndc/scan/cli.py
    - tests/conftest.py
    - tests/test_db.py
    - tests/test_cli_topic.py
  modified:
    - .gitignore
decisions:
  - "schema_migrations bootstrap DDL lives in schema/_tracking.sql (not a numbered migration) so no .py file contains CREATE TABLE"
  - ".env loading is explicit: NDC_ENV_FILE or ./.env in cwd, never override; tests point it at a nonexistent file so the real key never leaks into test runs"
  - "Build backend left as uv init default (uv_build, Astral) — part of the uv toolchain, fetched at build time"
metrics:
  duration: ~15min
  completed: 2026-10-24
---

# Phase 1 Plan 01: Walking Skeleton Summary

uv/Typer `ndc` CLI with a WAL SQLite DB (migration runner + topic/llm_run tables) running in a 1g-capped, port-free `nd-content` Docker container on `/home/nd-content-volumes/data`; `topic add` / `topic list` round-trip proven in Docker.

## Package legitimacy gate (Task 1)

Resolved by the operator before execution: **"packages approved"** — all listed packages approved, none dropped. The orchestrator verified on PyPI that every name and pinned version exists (typer 0.27.3, sqlite-utils 4.2.1, pydantic 2.14.1, pyyaml 6.0.3, python-dotenv 1.2.4, rich 15.0.0, httpx 0.28.1, tenacity 9.2.1, simplemma 2.0.0, yt-dlp 2026.10.21, pytest 9.1.1, ruff 0.17.2, pytest-recording 0.14.0, plus plan-06 faster-whisper 1.2.1, av, pillow, numpy) and that `python:3.13-slim` and `ghcr.io/astral-sh/uv:0.13.5` resolve. `anthropic` not installed (D-21). The uv image pulled fine; no pip fallback needed (assumption A11 holds).

## Tasks

| Task | Name | Commit |
|---|---|---|
| 1 | Package legitimacy checkpoint | resolved by operator (no commit) |
| 2 | Scaffold ndc + topic add/list via SQLite (TDD) | 4a7e595 (RED), f6fdbe7 (GREEN) |
| 3 | Memory-capped Docker container on own volume | 7e65105 |

## Verification

- Host: `uv run pytest -q` → 6 passed; `uv run ruff check src tests` → clean; `ruff format` applied.
- Container: `bash scripts/test.sh tests/` → 6 passed.
- `docker compose run --rm ndc doctor` →
  ```
  db: /data/ndc.db
  config_dir: /app/config
  migrations: 001_core.sql
  ANTHROPIC_API_KEY: present
  ```
- Smoke: `docker compose run --rm ndc topic add --pillar parents --condition adhd --domain routines_household --audience parents --angle try_this_strategy --title "Smoke: Morgenroutine" --tag whitelist --source-likely yes` → `added topic 1`; `topic list` showed the row (list_tag `whitelist`, status `proposed`). Row then deleted via `docker compose run --rm -T --entrypoint uv ndc run --no-sync python -c "...DELETE..."` → `remaining 0`. `/home/nd-content-volumes/data/ndc.db` exists, topic table empty.
- Grep checks: one `CREATE TABLE IF NOT EXISTS topic` and one `llm_run` in 001; no `CREATE TABLE` in any .py; `mem_limit: 1g` = 1, `ports:` = 0, volume mount = 1; `git check-ignore .env` → `.env`; `anthropic` absent from pyproject.toml; `.env` still mode 600 and untracked.
- polymarkt-watch untouched (no commands run there; distinct compose project `nd-content`, network `nd-content_default`).

## Deviations from Plan

**1. [Rule 3 - Blocking] schema_migrations DDL moved out of db.py**
- Acceptance criterion requires no `CREATE TABLE` in any .py; the runner's own tracking table needed DDL. Put it in `src/ndc/schema/_tracking.sql` (does not match the `NNN_*.sql` pattern, so it is not tracked as a migration). Commit f6fdbe7.

**2. [Rule 2 - Correctness] Explicit .env path + test isolation**
- `load_dotenv()` default discovery would find `/home/nd-content/.env` during host test runs and make the "missing" doctor test see the real key. Added `NDC_ENV_FILE` (default `./.env` in cwd); conftest sets it to a nonexistent file. Commit 4a7e595 / f6fdbe7.

**3. [Rule 1 - Usability] `topic list` table width**
- Rich table uses terminal width on a TTY (phone SSH), fixed 200 columns when piped/in tests. Commit 7e65105.

Note for operators: `docker compose config` (unfiltered) expands `env_file` into the output and would print the key — only ever run it piped through grep.

## Known Stubs

- `ndc check` and `ndc scan` sub-apps are intentionally empty (help text only); populated by plans 01-02 and 01-03/01-04.
- `config/`, `docs/`, `scan/` contain only `.gitkeep` so the compose mounts exist.

## Self-Check: PASSED
