# RAWBerry database

`init/01_extensions.sql` enables pgvector; `init/02_schema.sql` creates the base
document, chunk, embedding, conversation, and citation tables.

Apply `migrations/001_api_persistence.sql` after the base schema to enable API
document ingestion, original-byte storage, public UUIDs, and user preferences.
The migration preserves existing integer IDs and adds sequences for new documents
and chunks. Application startup never changes the schema.

See [API persistence setup and tests](../rawberry-api/PERSISTENCE.md) for commands,
configuration, compatibility notes, and remaining integration limitations.
