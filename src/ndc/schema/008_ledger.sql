-- 008 ledger (plan 02-01): evidence ledger for the grounded script pipeline.
-- source -> source_snapshot (immutable, sha256) -> source_sentence (the citation unit);
-- topic_pick -> corpus/corpus_source (locked set a draft may cite); script -> script_version
-- (immutable, sha256) -> script_sentence -> script_citation. Edits create new versions (D-16).

CREATE TABLE IF NOT EXISTS source (
  id INTEGER PRIMARY KEY,
  kind TEXT NOT NULL CHECK (kind IN ('pubmed', 'awmf')),
  pmid TEXT UNIQUE,
  pmcid TEXT,
  doi TEXT UNIQUE,
  awmf_reg_no TEXT,
  awmf_version TEXT,
  awmf_valid_until TEXT,
  awmf_status TEXT CHECK (awmf_status IS NULL OR awmf_status IN
    ('gueltig', 'in_ueberarbeitung', 'abgelaufen')),
  title TEXT NOT NULL,
  authors_json TEXT NOT NULL DEFAULT '[]',
  year INTEGER,
  journal TEXT,
  pubtypes_json TEXT NOT NULL DEFAULT '[]',
  language TEXT,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
  UNIQUE (awmf_reg_no, awmf_version)
);

CREATE TABLE IF NOT EXISTS source_snapshot (
  id INTEGER PRIMARY KEY,
  source_id INTEGER NOT NULL REFERENCES source(id),
  sha256 TEXT NOT NULL UNIQUE,
  origin TEXT NOT NULL CHECK (origin IN ('pubmed_abstract', 'epmc_fulltext', 'awmf_pdf')),
  retrieved_at TEXT NOT NULL,
  raw_artifact_sha256 TEXT,
  n_sentences INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS source_sentence (
  id INTEGER PRIMARY KEY,
  snapshot_id INTEGER NOT NULL REFERENCES source_snapshot(id),
  ordinal INTEGER NOT NULL,
  section TEXT,
  page INTEGER,
  text TEXT NOT NULL,
  UNIQUE (snapshot_id, ordinal)
);

CREATE TABLE IF NOT EXISTS topic_pick (
  topic_id INTEGER NOT NULL REFERENCES topic(id),
  snapshot_id INTEGER NOT NULL REFERENCES source_snapshot(id),
  picked_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
  UNIQUE (topic_id, snapshot_id)
);

CREATE TABLE IF NOT EXISTS corpus (
  id INTEGER PRIMARY KEY,
  topic_id INTEGER NOT NULL REFERENCES topic(id),
  sha256 TEXT NOT NULL,
  locked_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
  UNIQUE (topic_id, sha256)
);

CREATE TABLE IF NOT EXISTS corpus_source (
  corpus_id INTEGER NOT NULL REFERENCES corpus(id),
  position INTEGER NOT NULL,
  snapshot_id INTEGER NOT NULL REFERENCES source_snapshot(id),
  short_cite TEXT NOT NULL,
  UNIQUE (corpus_id, position)
);

CREATE TABLE IF NOT EXISTS script (
  id INTEGER PRIMARY KEY,
  topic_id INTEGER NOT NULL REFERENCES topic(id),
  corpus_id INTEGER NOT NULL REFERENCES corpus(id),
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE IF NOT EXISTS script_version (
  id INTEGER PRIMARY KEY,
  script_id INTEGER NOT NULL REFERENCES script(id),
  parent_version_id INTEGER REFERENCES script_version(id),
  version_no INTEGER NOT NULL,
  text TEXT NOT NULL,
  sha256 TEXT NOT NULL UNIQUE,
  word_count INTEGER NOT NULL,
  origin TEXT NOT NULL CHECK (origin IN ('draft', 'edit')),
  llm_run_id INTEGER REFERENCES llm_run(id),
  check_status TEXT NOT NULL CHECK (check_status IN ('ok', 'needs_override', 'blocked')),
  check_json TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
  UNIQUE (script_id, version_no)
);

CREATE TABLE IF NOT EXISTS script_sentence (
  id INTEGER PRIMARY KEY,
  script_version_id INTEGER NOT NULL REFERENCES script_version(id),
  ordinal INTEGER NOT NULL,
  text TEXT NOT NULL,
  char_start INTEGER NOT NULL,
  char_end INTEGER NOT NULL,
  sha256 TEXT NOT NULL,
  UNIQUE (script_version_id, ordinal)
);

CREATE TABLE IF NOT EXISTS script_citation (
  script_sentence_id INTEGER NOT NULL REFERENCES script_sentence(id),
  source_sentence_id INTEGER NOT NULL REFERENCES source_sentence(id),
  UNIQUE (script_sentence_id, source_sentence_id)
);

CREATE INDEX IF NOT EXISTS ix_source_sentence_snapshot ON source_sentence (snapshot_id, ordinal);
CREATE INDEX IF NOT EXISTS ix_script_version_script ON script_version (script_id, version_no);

-- Immutability (T-02-01): ledger rows are append-only.
CREATE TRIGGER IF NOT EXISTS source_snapshot_no_update BEFORE UPDATE ON source_snapshot
BEGIN SELECT RAISE(ABORT, 'source_snapshot is immutable'); END;
CREATE TRIGGER IF NOT EXISTS source_snapshot_no_delete BEFORE DELETE ON source_snapshot
BEGIN SELECT RAISE(ABORT, 'source_snapshot is immutable'); END;
CREATE TRIGGER IF NOT EXISTS source_sentence_no_update BEFORE UPDATE ON source_sentence
BEGIN SELECT RAISE(ABORT, 'source_sentence is immutable'); END;
CREATE TRIGGER IF NOT EXISTS source_sentence_no_delete BEFORE DELETE ON source_sentence
BEGIN SELECT RAISE(ABORT, 'source_sentence is immutable'); END;
CREATE TRIGGER IF NOT EXISTS script_version_no_update BEFORE UPDATE ON script_version
BEGIN SELECT RAISE(ABORT, 'script_version is immutable'); END;
CREATE TRIGGER IF NOT EXISTS script_version_no_delete BEFORE DELETE ON script_version
BEGIN SELECT RAISE(ABORT, 'script_version is immutable'); END;
CREATE TRIGGER IF NOT EXISTS script_sentence_no_update BEFORE UPDATE ON script_sentence
BEGIN SELECT RAISE(ABORT, 'script_sentence is immutable'); END;
CREATE TRIGGER IF NOT EXISTS script_sentence_no_delete BEFORE DELETE ON script_sentence
BEGIN SELECT RAISE(ABORT, 'script_sentence is immutable'); END;
CREATE TRIGGER IF NOT EXISTS script_citation_no_update BEFORE UPDATE ON script_citation
BEGIN SELECT RAISE(ABORT, 'script_citation is immutable'); END;
CREATE TRIGGER IF NOT EXISTS script_citation_no_delete BEFORE DELETE ON script_citation
BEGIN SELECT RAISE(ABORT, 'script_citation is immutable'); END;
CREATE TRIGGER IF NOT EXISTS corpus_source_no_update BEFORE UPDATE ON corpus_source
BEGIN SELECT RAISE(ABORT, 'corpus_source is immutable'); END;
CREATE TRIGGER IF NOT EXISTS corpus_source_no_delete BEFORE DELETE ON corpus_source
BEGIN SELECT RAISE(ABORT, 'corpus_source is immutable'); END;

-- llm_run (001_core) extension for SCR-06 call logging.
ALTER TABLE llm_run ADD COLUMN prompt_sha256 TEXT;
ALTER TABLE llm_run ADD COLUMN input_sha256s_json TEXT;
ALTER TABLE llm_run ADD COLUMN request_artifact_path TEXT;
ALTER TABLE llm_run ADD COLUMN cache_read_tokens INTEGER;
ALTER TABLE llm_run ADD COLUMN cache_write_tokens INTEGER;
ALTER TABLE llm_run ADD COLUMN thinking_tokens INTEGER;
ALTER TABLE llm_run ADD COLUMN stop_reason TEXT;
ALTER TABLE llm_run ADD COLUMN request_id TEXT;
ALTER TABLE llm_run ADD COLUMN subject_kind TEXT;
ALTER TABLE llm_run ADD COLUMN subject_id INTEGER;
