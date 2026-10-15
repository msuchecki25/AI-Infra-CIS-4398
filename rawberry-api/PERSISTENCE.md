# API database integration

The API selects PostgreSQL when `DATABASE_URL` is nonempty. Without it, each
application instance gets its own temporary in-memory repository. A configured
database failure never falls back to memory. Startup checks connectivity and
migration version; request-time storage failures return a safe HTTP 503. Streaming
chat retains its existing terminal `failed` event behavior.

## Database preparation

Use a PostgreSQL database with pgvector installed on the server. From the repository
root, set `DATABASE_URL` in your shell or secret manager, then run:

```powershell
psql "$env:DATABASE_URL" -v ON_ERROR_STOP=1 -f rawberry-db/init/01_extensions.sql
psql "$env:DATABASE_URL" -v ON_ERROR_STOP=1 -f rawberry-db/init/02_schema.sql
psql "$env:DATABASE_URL" -v ON_ERROR_STOP=1 -f rawberry-db/migrations/001_api_persistence.sql
```

On an existing database that already has the base schema, run only the migration.
The migration is transactional and may be reapplied. The original base schema's
index creation statements are not repeatable. Take a backup and coordinate schema
changes with the DB/RAG team before using an existing shared database. No migration
is applied automatically by API startup.

Install requirements and start the API:

```powershell
Set-Location rawberry-api
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

Restarting the API with the same database retains uploads, ingested text, chunks,
and system prompts. Multiple API processes using that database see the same data.
Unset `DATABASE_URL` to use temporary storage. Tests can explicitly inject
`create_app(store=InMemoryStore())` regardless of environment configuration.

## Stored records and compatibility

- Uploaded documents use the existing `document` and `chunk` tables. Existing
  BIGINT primary keys and relationships remain intact; a unique public UUID maps
  API document IDs to SQL rows. New sequences start above existing IDs.
- Upload owner strings are preserved separately in `document.owner_id`. Legacy
  numeric `user_id` values remain unchanged; no user identity is invented for an
  anonymous upload. New uploads do not populate the legacy numeric owner column.
- `document_content` stores original bytes as BYTEA. This makes documents, file
  bytes, and chunks part of one transaction, including multi-file upload batches.
  PostgreSQL backup/storage requirements therefore include original files.
- `ingested_item` preserves `/ingest` text, metadata, submitted user ID, and insertion
  order. `/get` and `recent_items` keep their existing response shape. These items
  remain separate from uploaded-document chunks, matching the prior API behavior.
- `user_preference` stores prompts; an empty prompt deletes the preference.
- Existing database documents without public UUIDs remain untouched and are not
  exposed by the new API repository. A legacy-data backfill is a separate task.
- Schema SQL lives in `rawberry-db`; API services depend on the `Repository`
  protocol, and PostgreSQL queries live in `app/postgres_repository.py`.

## API behavior

- `POST /upload`: existing multipart `files` and optional string `owner_id` contract.
  Validated uploads commit together; storage failure rolls the entire batch back.
- `GET /documents`: returns a list of document metadata, including chunk counts.
- `POST /ingest` and `GET /get`: persist and retrieve plain-text items.
- `GET/PUT /users/{userid}/system-prompt`: read/update persisted preferences.
- `/chat` and `/chat/stream`: read uploaded chunks and preferences through the
  repository; generated replies and conversation history are not persisted.

TXT uploads are chunked with nullable page numbers, rather than invented pages.
PDF/DOCX bytes are retained, but extraction is still pending. Embeddings remain
pending. Retrieval preserves the prototype's keyword ranking and currently reads
all API chunks before ranking; it is suitable for the current small prototype.
Database-side semantic retrieval and vector indexing remain future RAG work.

Authentication and owner filtering have not been added. Submitted ownership IDs
are metadata, not verified authorization; listings and retrieval retain their
existing global scope. Use synthetic data until user isolation is implemented.

## Verification

From `rawberry-api`:

```powershell
python -B -m pytest tests -p no:cacheprovider
```

For real database integration tests, configure `TEST_DATABASE_URL` to a **disposable**
PostgreSQL/pgvector database and run the same command. Those tests enable the vector
extension if necessary and create/drop isolated schemas; the database role needs
appropriate privileges. They never use `DATABASE_URL` as their test target.

The tests cover application recreation, visibility across instances, original byte
retention, preferences, retrieved chat context, legacy-row migration/reapplication,
and transaction rollback after a mid-batch chunk constraint failure. Without
`TEST_DATABASE_URL`, database integration tests are explicitly skipped.
Ordinary tests clear inherited `DATABASE_URL` through an autouse fixture, so a
developer's configured application database is not used by the test suite.

To roll back application behavior, unset `DATABASE_URL` and restart (this switches
to empty temporary storage). This does not delete persisted database records.
There is no destructive down migration in this change.
