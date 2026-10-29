# RAWBerry database

`init/01_extensions.sql` enables pgvector; `init/02_schema.sql` creates the base
document, chunk, embedding, conversation, and citation tables.

Apply `migrations/001_api_persistence.sql` after the base schema to enable API
document ingestion, original-byte storage, public UUIDs, and user preferences.
The migration preserves existing integer IDs and adds sequences for new documents
and chunks. Application startup never changes the schema.

Apply `migrations/002_user_scoping_conversations.sql` next for consistent string
user IDs, quarantined legacy ownership, and persistent conversation turns.

Apply `migrations/003_vector_embeddings.sql` after migration 002 for generated
embedding IDs and the persisted vector-search path. It preserves existing vectors
and relationships; the API never applies this migration automatically. App startup
requires migration 005 in PostgreSQL mode (see below). Existing unembedded chunks remain stored
but require their source TXT file to be uploaded again before semantic search can
find them. Existing incompatible model/dimension vectors are excluded from retrieval.

For a new database with pgvector installed, run these files in order from the
repository root after configuring `DATABASE_URL`:

```powershell
psql "$env:DATABASE_URL" -v ON_ERROR_STOP=1 -f rawberry-db/init/01_extensions.sql
psql "$env:DATABASE_URL" -v ON_ERROR_STOP=1 -f rawberry-db/init/02_schema.sql
psql "$env:DATABASE_URL" -v ON_ERROR_STOP=1 -f rawberry-db/migrations/001_api_persistence.sql
psql "$env:DATABASE_URL" -v ON_ERROR_STOP=1 -f rawberry-db/migrations/002_user_scoping_conversations.sql
psql "$env:DATABASE_URL" -v ON_ERROR_STOP=1 -f rawberry-db/migrations/003_vector_embeddings.sql
```

For an existing database, apply only missing migrations in order. Migration 002
preserves legacy ownership separately and leaves old records inaccessible until
their owner is explicitly mapped to a verified upstream user ID. Back up shared
data and coordinate migration execution with the database team. Do not run the
old adapter after migration 002; no automatic down migration is supplied.

Apply `migrations/004_conversation_retention.sql` after 003 to index public
conversations by last activity for the 24-hour inactivity policy. This migration
does not delete data. Retention filtering works with migration 003, so the index
can be rolled out before or after the application; migration 004 is recommended
before scheduling cleanup:

```powershell
psql "$env:DATABASE_URL" -v ON_ERROR_STOP=1 -f rawberry-db/migrations/004_conversation_retention.sql
```

The API hides expired conversations immediately. Physical deletion requires a
scheduled `python -m app.cleanup_conversations` invocation from `rawberry-api`.
See the API README for batching, generation protection, and deployment details.

Apply `migrations/005_conversation_descriptions.sql` after 004 before deploying the
description-enabled API. It adds nullable `chat_session.description`, limited to
300 characters. Existing conversations remain null until their next successful
exchange. The application requires migration 005 at startup; apply migrations
before rolling out this version. Older API versions can continue to use the schema.

```powershell
psql "$env:DATABASE_URL" -v ON_ERROR_STOP=1 -f rawberry-db/migrations/005_conversation_descriptions.sql
```

To run database integration tests, set `TEST_DATABASE_URL` to a disposable pgvector
database and run `python -m pytest tests rawberry-api/tests` from the repository
root. Tests create/drop isolated schemas and need extension/schema privileges.
Without that setting, database integration tests are skipped. Tests use deterministic
768-dimensional fake embeddings and never call Vertex AI. The shared Cloud SQL
instance must not be used as `TEST_DATABASE_URL`.

See the [API README](../rawberry-api/README.md) for current behavior and limitations.
