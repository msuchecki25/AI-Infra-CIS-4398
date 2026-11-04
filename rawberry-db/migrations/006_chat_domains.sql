-- Apply after 005_conversation_descriptions.sql.
BEGIN;
SELECT pg_advisory_xact_lock(4398, 1);
-- Existing conversations become education chats; existing personal documents remain
-- stored but are no longer retrieved. Re-ingest curated sources into each corpus.
ALTER TABLE chat_session ADD COLUMN IF NOT EXISTS domain TEXT NOT NULL DEFAULT 'education'
    CHECK (domain IN ('medical', 'education'));
INSERT INTO schema_migration(version) VALUES ('006_chat_domains') ON CONFLICT DO NOTHING;
COMMIT;
