# nd-content

Operator CLI `ndc` for a neurodiversity short-form content pipeline (faceless, German, every claim cited).
Run via `docker compose run --rm ndc <cmd>`; tests via `bash scripts/test.sh tests/` inside the container.

## Commands

| Area | Commands | Docs |
|---|---|---|
| Topics & checks (Phase 1) | `ndc topic import|add|list|select|review`, `ndc check …` | `config/matrix.yaml`, `config/terminology.yaml`, `config/safety.yaml` |
| Competitor scan & language decision | `ndc scan …` | `docs/scan-*.md`, `docs/language-decision*.md` |
| Sources | `ndc source search|pick|pick-snapshot|check-ids|list|show|add|import-awmf`, `ndc corpus lock|show` | `docs/script-pipeline.md` §1, §7 |
| Scripts | `ndc script draft [--punch]|punch|show|export|import|verify|sources` | `docs/script-pipeline.md` §1, §4 |
| Review | `ndc review status|show|ack|decide|serve` | `docs/script-pipeline.md` §2–3 |

## Services (docker compose)

- `ndc` — CLI, 1 GB, reads `.env` (`ANTHROPIC_API_KEY`, optional `NCBI_EMAIL`/`NCBI_API_KEY`).
- `ndc-heavy` — on-demand media analysis, niced, 3 GB.
- `ndc-review` — phone review UI, the only long-running service: `127.0.0.1:8090`, no secrets, read-only rootfs, 256 MB.

Data lives in `/home/nd-content-volumes/data` (`ndc.db`, `artifacts/`, `edits/`, `awmf/`). Model IDs, prompts and prices are config only (`config/llm.yaml`, `config/prompts/`).
