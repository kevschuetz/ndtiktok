-- 002_checks: hash-bound overrides for warn-tier checker findings (D-12, plan 01-02).
-- Block-tier rules are never overridable; record_override refuses them before insert.
CREATE TABLE IF NOT EXISTS check_override (
  id INTEGER PRIMARY KEY,
  text_sha256 TEXT NOT NULL,
  rule_id TEXT NOT NULL,
  level TEXT NOT NULL,
  reason TEXT NOT NULL CHECK (length(trim(reason)) >= 5),
  terminology_version INTEGER NOT NULL,
  created_at TEXT NOT NULL,
  UNIQUE (text_sha256, rule_id)
);
