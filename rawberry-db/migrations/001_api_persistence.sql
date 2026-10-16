-- Apply after init/01_extensions.sql and init/02_schema.sql.
-- Additive migration: preserve existing BIGINT relationships and expose UUIDs to the API.
BEGIN;
SELECT pg_advisory_xact_lock(4398, 1);
CREATE TABLE IF NOT EXISTS schema_migration (
    version TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE SEQUENCE IF NOT EXISTS document_api_id_seq OWNED BY document.id;
ALTER TABLE document ALTER COLUMN id SET DEFAULT nextval('document_api_id_seq');
SELECT setval('document_api_id_seq', GREATEST(
    COALESCE((SELECT MAX(id) FROM document), 0),
    (SELECT last_value FROM document_api_id_seq), 1));
CREATE SEQUENCE IF NOT EXISTS chunk_api_id_seq OWNED BY chunk.id;
ALTER TABLE chunk ALTER COLUMN id SET DEFAULT nextval('chunk_api_id_seq');
SELECT setval('chunk_api_id_seq', GREATEST(
    COALESCE((SELECT MAX(id) FROM chunk), 0),
    (SELECT last_value FROM chunk_api_id_seq), 1));

-- Legacy user_id remains for existing clients. The upload contract permits arbitrary
-- string owners and anonymous uploads, so preserve that value separately.
ALTER TABLE document ALTER COLUMN user_id DROP NOT NULL;
ALTER TABLE document ADD COLUMN IF NOT EXISTS public_id UUID UNIQUE;
ALTER TABLE document ADD COLUMN IF NOT EXISTS owner_id TEXT;
ALTER TABLE document ADD COLUMN IF NOT EXISTS filename TEXT;
ALTER TABLE document ADD COLUMN IF NOT EXISTS file_type TEXT;
ALTER TABLE document ADD COLUMN IF NOT EXISTS size_bytes BIGINT;
ALTER TABLE document ADD COLUMN IF NOT EXISTS embedding_status TEXT NOT NULL DEFAULT 'pending';
ALTER TABLE document ADD COLUMN IF NOT EXISTS metadata JSONB NOT NULL DEFAULT '{}';
ALTER TABLE document ADD COLUMN IF NOT EXISTS uploaded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP;

CREATE TABLE IF NOT EXISTS document_content (
    document_id BIGINT PRIMARY KEY REFERENCES document(id) ON DELETE CASCADE,
    content BYTEA NOT NULL
);
ALTER TABLE chunk ADD COLUMN IF NOT EXISTS page_number INTEGER;
ALTER TABLE chunk ADD COLUMN IF NOT EXISTS processing_status TEXT NOT NULL DEFAULT 'pending';

CREATE TABLE IF NOT EXISTS ingested_item (
    sequence_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    public_id UUID NOT NULL UNIQUE,
    user_id BIGINT,
    content TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS user_preference (
    user_id BIGINT PRIMARY KEY,
    system_prompt TEXT NOT NULL CHECK (length(system_prompt) <= 2000)
);

-- Avoid colliding with existing integer IDs or duplicate existing status names.
LOCK TABLE status IN EXCLUSIVE MODE;
INSERT INTO status (id, status)
SELECT COALESCE(MAX(id), 0) + 1, 'uploaded' FROM status
HAVING NOT EXISTS (SELECT 1 FROM status WHERE status = 'uploaded');

INSERT INTO schema_migration(version) VALUES ('001_api_persistence') ON CONFLICT DO NOTHING;
COMMIT;
