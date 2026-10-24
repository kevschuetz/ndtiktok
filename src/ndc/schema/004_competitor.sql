-- 004_competitor: competitor scan tables (MKT-01, plan 01-04). TikTok and YouTube Shorts only (D-03).
-- Every value keeps its provenance in competitor_field_obs (D-01).
CREATE TABLE IF NOT EXISTS competitor_candidate (
  id INTEGER PRIMARY KEY,
  handle TEXT NOT NULL,
  platform TEXT NOT NULL CHECK (platform IN ('tiktok', 'youtube')),
  language TEXT NOT NULL CHECK (language IN ('de', 'en')),
  discovery_source TEXT,
  query TEXT,
  seed_named INTEGER NOT NULL DEFAULT 0,
  operator_decision TEXT CHECK (operator_decision IN ('include', 'exclude')),
  notes TEXT,
  status TEXT NOT NULL DEFAULT 'candidate' CHECK (status IN ('candidate', 'selected', 'excluded')),
  created_at TEXT NOT NULL,
  UNIQUE (handle, platform)
);

CREATE TABLE IF NOT EXISTS competitor_account (
  id INTEGER PRIMARY KEY,
  candidate_id INTEGER REFERENCES competitor_candidate(id),
  handle TEXT NOT NULL,
  platform TEXT NOT NULL CHECK (platform IN ('tiktok', 'youtube')),
  language TEXT NOT NULL CHECK (language IN ('de', 'en')),
  followers INTEGER,
  tier TEXT,
  video_count INTEGER,
  bio TEXT,
  bio_link TEXT,
  channel_id TEXT,
  fetch_status TEXT,
  fetch_error TEXT,
  attempted_at TEXT,
  captured_at TEXT,
  posts_fetch_status TEXT,
  posts_captured_at TEXT,
  reach_median REAL,
  n_reach_posts INTEGER NOT NULL DEFAULT 0,
  UNIQUE (handle, platform)
);

CREATE TABLE IF NOT EXISTS competitor_post (
  id INTEGER PRIMARY KEY,
  account_id INTEGER NOT NULL REFERENCES competitor_account(id),
  post_id TEXT NOT NULL,
  posted_at INTEGER,
  views INTEGER,
  likes INTEGER,
  comments INTEGER,
  shares INTEGER,
  saves INTEGER,
  duration_s REAL,
  description TEXT,
  pinned_comment TEXT,
  pinned INTEGER NOT NULL DEFAULT 0,
  in_reach_window INTEGER NOT NULL DEFAULT 0,
  provenance TEXT NOT NULL DEFAULT 'scraped',
  captured_at TEXT NOT NULL,
  UNIQUE (account_id, post_id)
);

CREATE TABLE IF NOT EXISTS competitor_field_obs (
  id INTEGER PRIMARY KEY,
  account_id INTEGER NOT NULL REFERENCES competitor_account(id),
  field TEXT NOT NULL,
  value TEXT,
  provenance TEXT NOT NULL
    CHECK (provenance IN ('scraped', 'auto', 'llm_session', 'operator_entered', 'operator_verified')),
  confidence TEXT CHECK (confidence IN ('low', 'medium', 'high')),
  method TEXT,
  scan_run_id INTEGER REFERENCES scan_run(id),
  observed_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_competitor_field_obs_account ON competitor_field_obs (account_id, field);
CREATE INDEX IF NOT EXISTS idx_competitor_post_account ON competitor_post (account_id);
