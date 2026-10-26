# Phase 2: Grounded Script Pipeline - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-10-26
**Phase:** 02-grounded-script-pipeline
**Areas discussed:** LLM execution path, English sources → German script, Source selection & depth, Review & approval rules

---

## LLM execution path

| Question | Options | Selected |
|---|---|---|
| Execution | Real API calls / In-session like Phase 1 / API with hard budget cap | Real API calls |
| Models | Opus draft + Sonnet verify / Sonnet draft + Opus verify / You decide | Opus draft + Sonnet verify |
| Flag loop | Show to operator, no auto-rewrite / One auto-repair round | Show to operator |
| Call log | Full I/O artifact + DB row / DB row only | Full I/O + DB row |

## English sources → German script

| Question | Options | Selected |
|---|---|---|
| Bridge | Draft German directly citing English / Draft English then translate | Draft German directly |
| Review view | German claim + English original / add German gloss | German claim + English original |
| Source list | Original citation, German labels / You decide | Original citation, German labels |

## Source selection & depth

| Question | Options | Selected |
|---|---|---|
| Selection | Operator picks from ranked shortlist / Auto top-K with veto | Operator picks |
| Depth | Abstract + OA full text / Abstracts only | Abstract + OA full text |
| Filters (multi) | Exclude retracted / Recency cut-off / Human studies+reviews only / Evidence-tier floor | Exclude retracted; Human studies+reviews only |
| AWMF | Record status, warn if expired / Block expired | Warn if expired |

## Review & approval rules

| Question | Options | Selected |
|---|---|---|
| Blockers | unsupported+contradicts block, overstated/partial need OK / everything but supports blocks / nothing blocks | unsupported+contradicts block |
| Non-claims | Extractor tags framing, verifier checks / every sentence cites | Extractor tags framing |
| Edits | New version, re-verify changed claims / full re-verify | Re-verify changed claims |
| Surface | HTML sheet + CLI / Terminal only / Phone-first | Phone-first |
| Access | Static HTML sent / Local server over Tailscale / Telegram buttons | Free text: "Why not a webserver in a docker container like polymarket copy trading ui?" |
| Access (follow-up) | Tailscale / Public + login + HTTPS / Cloudflare Tunnel | Free text: "I will create a ssh tunnel to my home network no prob" → bind 127.0.0.1 |
| Phone scope | Approve/reject/request changes / also edit text | Approve/reject/request changes |

**Notes:** Security constraints from the 2026-10-21 polymarkt Safe-drain incident added (no arbitrary path serving, no secrets on page, hash-bound approvals).

## Claude's Discretion

- Topic → query construction, hook variants, length enforcement, web framework, schema/CLI details.

## Deferred Ideas

- Phone-side script editing; Telegram approve card (M2); exposing the polymarkt UI via the same tunnel.
