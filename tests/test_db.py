import os

from ndc.db import Database


def test_migrations_apply_once_and_wal(tmp_path):
    path = os.environ["NDC_DB"]
    Database(path).connect().close()
    conn = Database(path).connect()
    try:
        rows = conn.execute(
            "SELECT filename FROM schema_migrations WHERE filename = ?", ("001_core.sql",)
        ).fetchall()
        assert len(rows) == 1
        assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        tables = {
            r[0]
            for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
        assert {"topic", "llm_run", "schema_migrations"} <= tables
    finally:
        conn.close()
