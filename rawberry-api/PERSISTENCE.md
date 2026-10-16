# Persistence and user ownership

With `DATABASE_URL` set, the API uses PostgreSQL. Without it, each application uses
isolated temporary memory. A configured database error never selects memory fallback.
Startup verifies connectivity and migration `002_user_scoping_conversations`.

## Setup

Use PostgreSQL with pgvector available on the server. From the repository root:

```powershell
psql "$env:DATABASE_URL" -v ON_ERROR_STOP=1 -f rawberry-db/init/01_extensions.sql
psql "$env:DATABASE_URL" -v ON_ERROR_STOP=1 -f rawberry-db/init/02_schema.sql
psql "$env:DATABASE_URL" -v ON_ERROR_STOP=1 -f rawberry-db/migrations/001_api_persistence.sql
psql "$env:DATABASE_URL" -v ON_ERROR_STOP=1 -f rawberry-db/migrations/002_user_scoping_conversations.sql
```

For an existing schema, run only migrations not already applied, in order. Base
schema index creation is not repeatable. Migration 002 may be reapplied safely.
The API never executes DDL. Back up existing databases and coordinate schema
changes with the DB/RAG team before applying them to a shared environment.

Install `rawberry-api/requirements.txt` and start `uvicorn app.main:app`. Database
credentials must be supplied through environment configuration, not committed files.

## Stored records

| Table | API use |
| --- | --- |
| `document` | Public UUID, internal BIGINT ID, string `user_id`, file metadata |
| `document_content` | Original bytes as BYTEA, linked to the document |
| `chunk` | TXT passages linked to their parent document; ownership inherited through that relationship |
| `ingested_item` | Legacy pasted text retained for compatibility; no current API reads or writes |
| `user_preference` | Prompt keyed by string `user_id` |
| `chat_session` | Owned conversation with public UUID and precise timestamps |
| `chat_turn` | Ordered user message, assistant reply, generation state, timestamps |

The history API projects user and assistant messages from `chat_turn`; the old
`message`, `role`, `citation`, and `chat_session_access` tables are preserved but
are not read or written by the new conversation implementation. This keeps each
generation outcome atomic without populating a second transcript representation.
Future citation integration must explicitly reconcile that legacy schema.

All repository data operations require a user ID. PostgreSQL filters ownership
before returning content; chunks are scoped through the parent document. `/upload`
is the only source-content entry point; `/ingest`, `/get`, and `recent_items` have
been removed. Existing `ingested_item` data is retained but never used for RAG. There is
no unscoped listing or retrieval method in the repository protocol. This is application
scoping, not database row-level security. Original file bytes, metadata, and chunks
commit together for an upload batch. PostgreSQL backups must include original bytes.

Conversation reservation uses a row lock on the owned `chat_session`. A unique
partial index permits only one pending turn per session. Generation happens outside
the database transaction, so other sessions remain available. Completion updates the
same pending turn; stale completion is rejected. Five-minute abandoned-turn recovery
runs on the next request. Provider/storage errors do not expose connection details.

## Legacy ownership migration

Migration 002 deliberately does not guess identities from old numeric IDs or upload
owner strings:

- Numeric `user_id` columns on documents, ingested items, and sessions become
  `legacy_user_id`; new nullable string `user_id` columns start empty on existing rows.
- Old document `owner_id` values remain available for explicit mapping.
- Existing preferences move to `legacy_user_preference`; the new preference table
  starts empty.
- Existing records are retained but invisible to owner-filtered API reads until an
  operator assigns a verified upstream `user_id` using a reviewed mapping.
- Documents/sessions also need public UUIDs to be exposed by API listing queries.
- Map a document's ownership on its parent row; chunk ownership follows it. Resolve
  conflicting legacy identifiers before exposing any row. Do not bulk-assign legacy
  rows to a default user or treat numeric/text resemblance as verified identity.

New API writes always supply nonempty user IDs. Nullable database ownership is retained
only to quarantine legacy records; no anonymous API path exposes those records.
Migration 002 changes the old application's schema contract. Do not roll back to the
old PostgreSQL adapter after applying it. Rollback requires a coordinated schema/data
plan; no destructive down migration is supplied. Unsetting `DATABASE_URL` switches
to empty temporary memory and leaves persisted records untouched.

## Verification

From `rawberry-api`:

```powershell
python -B -m pytest tests -p no:cacheprovider
```

For real database checks, set `TEST_DATABASE_URL` to a **disposable** pgvector database.
Tests enable the extension if needed and create/drop isolated schemas. They cover
migration reapplication and legacy quarantine, upload rollback, restart persistence,
user isolation, independent conversations, and abandoned generation recovery.
Without that setting, database tests are explicitly skipped; ordinary tests clear
inherited application database settings and use mock generation.

See [README.md](README.md) for request examples and the upstream authentication boundary.
