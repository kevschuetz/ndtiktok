-- 006_analysis: judgment + local video analysis tables (MKT-01, plan 01-06, D-17, D-21).
-- Per-citation levels from in-session judgments (after the evidence substring guard), and one row
-- per analyzed video (transcript, pitch, contact sheet). Downloaded videos are never stored.
CREATE TABLE IF NOT EXISTS competitor_post_citing (
  id INTEGER PRIMARY KEY,
  account_id INTEGER NOT NULL REFERENCES competitor_account(id),
  post_id TEXT,
  video_id TEXT,
  source TEXT NOT NULL CHECK (source IN ('caption', 'pinned_comment', 'speech', 'onscreen')),
  level INTEGER NOT NULL CHECK (level BETWEEN 0 AND 3),
  claimed_level INTEGER,
  evidence TEXT,
  guard_result TEXT NOT NULL CHECK (guard_result IN ('kept', 'downgraded')),
  created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_competitor_post_citing_account ON competitor_post_citing (account_id);

CREATE TABLE IF NOT EXISTS competitor_video (
  id INTEGER PRIMARY KEY,
  account_id INTEGER NOT NULL REFERENCES competitor_account(id),
  platform_video_id TEXT NOT NULL,
  posted_at INTEGER,
  duration_s REAL,
  download_status TEXT NOT NULL CHECK (download_status IN ('ok', 'unavailable', 'skipped')),
  download_error TEXT,
  transcript TEXT,
  transcript_lang TEXT,
  pitch_hz_median REAL,
  contact_sheet_path TEXT,
  analyzed_at TEXT,
  UNIQUE (account_id, platform_video_id)
);
