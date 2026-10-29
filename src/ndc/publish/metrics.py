"""Fixed-age metric snapshots (MEAS-03): manual entry, TikTok Studio CSV import, due list.

Ages are tolerance windows from config/metrics.yaml; the actual post age is stored per row.
Rows are append-only (corrections = new rows). The due list is written only inside /data.
"""

import csv
import json
import os
from datetime import UTC, datetime
from pathlib import Path

from ndc.db import Database
from ndc.publish.store import load_metrics_cfg, parse_post_url

FIELDS = (
    "views",
    "likes",
    "comments",
    "shares",
    "saves",
    "follows",
    "avg_watch_s",
    "watched_full_pct",
)
INT_FIELDS = {"views", "likes", "comments", "shares", "saves", "follows"}
FYF = ("yes", "no", "unknown")
DUE_ROOT = Path("/data")


class MetricsError(Exception):
    pass


def _parse_ts(s: str) -> datetime:
    s = s.strip().replace("Z", "+00:00")
    dt = datetime.fromisoformat(s)
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _fmt(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def age_hours(posted_at: str, when: datetime) -> float:
    return round((when - _parse_ts(posted_at)).total_seconds() / 3600, 2)


def label_for_age(hours: float, cfg: dict | None = None) -> str:
    cfg = cfg or load_metrics_cfg()
    for label, (lo, hi) in cfg["ages"].items():
        if lo <= hours <= hi:
            return label
    return "adhoc"


def _num(v, field):
    """Tolerant number parsing for TikTok exports: '2.345' / '2,345' / '1 234' -> 2345 for integer
    fields; '38,2%' -> 38.2 and '1,234.5' -> 1234.5 for floats."""
    if v is None or str(v).strip() in ("", "-", "—"):
        return None
    s = str(v).strip().replace("%", "").replace("\u202f", "").replace(" ", "")
    if field in INT_FIELDS:
        digits = "".join(ch for ch in s if ch.isdigit())
        return int(digits) if digits else None
    if "," in s and "." in s:
        s = (
            s.replace(".", "").replace(",", ".")
            if s.rfind(",") > s.rfind(".")
            else s.replace(",", "")
        )
    elif "," in s:
        s = s.replace(",", ".")
    return float(s)


def add_snapshot(
    db: Database,
    publication_id: int,
    age_label: str | None,
    values: dict,
    source: str,
    captured_at: str | None = None,
    fyf_status: str = "unknown",
    fyf_reason: str | None = None,
    raw: dict | None = None,
) -> int:
    cfg = load_metrics_cfg()
    if fyf_status not in FYF:
        raise MetricsError(f"fyf_status muss yes|no|unknown sein, nicht {fyf_status!r}")
    if source not in ("csv", "manual"):
        raise MetricsError("source muss csv oder manual sein")
    when = _parse_ts(captured_at) if captured_at else datetime.now(UTC)
    conn = db.connect()
    try:
        pub = conn.execute("SELECT * FROM publication WHERE id = ?", (publication_id,)).fetchone()
        if pub is None:
            raise MetricsError(f"publication {publication_id} nicht gefunden")
        hours = age_hours(pub["posted_at"], when)
        label = age_label or label_for_age(hours, cfg)
        if label not in (*cfg["ages"].keys(), "adhoc"):
            raise MetricsError(f"unbekanntes Alter {label!r}")
        cols = {f: _num(values.get(f), f) for f in FIELDS}
        return conn.execute(
            "INSERT INTO metric_snapshot (publication_id, age_label, captured_at, post_age_hours, "
            "views, likes, comments, shares, saves, follows, avg_watch_s, watched_full_pct, "
            "retention_json, fyf_status, fyf_reason, source, raw_json) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                publication_id,
                label,
                _fmt(when),
                hours,
                *(cols[f] for f in FIELDS),
                json.dumps(values["retention"]) if values.get("retention") else None,
                fyf_status,
                fyf_reason,
                source,
                json.dumps(raw, ensure_ascii=False) if raw else None,
            ),
        ).lastrowid
    finally:
        conn.close()


def _header_map(headers: list[str], cfg: dict) -> dict[str, str]:
    """our field -> csv header, first match wins (case-insensitive, trimmed)."""
    norm = {h.strip().lstrip("﻿").casefold(): h for h in headers}
    out = {}
    for field, names in (cfg.get("csv_columns") or {}).items():
        for n in names:
            if n.casefold() in norm:
                out[field] = norm[n.casefold()]
                break
    return out


def import_csv(
    db: Database, path: str | Path, captured_at: str | None = None, age_label: str | None = None
) -> dict:
    cfg = load_metrics_cfg()
    p = Path(path)
    with p.open(encoding="utf-8-sig", newline="") as f:
        sample = f.read(4096)
        f.seek(0)
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t") if sample else csv.excel
        reader = csv.DictReader(f, dialect=dialect)
        rows = list(reader)
        headers = reader.fieldnames or []
    hmap = _header_map(headers, cfg)
    report = {"headers": headers, "mapped": hmap, "matched": [], "unmatched": []}
    if "post_url" not in hmap and "post_id" not in hmap:
        raise MetricsError(
            "CSV: keine Spalte für post_url/post_id erkannt — "
            "config/metrics.yaml csv_columns ergänzen. "
            f"Gefundene Spalten: {headers}"
        )
    conn = db.connect()
    try:
        pubs = conn.execute("SELECT id, post_id, post_url, platform FROM publication").fetchall()
    finally:
        conn.close()
    by_id = {(r["platform"], r["post_id"]): r["id"] for r in pubs}
    for row in rows:
        pid = None
        if "post_url" in hmap and row.get(hmap["post_url"]):
            try:
                pid = by_id.get(("tiktok", parse_post_url("tiktok", row[hmap["post_url"]])))
            except Exception:
                pid = None
        if pid is None and "post_id" in hmap and row.get(hmap["post_id"]):
            pid = by_id.get(("tiktok", str(row[hmap["post_id"]]).strip()))
        if pid is None:
            report["unmatched"].append(
                row.get(hmap.get("post_url", ""), "") or row.get(hmap.get("post_id", ""), "?")
            )
            continue
        values = {f: row.get(hmap[f]) for f in FIELDS if f in hmap}
        sid = add_snapshot(db, pid, age_label, values, "csv", captured_at=captured_at, raw=row)
        report["matched"].append({"publication_id": pid, "snapshot_id": sid})
    return report


def due(conn, now: datetime | None = None, cfg: dict | None = None) -> list[dict]:
    cfg = cfg or load_metrics_cfg()
    now = now or datetime.now(UTC)
    out = []
    pubs = conn.execute(
        "SELECT p.*, t.working_title FROM publication p JOIN topic t ON t.id = p.topic_id "
        "ORDER BY p.posted_at"
    ).fetchall()
    for p in pubs:
        scope = cfg["platform_fields"].get(p["platform"], "full")
        labels = list(cfg["ages"].keys()) if scope == "full" else ["7d"]
        have = {
            r[0]
            for r in conn.execute(
                "SELECT age_label FROM metric_snapshot WHERE publication_id = ?", (p["id"],)
            )
        }
        hours = age_hours(p["posted_at"], now)
        for label in labels:
            lo, hi = cfg["ages"][label]
            if label not in have and lo <= hours <= hi:
                out.append(
                    {
                        "publication_id": p["id"],
                        "platform": p["platform"],
                        "age": label,
                        "post_age_hours": hours,
                        "window_closes_in_h": round(hi - hours, 1),
                        "title": p["working_title"],
                        "post_url": p["post_url"],
                        "fields": "full" if scope == "full" else ",".join(scope),
                    }
                )
    return out


def write_due(path: str | Path, items: list[dict], now: datetime | None = None) -> Path:
    target = Path(path)
    try:
        inside = target.resolve().is_relative_to(DUE_ROOT.resolve())
    except (OSError, ValueError):
        inside = False
    if not inside:
        raise MetricsError(f"due-Datei darf nur unter {DUE_ROOT} liegen")
    payload = {"generated_at": _fmt(now or datetime.now(UTC)), "due": items}
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, target)
    return target


def snapshots(conn, publication_id: int) -> list:
    return conn.execute(
        "SELECT * FROM metric_snapshot WHERE publication_id = ? ORDER BY post_age_hours, id",
        (publication_id,),
    ).fetchall()
