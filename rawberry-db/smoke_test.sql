-- Rawberry schema smoke test
-- Run: psql -d rawberry -f smoke_test.sql
-- Everything runs inside one transaction and is ROLLED BACK at the end,
-- so no test data is left behind. Test rows use ids in the 900000 range.

\set ON_ERROR_STOP on
BEGIN;w

\echo '--- 1. Lookup tables ---'
INSERT INTO status (id, status) VALUES (900001, 'smoke_test_processed');
INSERT INTO role (id, name) VALUES (900001, 'smoke_user'), (900002, 'smoke_assistant');

\echo '--- 2. Document + author ---'
INSERT INTO author (id, name) VALUES (900001, 'Test Author');
INSERT INTO document (id, user_id, title, status_id, created_at)
VALUES (900001, 1, 'Smoke Test Doc', 900001, CURRENT_DATE);
INSERT INTO document_author (id, document_id, author_id) VALUES (900001, 900001, 900001);

\echo '--- 3. Chunks + embeddings ---'
INSERT INTO chunk (id, doc_id, chunk_index, content, created_at) VALUES
    (900001, 900001, 0, 'Machine learning lets systems learn patterns from data.', CURRENT_DATE),
    (900002, 900001, 1, 'Artificial intelligence covers reasoning and language.',   CURRENT_DATE),
    (900003, 900001, 2, 'Cybersecurity protects networks from attackers.',           CURRENT_DATE);

INSERT INTO embedding (id, chunk_id, vector, model, created_at) VALUES
    (900001, 900001, '[0.1, 0.2, 0.3]', 'smoke-test', CURRENT_DATE),
    (900002, 900002, '[0.1, 0.2, 0.4]', 'smoke-test', CURRENT_DATE),
    (900003, 900003, '[0.8, 0.1, 0.1]', 'smoke-test', CURRENT_DATE);

\echo '--- 4. Retrieval: expect chunk 0, then 1, then 2 ---'
SELECT c.chunk_index,
       left(c.content, 40)                  AS content,
       round((e.vector <=> '[0.1, 0.2, 0.3]')::numeric, 4) AS cosine_distance
FROM embedding e
JOIN chunk c ON c.id = e.chunk_id
WHERE e.model = 'smoke-test'
ORDER BY e.vector <=> '[0.1, 0.2, 0.3]'
LIMIT 3;

\echo '--- 5. Chat session, messages, citation ---'
INSERT INTO chat_session (id, user_id, doc_id, title, created_at)
VALUES (900001, 1, 900001, 'Smoke chat', CURRENT_DATE);
INSERT INTO message (id, session_id, role_id, content, created_at) VALUES
    (900001, 900001, 900001, 'What is machine learning?', CURRENT_DATE),
    (900002, 900001, 900002, 'It lets systems learn patterns from data.', CURRENT_DATE);
INSERT INTO citation (id, message_id, chunk_id, retrieval_score, created_at)
VALUES (900001, 900002, 900001, 1.0, CURRENT_DATE);
INSERT INTO chat_session_access (id, user_id, session_id, is_deleted)
VALUES (900001, 1, 900001, false);

SELECT r.name AS role, left(m.content, 45) AS message, c.chunk_index AS cited_chunk, ci.retrieval_score
FROM message m
JOIN role r ON r.id = m.role_id
LEFT JOIN citation ci ON ci.message_id = m.id
LEFT JOIN chunk c ON c.id = ci.chunk_id
WHERE m.session_id = 900001
ORDER BY m.id;

\echo '--- 6. Constraint checks ---'
DO $$
BEGIN
    INSERT INTO embedding (id, chunk_id, vector, model, created_at)
    VALUES (900098, 999999999, '[1,1,1]', 'smoke-test', CURRENT_DATE);
    RAISE EXCEPTION 'FAIL: embedding for a missing chunk was accepted';
EXCEPTION WHEN foreign_key_violation THEN
    RAISE NOTICE 'OK: embedding for a missing chunk rejected (FK works)';
END $$;

DO $$
BEGIN
    INSERT INTO embedding (id, chunk_id, vector, model, created_at)
    VALUES (900099, 900001, '[0.5,0.5,0.5]', 'smoke-test', CURRENT_DATE);
    RAISE EXCEPTION 'FAIL: duplicate (chunk_id, model) was accepted';
EXCEPTION WHEN unique_violation THEN
    RAISE NOTICE 'OK: duplicate embedding for same chunk+model rejected';
END $$;

DO $$
BEGIN
    INSERT INTO embedding (id, chunk_id, vector, model, created_at)
    VALUES (900100, 900002, '[0.5, 0.5]', 'other-model', CURRENT_DATE);
    RAISE NOTICE 'WARNING: a 2-dim vector was accepted next to 3-dim ones. '
                 'Consider vector(N) to enforce one dimension.';
EXCEPTION WHEN others THEN
    RAISE NOTICE 'OK: mismatched vector dimension rejected';
END $$;

\echo '--- All checks ran. Rolling back test data. ---'
ROLLBACK;