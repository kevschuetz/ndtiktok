-- 007_decision_provenance (code review HI-03): every language decision records the rule-lock
-- state it ran under, the rule_amendment logged in the same run (if any) and its input source
-- ("db:selected sample" or "csv:<path> sha256:<hex>"). Rows written before this migration keep
-- NULLs (they predate the provenance record; the 2026-10 decision ran with a valid lock).
ALTER TABLE language_decision ADD COLUMN lock_status TEXT;
ALTER TABLE language_decision ADD COLUMN amendment_id INTEGER REFERENCES rule_amendment(id);
ALTER TABLE language_decision ADD COLUMN input_source TEXT;
