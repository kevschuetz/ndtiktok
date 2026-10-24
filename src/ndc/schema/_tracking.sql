-- Bootstrap table for the migration runner (not itself a numbered migration).
CREATE TABLE IF NOT EXISTS schema_migrations (
  filename TEXT PRIMARY KEY,
  applied_at TEXT NOT NULL
);
