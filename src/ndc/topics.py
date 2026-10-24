"""Topic storage. Dimensions are free text here; plan 05 adds vocab validation."""

import sqlite3
from typing import Any

from ndc.db import Database

INSERT_COLUMNS = (
    "pillar",
    "condition",
    "domain",
    "audience",
    "angle",
    "language",
    "working_title",
    "summary",
    "list_tag",
    "source_likely",
    "origin",
)
FILTER_COLUMNS = ("pillar", "condition", "domain", "audience", "angle", "list_tag", "status")
LIST_COLUMNS = (
    "id",
    "pillar",
    "condition",
    "domain",
    "audience",
    "angle",
    "working_title",
    "list_tag",
    "status",
)


def add_topic(db: Database, **fields: Any) -> int:
    unknown = set(fields) - set(INSERT_COLUMNS)
    if unknown:
        raise ValueError(f"unknown topic fields: {sorted(unknown)}")
    cols = [c for c in INSERT_COLUMNS if fields.get(c) is not None]
    placeholders = ", ".join("?" for _ in cols)
    sql = f"INSERT INTO topic ({', '.join(cols)}) VALUES ({placeholders})"
    conn = db.connect()
    try:
        cur = conn.execute(sql, [fields[c] for c in cols])
        return int(cur.lastrowid)
    finally:
        conn.close()


def list_topics(db: Database, filters: dict[str, Any] | None = None) -> list[sqlite3.Row]:
    filters = {k: v for k, v in (filters or {}).items() if v is not None}
    unknown = set(filters) - set(FILTER_COLUMNS)
    if unknown:
        raise ValueError(f"unknown topic filters: {sorted(unknown)}")
    where = " AND ".join(f"{k} = ?" for k in filters)
    sql = f"SELECT {', '.join(LIST_COLUMNS)} FROM topic"
    if where:
        sql += f" WHERE {where}"
    sql += " ORDER BY id"
    conn = db.connect()
    try:
        return conn.execute(sql, list(filters.values())).fetchall()
    finally:
        conn.close()
