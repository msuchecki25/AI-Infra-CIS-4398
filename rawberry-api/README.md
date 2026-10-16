# RAWBerry API

FastAPI backend for document ingestion, chunking, RAG retrieval, and Gemini calls.
Authentication and account management belong to the upstream application.

## Authentication boundary and user context

Every data endpoint requires one `X-User-ID` header supplied by the trusted upstream
backend or gateway. IDs are opaque, case-sensitive strings of 1-128 printable ASCII
characters without spaces. `42`, `042`, `Alice`, and `alice` are distinct users.
This provisional format must be confirmed with the upstream team before integration.

The header is **not authentication**. The upstream service must authenticate users,
strip client-supplied identity headers, set the actual user's ID, and restrict direct
access to RAWBerry. This backend does not provide login, registration, password
storage, or account sessions. Local Swagger testing lets you manually enter an ID;
that is a development convenience, not proof of identity.

RAWBerry uses this user context to scope documents, preferences,
retrieved chunks and conversations. Another user's conversation
returns the same 404 as a nonexistent conversation. Anonymous uploads and sharing
are not supported. `/` and `/health` do not require user context.

## Current implementation

- Configurable PostgreSQL persistence; isolated in-memory mode without `DATABASE_URL`.
- Multi-file uploads: PDF, DOCX, and UTF-8 TXT; 25 MiB per-file limit.
- TXT chunking and owner-filtered keyword retrieval.
- Optional Vertex AI Gemini generation, or mock responses for local development.
- Per-user response preferences.
- Independent conversations with ordered user/assistant history and generation states.
- SSE chat lifecycle events; generated tokens are not streamed individually.

PDF/DOCX text extraction, embeddings, semantic search, citations, and sharing remain
future work. Documents enter the RAG pipeline only through `/upload`; pasted-text
submission is not supported. Chat messages remain part of conversation history.

## Run locally

```powershell
Set-Location rawberry-api
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

Swagger: <http://127.0.0.1:8000/docs>. Expand an endpoint, click **Try it out**, and
enter `X-User-ID` (for example, `alice`). Use the file picker for `/upload`.

Without `DATABASE_URL`, all content and conversations disappear when the API
process restarts and are not shared across processes. See [PERSISTENCE.md](PERSISTENCE.md)
for database setup, migrations, and integration tests.

## API contract

This branch intentionally changes the prototype's user/session contract. Identity
comes only from `X-User-ID`; JSON/form/query `userid`, `user_id`, and `owner_id` are
not alternative identity sources. Request models reject extra fields; uploads reject
legacy identity form fields. The old `/users/{userid}/system-prompt` route is removed.
`data.window` and `data.agent` are removed from chat requests; specialized assistant
selection is not implemented.

| Endpoint | Behavior |
| --- | --- |
| `GET /` | Status and endpoint listing; no user header required |
| `GET /health` | Process liveness; no user header required |
| `POST /upload` | Upload multipart `files`; ownership comes from the header |
| `GET /documents` | List only the current user's uploaded document metadata |
| `GET /me/system-prompt` | Read the current user's preferences |
| `PUT /me/system-prompt` | Update preferences; empty prompt clears them |
| `POST /conversations` | Create an independent conversation |
| `GET /conversations` | List the current user's conversations |
| `GET /conversations/{conversation_id}/messages` | Read owned conversation history |
| `POST /chat` | Generate and store a turn in an owned conversation |
| `POST /chat/stream` | Same chat behavior with SSE lifecycle events |

Create a conversation with `POST /conversations`:

```json
{"title": "Research questions"}
```

Use its returned `id` as `conversation_id` in either chat endpoint:

```json
{
  "conversation_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "What does my document say?"
}
```

The response includes `conversation_id`, `turn_id`, and `reply`. Update preferences
with `{"prompt": "Keep answers concise."}`.

## Document-only RAG input

Use `POST /upload` to submit one or more document files, and `GET /documents` to
list your uploaded document metadata. TXT files produce searchable chunks now;
PDF/DOCX extraction is still pending. Uploaded content is scoped to `X-User-ID`.

`POST /ingest` and `GET /get` have been removed and return 404. Chat responses no
longer include `recent_items`. Existing pasted-text database rows are retained as
legacy data but are not exposed, searched, or supplied to the model. No destructive
database migration is needed for this API change.

A user's chat questions and assistant replies are recorded through `/chat` or
`/chat/stream` in the selected conversation. They are conversation history, not
uploaded source documents.

## Conversation behavior

Each conversation has independent history, but may retrieve from **all documents
owned by its user**, including documents uploaded after the conversation was created.
The model receives at most ten completed prior turns with a 12,000-character history
budget. Failed/pending turns and other conversations are excluded from model history.

The user message is persisted before generation. A successful turn adds the assistant
reply; failure retains the user message with `failed` status. The history API returns
ordered message records with role, content, turn ID, status, and timestamp.

Only one generation can be pending in a conversation. A concurrent request receives
409. Other conversations can proceed independently. An abandoned pending turn becomes
failed when a new request arrives after five minutes; a late completion cannot overwrite
it. Clients should check history before retrying after a network failure because a
request may have completed. Requests are not idempotent.

SSE uses the `status` event with one `request_id`: `received`, `generating`, then
`completed` or `failed`. Ownership and busy checks run before the stream starts.
Disconnecting does not guarantee cancellation of the worker; pending work can finish
or be recovered through the timeout rule. This is lifecycle reporting, not token streaming.

## Errors and verification

- 422: missing/invalid/duplicate identity header, obsolete fields, or invalid payload.
- 404: missing resource or resource owned by another user.
- 409: conversation already generating, or a completion for a superseded turn.
- 502: generation failed; provider details are not returned.
- 503: storage unavailable; configured PostgreSQL never silently falls back to memory.
- File validation retains 400/413 responses with safe error codes.

```powershell
python -B -m pytest tests -p no:cacheprovider
```

Tests use mocked generation and clear inherited `DATABASE_URL`. PostgreSQL tests
require a separate disposable database configured through `TEST_DATABASE_URL`.

## Development boundaries

API routes handle requests and responses; services handle ingestion/generation;
repository implementations own storage queries. The Database/RAG team owns extraction,
indexing, and retrieval design. Coordinate changes to those interfaces across subteams.
Keep secrets in environment configuration and preserve Cloud Run compatibility.

Current request contracts are in `app/user_models.py`; shared legacy response types
remain in `app/models.py`. Historical request/authentication models in `models.py`
are not used by these routes and do not create authentication endpoints.
