CREATE TABLE IF NOT EXISTS status (
    id BIGINT PRIMARY KEY NOT NULL,
    status TEXT NOT NULL,

    CONSTRAINT uq_status
        UNIQUE (status)
);

CREATE TABLE IF NOT EXISTS author (
    id BIGINT PRIMARY KEY NOT NULL,
    name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS role (
    id BIGINT PRIMARY KEY NOT NULL,
    name TEXT NOT NULL,

    CONSTRAINT uq_role_name
        UNIQUE (name)
);

CREATE TABLE IF NOT EXISTS document (
    id BIGINT PRIMARY KEY NOT NULL,
    user_id BIGINT NOT NULL,
    title TEXT NULL,
    header TEXT NULL,
    institution TEXT NULL,
    citation TEXT NULL,
    publish_date DATE NULL,
    status_id BIGINT NOT NULL,
    created_at DATE NOT NULL,
    updated_at DATE NULL,

    CONSTRAINT fk_document_status
        FOREIGN KEY (status_id)
        REFERENCES status(id)
);

CREATE TABLE IF NOT EXISTS document_author (
    id BIGINT PRIMARY KEY NOT NULL,
    document_id BIGINT NOT NULL,
    author_id BIGINT NOT NULL,

    CONSTRAINT fk_document_author_document
        FOREIGN KEY (document_id)
        REFERENCES document(id),

    CONSTRAINT fk_document_author_author
        FOREIGN KEY (author_id)
        REFERENCES author(id),

    CONSTRAINT uq_document_author
        UNIQUE (document_id, author_id)
);

CREATE TABLE IF NOT EXISTS chunk (
    id BIGINT PRIMARY KEY NOT NULL,
    doc_id BIGINT NOT NULL,
    chunk_index BIGINT NOT NULL,
    content TEXT NOT NULL,
    created_at DATE NOT NULL,

    CONSTRAINT fk_chunk_document
        FOREIGN KEY (doc_id)
        REFERENCES document(id),

    CONSTRAINT uq_chunk_index
        UNIQUE (doc_id, chunk_index)
);

CREATE TABLE IF NOT EXISTS embedding (
    id BIGINT PRIMARY KEY NOT NULL,
    chunk_id BIGINT NOT NULL,
    vector VECTOR NOT NULL,
    model TEXT NOT NULL,
    created_at DATE NOT NULL,

    CONSTRAINT fk_embedding_chunk
        FOREIGN KEY (chunk_id)
        REFERENCES chunk(id),

    CONSTRAINT uq_embedding_chunk_model
        UNIQUE (chunk_id, model)
);

CREATE TABLE IF NOT EXISTS chat_session (
    id BIGINT PRIMARY KEY NOT NULL,
    user_id BIGINT NOT NULL,
    doc_id BIGINT NOT NULL,
    title TEXT,
    created_at DATE NOT NULL,
    updated_at DATE,

    CONSTRAINT fk_chat_session_document
        FOREIGN KEY (doc_id)
        REFERENCES document(id)
);

CREATE TABLE IF NOT EXISTS message (
    id BIGINT PRIMARY KEY NOT NULL,
    session_id BIGINT NOT NULL,
    role_id BIGINT NOT NULL,
    content TEXT NOT NULL,
    created_at DATE NOT NULL,

    CONSTRAINT fk_message_session
        FOREIGN KEY (session_id)
        REFERENCES chat_session(id),

    CONSTRAINT fk_message_role
        FOREIGN KEY (role_id)
        REFERENCES role(id)
);

CREATE TABLE IF NOT EXISTS citation (
    id BIGINT PRIMARY KEY NOT NULL,
    message_id BIGINT NOT NULL,
    chunk_id BIGINT NOT NULL,
    retrieval_score DECIMAL NOT NULL,
    created_at DATE NOT NULL,

    CONSTRAINT fk_citation_message
        FOREIGN KEY (message_id)
        REFERENCES message(id),

    CONSTRAINT fk_citation_chunk
        FOREIGN KEY (chunk_id)
        REFERENCES chunk(id)
);

CREATE TABLE IF NOT EXISTS chat_session_access (
    id BIGINT PRIMARY KEY NOT NULL,
    user_id BIGINT NOT NULL,
    session_id BIGINT NOT NULL,
    is_deleted BOOL NOT NULL,

    CONSTRAINT fk_chat_session_access_session
        FOREIGN KEY (session_id)
        REFERENCES chat_session(id),

    CONSTRAINT uq_chat_session_access
        UNIQUE (user_id, session_id)
);

CREATE INDEX idx_document_status_id
ON document(status_id);

CREATE INDEX idx_document_author_document_id
ON document_author(document_id);

CREATE INDEX idx_document_author_author_id
ON document_author(author_id);

CREATE INDEX idx_chunk_doc_id
ON chunk(doc_id);

CREATE INDEX idx_embedding_chunk_id
ON embedding(chunk_id);

CREATE INDEX idx_chat_session_doc_id
ON chat_session(doc_id);

CREATE INDEX idx_chat_session_user_id
ON chat_session(user_id);

CREATE INDEX idx_message_session_id
ON message(session_id);

CREATE INDEX idx_message_role_id
ON message(role_id);

CREATE INDEX idx_citation_message_id
ON citation(message_id);

CREATE INDEX idx_citation_chunk_id
ON citation(chunk_id);

CREATE INDEX idx_chat_session_access_user_id
ON chat_session_access(user_id);

CREATE INDEX idx_chat_session_access_session_id
ON chat_session_access(session_id);