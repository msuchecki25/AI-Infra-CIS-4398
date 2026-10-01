CREATE TABLE IF NOT EXISTS chatSessions (
    id BIGSERIAL PRIMARY KEY,
    session_name varchar(255),
    created_at DEFAULT CURRENT_TIMESTAMP,
    updated_at DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS messages (
    id BIGSERIAL PRIMARY KEY,
    session_id BIGINT NOT NULL,
    role VARCHAR(20) NOT NULL,
    
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT fk_messages_session
        FOREIGN KEY (session_id)
        REFERENCES chat_sessions(id)
        ON DELETE CASCADE,

    CONSTRAINT valid_message_role
        CHECK (role IN ('user', 'assistant', 'system'))
);

CREATE TABLE IF NOT EXISTS documents (
    id BIGSERIAL PRIMARY KEY,

    filename VARCHAR(255) NOT NULL,

    file_type VARCHAR(50),

    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS document_chunks (
    id BIGSERIAL PRIMARY KEY,

    document_id BIGINT NOT NULL,

    chunk_index INTEGER NOT NULL,

    chunk_text TEXT NOT NULL,

    embedding VECTOR(768),

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_chunks_document
        FOREIGN KEY (document_id)
        REFERENCES documents(id)
        ON DELETE CASCADE
);