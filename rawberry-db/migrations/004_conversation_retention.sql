-- Apply after 003_vector_embeddings.sql. No existing conversations are deleted.
BEGIN;
SELECT pg_advisory_xact_lock(4398, 1);
CREATE INDEX IF NOT EXISTS idx_chat_session_retention
    ON chat_session(updated_ts, id) WHERE public_id IS NOT NULL;
INSERT INTO schema_migration(version) VALUES ('004_conversation_retention') ON CONFLICT DO NOTHING;
COMMIT;
