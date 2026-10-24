-- 003_decision: pre-registered language decision (MKT-02, D-20, plan 01-03).
-- scan_run.rule_sha256 records the rule hash each scan stage ran under; the first row is the
-- reference that `ndc scan decide` compares against. Changes need a logged rule_amendment.
CREATE TABLE IF NOT EXISTS scan_run (
  id INTEGER PRIMARY KEY,
  stage TEXT NOT NULL,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  rule_sha256 TEXT NOT NULL,
  notes TEXT
);

CREATE TABLE IF NOT EXISTS rule_amendment (
  id INTEGER PRIMARY KEY,
  old_sha256 TEXT NOT NULL,
  new_sha256 TEXT NOT NULL,
  reason TEXT NOT NULL CHECK (length(trim(reason)) >= 5),
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS language_decision (
  id INTEGER PRIMARY KEY,
  verdict TEXT NOT NULL CHECK (verdict IN ('de', 'en')),
  matched_row TEXT NOT NULL,
  inconclusive INTEGER NOT NULL,
  metrics_json TEXT NOT NULL,
  rule_sha256 TEXT NOT NULL,
  decided_at TEXT NOT NULL
);
