-- 011 idcheck (plan 02-07): mechanical DOI/PMID verification results (append-only, latest wins).
CREATE TABLE IF NOT EXISTS id_check (
  id INTEGER PRIMARY KEY,
  source_id INTEGER NOT NULL REFERENCES source(id),
  identifier_kind TEXT NOT NULL CHECK (identifier_kind IN ('pmid', 'doi', 'awmf')),
  identifier TEXT,
  status TEXT NOT NULL CHECK (status IN ('ok', 'mismatch', 'unresolvable', 'error', 'manual')),
  fetched_title TEXT,
  fetched_year INTEGER,
  detail TEXT,
  checked_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);
CREATE INDEX IF NOT EXISTS ix_id_check_source ON id_check (source_id, id);
CREATE TRIGGER IF NOT EXISTS id_check_no_update BEFORE UPDATE ON id_check
BEGIN SELECT RAISE(ABORT, 'id_check is append-only'); END;
