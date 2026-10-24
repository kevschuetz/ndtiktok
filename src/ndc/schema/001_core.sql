-- 001 core (plan 01-01): topic matrix + llm_run audit table (used from Phase 2).
CREATE TABLE IF NOT EXISTS topic (
  id INTEGER PRIMARY KEY,
  pillar TEXT NOT NULL,
  condition TEXT NOT NULL,
  domain TEXT NOT NULL,
  audience TEXT NOT NULL,
  angle TEXT NOT NULL,
  language TEXT,                          -- 'de'|'en'; NULL until the language decision
  working_title TEXT NOT NULL,
  summary TEXT,
  list_tag TEXT NOT NULL CHECK (list_tag IN ('whitelist', 'blacklist')),
  source_likely TEXT NOT NULL CHECK (source_likely IN ('yes', 'maybe', 'no')),
  status TEXT NOT NULL DEFAULT 'proposed'
    CHECK (status IN ('proposed', 'backlog', 'selected', 'in_production',
                      'published', 'retired', 'rejected')),
  safety_status TEXT NOT NULL DEFAULT 'ok' CHECK (safety_status IN ('ok', 'flagged', 'blocked')),
  safety_hits_json TEXT,                  -- check() findings at last evaluation
  origin TEXT NOT NULL DEFAULT 'matrix',  -- matrix|operator|trend(M2)|reddit(M2)
  decided_reason TEXT,
  decided_at TEXT,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
  UNIQUE (working_title, language)
);

CREATE INDEX IF NOT EXISTS ix_topic_dims ON topic (pillar, condition, domain, audience, angle);

CREATE TABLE IF NOT EXISTS llm_run (
  id INTEGER PRIMARY KEY,
  stage TEXT NOT NULL,
  model TEXT NOT NULL,
  request_sha256 TEXT NOT NULL,
  response_artifact_path TEXT,
  input_tokens INTEGER,
  output_tokens INTEGER,
  cost_usd REAL,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);
