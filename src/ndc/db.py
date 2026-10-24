"""Sole DDL owner: applies src/ndc/schema/NNN_*.sql in order, tracked in schema_migrations."""

import re
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

SCHEMA_DIR = Path(__file__).resolve().parent / "schema"
_MIGRATION_RE = re.compile(r"^\d{3}_.+\.sql$")
_TRACKING_SQL = SCHEMA_DIR / "_tracking.sql"


def migration_files() -> list[Path]:
    return sorted(p for p in SCHEMA_DIR.iterdir() if _MIGRATION_RE.match(p.name))


class Database:
    def __init__(self, path: str | Path):
        self.path = str(path)

    def connect(self) -> sqlite3.Connection:
        parent = Path(self.path).parent
        parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        self._migrate(conn)
        return conn

    def _migrate(self, conn: sqlite3.Connection) -> None:
        for stmt in _split_statements(_TRACKING_SQL.read_text(encoding="utf-8")):
            conn.execute(stmt)
        applied = {r[0] for r in conn.execute("SELECT filename FROM schema_migrations")}
        for path in migration_files():
            if path.name in applied:
                continue
            sql = path.read_text(encoding="utf-8")
            try:
                conn.execute("BEGIN")
                for stmt in _split_statements(sql):
                    conn.execute(stmt)
                conn.execute(
                    "INSERT INTO schema_migrations (filename, applied_at) VALUES (?, ?)",
                    (path.name, datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")),
                )
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise

    def applied_migrations(self) -> list[str]:
        conn = self.connect()
        try:
            return [
                r[0]
                for r in conn.execute("SELECT filename FROM schema_migrations ORDER BY filename")
            ]
        finally:
            conn.close()


def _split_statements(sql: str) -> list[str]:
    """Split a migration file into complete statements (executescript would auto-commit)."""
    out, buf = [], ""
    for line in sql.splitlines(keepends=True):
        buf += line
        if sqlite3.complete_statement(buf):
            if buf.strip():
                out.append(buf.strip())
            buf = ""
    if buf.strip():
        out.append(buf.strip())
    return out
