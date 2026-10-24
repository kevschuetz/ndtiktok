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

-- The competitor sheet (MKT-01, D-05): one row per fetched account, every field with provenance.
-- Field priority: operator_verified > operator_entered > llm_session/auto > scraped, then newest.
-- Fields filled by later plans (score levels, face, voice, format, pillars, audiences,
-- monetization, needs_operator_check) come out NULL until observed.
-- Field-obs names: source_citing_score (final/operator), source_text_level, source_video_level.
CREATE VIEW IF NOT EXISTS v_competitor_sheet AS
WITH ranked AS (
  SELECT account_id, field, value, provenance,
    ROW_NUMBER() OVER (
      PARTITION BY account_id, field
      ORDER BY CASE provenance
                 WHEN 'operator_verified' THEN 1
                 WHEN 'operator_entered' THEN 2
                 WHEN 'llm_session' THEN 3
                 WHEN 'auto' THEN 3
                 ELSE 4 END,
               observed_at DESC, id DESC) AS rn
  FROM competitor_field_obs
  WHERE value IS NOT NULL
),
best AS (SELECT account_id, field, value, provenance FROM ranked WHERE rn = 1),
win AS (
  SELECT account_id,
    SUM(CASE WHEN saves IS NOT NULL AND views > 0 THEN saves END) AS saves_sum,
    SUM(CASE WHEN saves IS NOT NULL AND views > 0 THEN views END) AS saves_views,
    SUM(CASE WHEN shares IS NOT NULL AND views > 0 THEN shares END) AS shares_sum,
    SUM(CASE WHEN shares IS NOT NULL AND views > 0 THEN views END) AS shares_views,
    COUNT(posted_at) AS n_dated,
    MIN(posted_at) AS first_ts,
    MAX(posted_at) AS last_ts
  FROM competitor_post
  WHERE in_reach_window = 1
  GROUP BY account_id
)
SELECT
  a.id AS account_id,
  a.handle,
  a.platform,
  a.language,
  a.followers,
  fo.provenance AS followers_provenance,
  a.tier,
  a.reach_median AS median_views_15,
  a.n_reach_posts,
  rm.provenance AS median_views_provenance,
  CASE
    WHEN sc.provenance IN ('operator_verified', 'operator_entered') THEN CAST(sc.value AS INTEGER)
    WHEN tl.value IS NOT NULL OR vl.value IS NOT NULL THEN
      MAX(COALESCE(CAST(tl.value AS INTEGER), -1), COALESCE(CAST(vl.value AS INTEGER), -1))
    ELSE CAST(sc.value AS INTEGER)
  END AS source_citing_score,
  CASE
    WHEN sc.provenance IN ('operator_verified', 'operator_entered') THEN sc.provenance
    WHEN tl.value IS NOT NULL OR vl.value IS NOT NULL THEN
      CASE WHEN COALESCE(CAST(vl.value AS INTEGER), -1) > COALESCE(CAST(tl.value AS INTEGER), -1)
           THEN vl.provenance ELSE tl.provenance END
    ELSE sc.provenance
  END AS source_citing_provenance,
  tl.value AS source_text_level,
  vl.value AS source_video_level,
  fa.value AS face,
  fa.provenance AS face_provenance,
  vg.value AS voice_gender,
  vg.provenance AS voice_gender_provenance,
  fm.value AS format,
  fm.provenance AS format_provenance,
  CASE WHEN w.n_dated >= 2 AND w.last_ts > w.first_ts
       THEN ROUND((w.n_dated - 1) * 7.0 * 86400 / (w.last_ts - w.first_ts), 2) END
    AS cadence_posts_per_week,
  pl.value AS pillars,
  au.value AS audiences,
  mo.value AS monetization_signals,
  mo.provenance AS monetization_provenance,
  CASE WHEN w.saves_views > 0 THEN ROUND(1000.0 * w.saves_sum / w.saves_views, 2) END
    AS saves_per_1k,
  CASE WHEN w.shares_views > 0 THEN ROUND(1000.0 * w.shares_sum / w.shares_views, 2) END
    AS shares_per_1k,
  nc.value AS needs_operator_check,
  a.bio,
  a.bio_link,
  a.fetch_status,
  a.posts_fetch_status,
  a.captured_at,
  COALESCE(c.seed_named, 0) AS seed_named,
  c.discovery_source,
  c.status
FROM competitor_account a
LEFT JOIN competitor_candidate c ON c.handle = a.handle AND c.platform = a.platform
LEFT JOIN win w ON w.account_id = a.id
LEFT JOIN best fo ON fo.account_id = a.id AND fo.field = 'followers'
LEFT JOIN best rm ON rm.account_id = a.id AND rm.field = 'reach_median'
LEFT JOIN best sc ON sc.account_id = a.id AND sc.field = 'source_citing_score'
LEFT JOIN best tl ON tl.account_id = a.id AND tl.field = 'source_text_level'
LEFT JOIN best vl ON vl.account_id = a.id AND vl.field = 'source_video_level'
LEFT JOIN best fa ON fa.account_id = a.id AND fa.field = 'face'
LEFT JOIN best vg ON vg.account_id = a.id AND vg.field = 'voice_gender'
LEFT JOIN best fm ON fm.account_id = a.id AND fm.field = 'format'
LEFT JOIN best pl ON pl.account_id = a.id AND pl.field = 'pillars'
LEFT JOIN best au ON au.account_id = a.id AND au.field = 'audiences'
LEFT JOIN best mo ON mo.account_id = a.id AND mo.field = 'monetization_signals'
LEFT JOIN best nc ON nc.account_id = a.id AND nc.field = 'needs_operator_check';
