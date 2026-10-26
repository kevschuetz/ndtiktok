-- 009 review (plans 02-03/02-04): per-sentence verdicts and hash-bound human review (append-only).
CREATE TABLE IF NOT EXISTS claim_verdict (
  id INTEGER PRIMARY KEY,
  script_sentence_id INTEGER NOT NULL UNIQUE REFERENCES script_sentence(id),
  llm_run_id INTEGER REFERENCES llm_run(id),
  verdict TEXT NOT NULL CHECK (verdict IN
    ('supports', 'partial', 'overstated', 'unsupported', 'contradicts', 'not_applicable')),
  kind TEXT NOT NULL CHECK (kind IN ('empirical', 'hedged_generalization', 'advice', 'framing')),
  certainty_escalation INTEGER NOT NULL,
  hidden_claim INTEGER NOT NULL,
  forced_reason TEXT,
  model_verdict TEXT NOT NULL,
  note_de TEXT NOT NULL,
  suggested_fix_de TEXT,
  reuse_key TEXT NOT NULL,
  reused_from_id INTEGER REFERENCES claim_verdict(id),
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE IF NOT EXISTS review (
  id INTEGER PRIMARY KEY,
  script_sha256 TEXT NOT NULL,
  decision TEXT NOT NULL CHECK (decision IN ('approved', 'rejected', 'changes_requested')),
  reviewer TEXT NOT NULL,
  channel TEXT NOT NULL CHECK (channel IN ('cli', 'web', 'telegram')),
  note TEXT,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);
CREATE INDEX IF NOT EXISTS ix_review_sha ON review (script_sha256, id);

CREATE TABLE IF NOT EXISTS claim_ack (
  id INTEGER PRIMARY KEY,
  script_sha256 TEXT NOT NULL,
  sentence_ordinal INTEGER NOT NULL,
  reviewer TEXT NOT NULL,
  channel TEXT NOT NULL CHECK (channel IN ('cli', 'web', 'telegram')),
  note TEXT,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
  UNIQUE (script_sha256, sentence_ordinal)
);

CREATE TRIGGER IF NOT EXISTS claim_verdict_no_update BEFORE UPDATE ON claim_verdict
BEGIN SELECT RAISE(ABORT, 'claim_verdict is immutable'); END;
CREATE TRIGGER IF NOT EXISTS claim_verdict_no_delete BEFORE DELETE ON claim_verdict
BEGIN SELECT RAISE(ABORT, 'claim_verdict is immutable'); END;
CREATE TRIGGER IF NOT EXISTS review_no_update BEFORE UPDATE ON review
BEGIN SELECT RAISE(ABORT, 'review is append-only'); END;
CREATE TRIGGER IF NOT EXISTS review_no_delete BEFORE DELETE ON review
BEGIN SELECT RAISE(ABORT, 'review is append-only'); END;
CREATE TRIGGER IF NOT EXISTS claim_ack_no_update BEFORE UPDATE ON claim_ack
BEGIN SELECT RAISE(ABORT, 'claim_ack is append-only'); END;
CREATE TRIGGER IF NOT EXISTS claim_ack_no_delete BEFORE DELETE ON claim_ack
BEGIN SELECT RAISE(ABORT, 'claim_ack is append-only'); END;
