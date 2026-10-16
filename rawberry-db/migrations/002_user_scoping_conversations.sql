-- Apply after 001_api_persistence.sql. No identity is inferred from legacy values.
BEGIN;
SELECT pg_advisory_xact_lock(4398, 1);
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM schema_migration WHERE version = '002_user_scoping_conversations') THEN
        ALTER TABLE document RENAME COLUMN user_id TO legacy_user_id;
        ALTER TABLE document ADD COLUMN user_id TEXT CHECK (user_id ~ '^[!-~]{1,128}$');
        ALTER TABLE ingested_item RENAME COLUMN user_id TO legacy_user_id;
        ALTER TABLE ingested_item ADD COLUMN user_id TEXT CHECK (user_id ~ '^[!-~]{1,128}$');
        -- Keep old preferences intact but inaccessible until explicitly mapped.
        ALTER TABLE user_preference RENAME TO legacy_user_preference;
        CREATE TABLE user_preference (
            user_id TEXT CONSTRAINT scoped_preference_pkey PRIMARY KEY CHECK (user_id ~ '^[!-~]{1,128}$'),
            system_prompt TEXT NOT NULL CHECK (length(system_prompt) <= 2000)
        );

        ALTER TABLE chat_session RENAME COLUMN user_id TO legacy_user_id;
        ALTER TABLE chat_session ALTER COLUMN legacy_user_id DROP NOT NULL;
        ALTER TABLE chat_session ALTER COLUMN doc_id DROP NOT NULL;
        ALTER TABLE chat_session ADD COLUMN user_id TEXT CHECK (user_id ~ '^[!-~]{1,128}$');
        ALTER TABLE chat_session ADD COLUMN public_id UUID UNIQUE;
        ALTER TABLE chat_session ADD COLUMN next_turn BIGINT NOT NULL DEFAULT 0;
        ALTER TABLE chat_session ADD COLUMN created_ts TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP;
        ALTER TABLE chat_session ADD COLUMN updated_ts TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP;
        CREATE SEQUENCE chat_session_api_id_seq OWNED BY chat_session.id;
        ALTER TABLE chat_session ALTER COLUMN id SET DEFAULT nextval('chat_session_api_id_seq');
        PERFORM setval('chat_session_api_id_seq', GREATEST(COALESCE((SELECT MAX(id) FROM chat_session), 0), 1));

        -- Each turn durably records the user message and its generation outcome.
        -- The history API projects ordered user/assistant messages from these rows.
        -- The original message/citation tables remain unchanged for legacy data.
        CREATE TABLE chat_turn (
            id UUID PRIMARY KEY,
            session_id BIGINT NOT NULL REFERENCES chat_session(id),
            ordinal BIGINT NOT NULL,
            prompt TEXT NOT NULL,
            reply TEXT,
            status TEXT NOT NULL CHECK (status IN ('pending', 'completed', 'failed')),
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMPTZ,
            UNIQUE(session_id, ordinal),
            CHECK ((status = 'completed' AND reply IS NOT NULL) OR
                   (status <> 'completed' AND reply IS NULL))
        );
        CREATE UNIQUE INDEX uq_chat_turn_pending ON chat_turn(session_id) WHERE status = 'pending';
        CREATE INDEX idx_document_user_id ON document(user_id);
        CREATE INDEX idx_ingested_item_user_id ON ingested_item(user_id, sequence_id);
        CREATE INDEX idx_chat_session_user_id_scoped ON chat_session(user_id, created_ts);
        INSERT INTO schema_migration(version) VALUES ('002_user_scoping_conversations');
    END IF;
END $$;
COMMIT;
