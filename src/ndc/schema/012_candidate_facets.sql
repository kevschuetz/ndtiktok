-- 012 (plan 02-11): which search facet(s) surfaced a candidate (JSON list).
ALTER TABLE source_candidate ADD COLUMN facets_json TEXT NOT NULL DEFAULT '[]';
