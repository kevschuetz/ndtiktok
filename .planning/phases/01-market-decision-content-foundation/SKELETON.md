# Walking Skeleton — nd-content

**Phase:** 1
**Generated:** 2026-10-24

## Capability Proven End-to-End

The operator runs `docker compose run --rm ndc topic add ...` and then `docker compose run --rm ndc topic list`, and the topic they just added comes back from a SQLite file on the project's own host volume, inside a memory-capped container with no open ports.

## Architectural Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Language / runtime | Python 3.13 in `python:3.13-slim`; uv 0.13.5 for env, lock and run | Research STACK.md: one language, reproducible `uv.lock`, fast Docker builds |
| Interface | Typer CLI `ndc` with sub-apps `topic`, `check`, `scan` (+ top-level `doctor`) | M1 is CLI-only (no web app, no task queue). Sub-apps live in their own modules (`ndc/topics_cli.py`, `ndc/checks/cli.py`, `ndc/scan/cli.py`) and are registered once in `ndc/cli.py`, so later plans add commands without touching `cli.py` and can run in parallel |
| Data layer | One SQLite file, WAL mode, stdlib `sqlite3` for DDL; sqlite-utils for convenience I/O (CSV export, upserts) | Zero ops, easy backup; research ARCHITECTURE "ledger of evidence" |
| Schema ownership | `ndc/db.py` is the only code that runs DDL. It applies `src/ndc/schema/NNN_*.sql` in filename order, tracked in a `schema_migrations` table, idempotently on every connect | One schema owner prevents drift; numbered files let parallel plans each add their own migration without editing the same file. Numbers are reserved per plan: 001 core (01), 002 checks (02), 003 decision/prereg (03), 004 competitor (04), 006 analysis (06) |
| DB location | `NDC_DB` env var, default `/data/ndc.db` inside the container; `/data` is bind-mounted from `/home/nd-content-volumes/data` | Own volume on the shared host; never the host's `/data` (belongs to another project's convention) |
| Config | Versioned YAML/Markdown under `config/` (git-reviewed, mounted read-only); each subsystem loads its own file through a pydantic model; `ndc/config.py` only resolves the config directory (`NDC_CONFIG_DIR`, default `/app/config`) | Content rules are judgment artifacts that need diffs and review; secrets never live here |
| Secrets | `.env` (gitignored, operator-created, chmod 600) loaded with python-dotenv; `.env.example` committed; `ndc doctor` reports presence only, never the value | ASVS L1 secret handling; the Anthropic key is for Phase 2+ |
| LLM access | Phase 1 makes no Anthropic API calls (D-21): judgment steps (source-citing scoring, frame analysis) are done in-session by the Claude Code executor and imported via `ndc scan import-judgments` with provenance `llm_session`. From Phase 2: Anthropic SDK 2.3.x directly, model IDs from `config/models.yaml`, every call writes an `llm_run` row (table created in 001) | Cost (operator, D-21); research: no agent frameworks; SCR-06 audit table exists from day one |
| Auth | None (local single-operator CLI, no network listener) | No server, no users; exposing no port is itself the control |
| Deployment target | `docker compose run --rm ndc <cmd>` on the shared polymarkt-watch host. Service `ndc`: `mem_limit: 1g`, `memswap_limit: 1g`, `cpus: "1.0"`, no `ports:`, no restart policy. Plan 06 adds `ndc-heavy` (same image, `mem_limit: 3g`, `nice -n 19`) for transcription | Must never starve polymarkt-watch; CLI-only, nothing listening |
| Tests | pytest inside the container via `bash scripts/test.sh <paths>`; `src/` and `tests/` are bind-mounted so code edits need no rebuild; tests always use a tmp DB via `NDC_DB` | Research validation architecture; host has no project venv guarantees |
| Directory layout | `src/ndc/{cli,db,config,topics,topics_cli,llm}.py`, `src/ndc/checks/`, `src/ndc/scan/`, `src/ndc/schema/`, `config/`, `docs/`, `scan/`, `tests/`, `scripts/` | Module-per-subsystem, mirrors research "Recommended Project Structure" |

## Stack Touched in Phase 1

- [ ] Project scaffold (uv project `ndc`, ruff, pytest config, Dockerfile, compose)
- [ ] Routing — Typer `ndc` entrypoint with `topic`, `check`, `scan` sub-apps and `doctor`
- [ ] Database — `ndc topic add` (real write) and `ndc topic list` (real read) against `/data/ndc.db`
- [ ] UI — the operator CLI command (`ndc topic add` / `ndc topic list`) is the interactive surface
- [ ] Deployment — `docker compose run --rm ndc topic list` on the shared host, with the volume at `/home/nd-content-volumes/data`

## Out of Scope (Deferred to Later Slices)

- Any web UI, HTTP server, Telegram bot or exposed port (M2 at the earliest)
- Scheduler/daemon/cron (M1 is operator-invoked commands only)
- Vector DB, embeddings, agent frameworks
- Source retrieval, script generation, fact-check, review gate (Phase 2)
- Accounts, crisis playbook, publishing, metrics log (Phase 3)
- Non-root container user hardening (no listener; revisit when M2 adds a long-running service)

## Subsequent Slice Plan

Each later slice adds commands/modules on top of this skeleton without changing its decisions:

- Phase 1 plan 02: `ndc check` terminology + safety filter, style guide
- Phase 1 plan 03: committed language decision rule + `ndc scan rule` / `ndc scan decide`
- Phase 1 plans 04–08: competitor scan (discovery, fetch, automated analysis, operator spot-check, decision)
- Phase 1 plans 09–10: hashtag + crisis-line sets; pruned topic matrix backlog
- Phase 2: `ndc retrieve` / `ndc draft` / `ndc verify` / review gate on the same DB and CLI
- Phase 3: publish log + metric snapshots on the same DB and CLI
