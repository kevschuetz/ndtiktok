"""Tier-stratified per-language sample (D-02).

Order: operator include (always) / exclude (never) -> D-04 seeds that exist on the platform with
>= 1000 followers -> per-tier quotas (mid >= mid_min, micro ~micro, macro ~macro, mega <= mega_max),
TikTok-weighted per platform_share -> backfill to target from mid, micro, macro. Order inside a
pool is a deterministic hash of the handle (reproducible, not biased by size). Shortfalls are
stored in a scan_run row (stage 'select') and printed.
"""

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

from ndc.db import Database
from ndc.scan import fetch, prereg
from ndc.scan.decide import load_rule

TIERS = ("mid", "micro", "macro", "mega")


@dataclass
class SelectResult:
    language: str
    selected: list = field(default_factory=list)  # (platform, handle) sorted
    counts: dict = field(default_factory=dict)
    shortfall: str | None = None
    notes: list = field(default_factory=list)
    run_id: int | None = None


def _key(row) -> str:
    return hashlib.sha256(f"{row['platform']}:{row['handle'].lower()}".encode()).hexdigest()


def select(db: Database, language: str, cfg: str | Path | None = None) -> SelectResult:
    scfg = fetch.load_scan_config(cfg)
    q = scfg.get("quotas") or {}
    target = int(q.get("target", 40))
    share = q.get("platform_share") or {"tiktok": 28, "youtube": 12}
    tt_frac = share.get("tiktok", 28) / max(1, share.get("tiktok", 28) + share.get("youtube", 12))
    mid_min, mega_max = int(q.get("mid_min", 12)), int(q.get("mega_max", 5))
    tier_target = {
        "micro": int(q.get("micro", 10)),
        "macro": int(q.get("macro", 10)),
        "mega": mega_max,
    }
    tier_target["mid"] = max(mid_min, target - sum(tier_target.values()))
    min_followers = load_rule(prereg.rule_path(cfg)).sample_min_followers

    conn = db.connect()
    try:
        rows = conn.execute(
            "SELECT c.id, c.handle, c.platform, c.seed_named, c.operator_decision,"
            " a.followers, a.tier, a.fetch_status FROM competitor_candidate c"
            " LEFT JOIN competitor_account a ON a.handle = c.handle AND a.platform = c.platform"
            " WHERE c.language = ?",
            (language,),
        ).fetchall()
    finally:
        conn.close()

    res = SelectResult(language=language)
    chosen: dict[int, object] = {}
    usable = []
    for r in rows:
        if r["operator_decision"] == "exclude":
            continue
        if r["operator_decision"] == "include":
            chosen[r["id"]] = r
            continue
        on_platform = r["followers"] is not None and r["fetch_status"] in ("ok", "operator_entered")
        if r["seed_named"]:
            if not on_platform:
                res.notes.append(
                    f"seed {r['platform']}:{r['handle']}: not on platform "
                    f"(fetch_status {r['fetch_status'] or 'not fetched'})"
                )
                continue
            if r["followers"] < min_followers:
                res.notes.append(
                    f"seed {r['platform']}:{r['handle']}: {r['followers']} followers, "
                    f"below {min_followers} (not selected)"
                )
                continue
            chosen[r["id"]] = r
            continue
        if on_platform and r["followers"] >= min_followers and r["tier"] in TIERS:
            usable.append(r)
    usable.sort(key=_key)

    def count(tier=None, platform=None):
        return sum(
            1
            for r in chosen.values()
            if (tier is None or r["tier"] == tier)
            and (platform is None or r["platform"] == platform)
        )

    def take(pool, n):
        got = 0
        for r in pool:
            if got >= n:
                break
            if r["id"] not in chosen:
                chosen[r["id"]] = r
                got += 1
        return got

    for tier in TIERS:
        need = tier_target[tier] - count(tier)
        if need <= 0:
            continue
        pool = [r for r in usable if r["tier"] == tier]
        tt_need = max(0, round(tier_target[tier] * tt_frac) - count(tier, "tiktok"))
        got = take([r for r in pool if r["platform"] == "tiktok"], min(need, tt_need))
        got += take([r for r in pool if r["platform"] == "youtube"], need - got)
        take(pool, need - got)  # backfill from either platform

    n_mid = count("mid")
    if n_mid < mid_min:
        res.shortfall = f"mid tier shortfall: {n_mid} of {mid_min}"
        res.notes.insert(0, res.shortfall)
    for tier in ("mid", "micro", "macro"):
        if len(chosen) >= target:
            break
        take([r for r in usable if r["tier"] == tier], target - len(chosen))

    res.selected = sorted((r["platform"], r["handle"]) for r in chosen.values())
    res.counts = {t: count(t) for t in TIERS}
    res.counts.update(total=len(chosen), tiktok=count(platform="tiktok"))
    res.counts["youtube"] = count(platform="youtube")

    conn = db.connect()
    try:
        conn.execute("BEGIN")
        conn.execute(
            "UPDATE competitor_candidate SET status = CASE"
            " WHEN operator_decision = 'exclude' THEN 'excluded' ELSE 'candidate' END"
            " WHERE language = ?",
            (language,),
        )
        conn.executemany(
            "UPDATE competitor_candidate SET status = 'selected' WHERE id = ?",
            [(cid,) for cid in chosen],
        )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()

    res.run_id = prereg.record_scan_run(db, "select", cfg)
    summary = f"select {language}: " + ", ".join(f"{k} {v}" for k, v in res.counts.items())
    fetch.add_run_note(db, res.run_id, "; ".join([summary, *res.notes]))
    fetch.finish_run(db, res.run_id)
    return res
