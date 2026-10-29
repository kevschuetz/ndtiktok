-- 014 recording (Phase 3, plan 03-03): the operator's take, aligned to the approved script,
-- verified where it deviates, approved by transcript hash. Append-only like the script tables.
CREATE TABLE IF NOT EXISTS recording (
  id INTEGER PRIMARY KEY,
  script_version_id INTEGER NOT NULL REFERENCES script_version(id),
  script_sha256 TEXT NOT NULL,
  file_name TEXT NOT NULL,
  file_sha256 TEXT NOT NULL,
  duration_s REAL,
  whisper_model TEXT NOT NULL,
  language TEXT NOT NULL,
  transcript_raw TEXT NOT NULL,
  transcript_final TEXT NOT NULL,          -- approved text for matches + spoken text for deviations/extras
  transcript_sha256 TEXT NOT NULL UNIQUE,  -- what gets approved and published
  similarity_threshold REAL NOT NULL,
  n_match INTEGER NOT NULL,
  n_deviation INTEGER NOT NULL,
  n_extra INTEGER NOT NULL,
  n_missing INTEGER NOT NULL,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE IF NOT EXISTS recording_sentence (
  id INTEGER PRIMARY KEY,
  recording_id INTEGER NOT NULL REFERENCES recording(id),
  ordinal INTEGER NOT NULL,                -- position in the final transcript
  status TEXT NOT NULL CHECK (status IN ('match', 'deviation', 'extra', 'missing')),
  spoken_text TEXT,                        -- NULL for missing
  approved_ordinal INTEGER,                -- script_sentence.ordinal; NULL for extra
  approved_text TEXT,
  final_text TEXT,                         -- NULL for missing
  start_s REAL,
  end_s REAL,
  similarity REAL,
  reason TEXT,
  words_json TEXT,
  UNIQUE (recording_id, ordinal)
);

CREATE TABLE IF NOT EXISTS recording_verdict (
  id INTEGER PRIMARY KEY,
  recording_sentence_id INTEGER NOT NULL UNIQUE REFERENCES recording_sentence(id),
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
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE IF NOT EXISTS recording_review (
  id INTEGER PRIMARY KEY,
  transcript_sha256 TEXT NOT NULL,
  decision TEXT NOT NULL CHECK (decision IN ('approved', 'rejected', 'changes_requested')),
  reviewer TEXT NOT NULL,
  channel TEXT NOT NULL CHECK (channel IN ('cli', 'web', 'telegram')),
  note TEXT,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);
CREATE INDEX IF NOT EXISTS ix_recording_review_sha ON recording_review (transcript_sha256, id);

CREATE TABLE IF NOT EXISTS recording_ack (
  id INTEGER PRIMARY KEY,
  transcript_sha256 TEXT NOT NULL,
  sentence_ordinal INTEGER NOT NULL,
  reviewer TEXT NOT NULL,
  channel TEXT NOT NULL CHECK (channel IN ('cli', 'web', 'telegram')),
  note TEXT,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
  UNIQUE (transcript_sha256, sentence_ordinal)
);

CREATE TRIGGER IF NOT EXISTS recording_no_update BEFORE UPDATE ON recording
BEGIN SELECT RAISE(ABORT, 'recording is immutable'); END;
CREATE TRIGGER IF NOT EXISTS recording_no_delete BEFORE DELETE ON recording
BEGIN SELECT RAISE(ABORT, 'recording is immutable'); END;
CREATE TRIGGER IF NOT EXISTS recording_sentence_no_update BEFORE UPDATE ON recording_sentence
BEGIN SELECT RAISE(ABORT, 'recording_sentence is immutable'); END;
CREATE TRIGGER IF NOT EXISTS recording_sentence_no_delete BEFORE DELETE ON recording_sentence
BEGIN SELECT RAISE(ABORT, 'recording_sentence is immutable'); END;
CREATE TRIGGER IF NOT EXISTS recording_verdict_no_update BEFORE UPDATE ON recording_verdict
BEGIN SELECT RAISE(ABORT, 'recording_verdict is immutable'); END;
CREATE TRIGGER IF NOT EXISTS recording_verdict_no_delete BEFORE DELETE ON recording_verdict
BEGIN SELECT RAISE(ABORT, 'recording_verdict is immutable'); END;
CREATE TRIGGER IF NOT EXISTS recording_review_no_update BEFORE UPDATE ON recording_review
BEGIN SELECT RAISE(ABORT, 'recording_review is append-only'); END;
CREATE TRIGGER IF NOT EXISTS recording_review_no_delete BEFORE DELETE ON recording_review
BEGIN SELECT RAISE(ABORT, 'recording_review is append-only'); END;
CREATE TRIGGER IF NOT EXISTS recording_ack_no_update BEFORE UPDATE ON recording_ack
BEGIN SELECT RAISE(ABORT, 'recording_ack is append-only'); END;
CREATE TRIGGER IF NOT EXISTS recording_ack_no_delete BEFORE DELETE ON recording_ack
BEGIN SELECT RAISE(ABORT, 'recording_ack is append-only'); END;
