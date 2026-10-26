-- 010 candidates (plan 02-05): cached search runs and ranked candidates (append-only).
CREATE TABLE IF NOT EXISTS search_run (
  id INTEGER PRIMARY KEY,
  topic_id INTEGER NOT NULL REFERENCES topic(id),
  query TEXT NOT NULL,
  raw_artifacts_json TEXT NOT NULL DEFAULT '[]',
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE IF NOT EXISTS source_candidate (
  id INTEGER PRIMARY KEY,
  search_run_id INTEGER NOT NULL REFERENCES search_run(id),
  rank INTEGER NOT NULL,
  score REAL NOT NULL,
  pmid TEXT,
  doi TEXT,
  pmcid TEXT,
  title TEXT NOT NULL,
  year INTEGER,
  tier TEXT,
  pubtypes_json TEXT NOT NULL DEFAULT '[]',
  is_oa INTEGER,               -- 1 yes, 0 no, NULL unknown
  safety_flag TEXT,            -- NULL ok, else check() status
  meta_json TEXT,
  UNIQUE (search_run_id, rank)
);

CREATE TRIGGER IF NOT EXISTS search_run_no_update BEFORE UPDATE ON search_run
BEGIN SELECT RAISE(ABORT, 'search_run is immutable'); END;
CREATE TRIGGER IF NOT EXISTS source_candidate_no_update BEFORE UPDATE ON source_candidate
BEGIN SELECT RAISE(ABORT, 'source_candidate is immutable'); END;
