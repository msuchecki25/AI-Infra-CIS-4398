-- Apply after 004_conversation_retention.sql. Existing descriptions remain NULL.
BEGIN;
SELECT pg_advisory_xact_lock(4398, 1);
ALTER TABLE chat_session ADD COLUMN IF NOT EXISTS description TEXT
    CHECK (description IS NULL OR length(description) <= 300);
INSERT INTO schema_migration(version) VALUES ('005_conversation_descriptions') ON CONFLICT DO NOTHING;
COMMIT;
