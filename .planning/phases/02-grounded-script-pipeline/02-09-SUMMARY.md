---
phase: 02-grounded-script-pipeline
plan: 09
subsystem: review-ui
tags: [web, security, phone, docker]
requires:
  - phase: 02-grounded-script-pipeline
    provides: "02-04 gate/store/VERDICT_LABELS_DE"
provides:
  - "review/web.py (4-route stdlib server, nonce, Host allow-list incl. NDC_REVIEW_ALLOWED_HOSTS), review/web_render.py (UI-SPEC pages), ndc review serve"
  - "compose service ndc-review: 127.0.0.1:8090, no env_file, read_only, cap_drop ALL, 256m"
affects: [02-10]
key-decisions:
  - "Phone reaches the UI via the Pi: Host allow-list + 10.0.0.213, 10.8.0.1 (env), bind stays 127.0.0.1 (D-18a)"
  - "PyMuPDF imported lazily — it pulls onnxruntime and OOM'd the 256 MB container on first request"
requirements-completed: [SCR-03]
duration: 45min
completed: 2026-10-26
---

# Phase 2 Plan 09: Phone review UI Summary

**A secret-free, four-route review page the operator used from the phone to confirm a claim and approve a real script.**

## Verification
- Security (live): `/proc/self/environ`, `/%2e%2e/proc/self/environ`, `/../etc/passwd`, `/static/x` → 404 without echo; foreign Host → 400; public IP 217.160.244.33:8090 refused; listens on 127.0.0.1:8090 only; container env has 0 ANTHROPIC/API keys; ReadonlyRootfs true, CapDrop ALL; CSP header present; memory 37 MiB.
- Operator (phone, via Pi tunnel): acked sentence 2 and approved version 2 (670ab1d6…) — review row channel `web` at 2026-10-26T07:52:45Z. Operator: "Approved." / UI: "UI ok".
- Unlocked DB-rendered source list (Graziano 2016 doi:10.1016/j.cpr.2016.04.011; Soler-Gutiérrez 2023 doi:10.1371/journal.pone.0280131).

## Deviations from Plan
1. **[Rule 1] Host allow-list blocked the operator** (Host = Pi address 10.0.0.213 → 400). Operator diagnosed; fixed with `NDC_REVIEW_ALLOWED_HOSTS` (10.0.0.213,10.8.0.1); rejected hosts are now logged.
2. **[Rule 1] OOM on first request** — lazy PyMuPDF import (195 → 37 MiB).
3. Entrypoint calls `/app/.venv/bin/ndc` directly (uv cache can't write on a read-only rootfs).
