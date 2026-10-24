"""Competitor sheet export (MKT-01): one definition, the v_competitor_sheet view, written by
csv.DictWriter. export_accounts() emits exactly the AccountRow columns consumed by `scan decide`.
"""

import csv
from pathlib import Path

from ndc.db import Database
from ndc.scan.decide import AccountRow

ACCOUNT_COLUMNS = tuple(AccountRow.model_fields)
_FACE = {"face", "faceless", "mixed", "unknown"}
_VOICE = {"male", "female", "mixed", "none", "unknown"}


def export_sheet(db: Database, path: str | Path) -> int:
    conn = db.connect()
    try:
        cur = conn.execute("SELECT * FROM v_competitor_sheet ORDER BY language, platform, handle")
        cols = [d[0] for d in cur.description]
        rows = cur.fetchall()
    finally:
        conn.close()
    with Path(path).open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow(dict(r))
    return len(rows)


def _score(v) -> int | None:
    try:
        s = int(v)
    except (TypeError, ValueError):
        return None
    return s if 0 <= s <= 3 else None


def export_accounts(db: Database, path: str | Path, selected_only: bool = True) -> int:
    """AccountRow CSV. Default: selected accounts; when nothing is selected yet, all accounts."""
    conn = db.connect()
    try:
        sql = "SELECT * FROM v_competitor_sheet"
        rows = conn.execute(sql + " WHERE status = 'selected'").fetchall() if selected_only else []
        if not rows:
            rows = conn.execute(sql).fetchall()
    finally:
        conn.close()
    out = []
    for r in rows:
        if r["language"] not in ("de", "en"):
            continue
        acc = AccountRow(
            handle=r["handle"],
            language=r["language"],
            platform=r["platform"],
            followers=r["followers"],
            reach_median=r["median_views_15"],
            n_reach_posts=r["n_reach_posts"] or 0,
            source_citing_score=_score(r["source_citing_score"]),
            face=r["face"] if r["face"] in _FACE else "unknown",
            voice_gender=r["voice_gender"] if r["voice_gender"] in _VOICE else "unknown",
        )
        out.append(acc.model_dump())
    with Path(path).open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(ACCOUNT_COLUMNS))
        w.writeheader()
        for row in out:
            w.writerow({k: ("" if v is None else v) for k, v in row.items()})
    return len(out)
