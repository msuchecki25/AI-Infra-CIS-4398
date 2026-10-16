# AI-Infra-CIS-4398

RAWBerry provides backend API endpoints for document ingestion, chunking, RAG
retrieval, and AI model integration.

Authentication, login, registration, and account management belong to the upstream
application. This backend is responsible for user-scoped storage and retrieval
using trusted user context supplied by that application's backend or gateway.
All data endpoints require `X-User-ID` from that trusted upstream service. Storage,
retrieval, preferences, and persistent conversation histories are scoped to that ID.
The header itself is not authentication; upstream must prevent identity spoofing.

See the [API README](rawberry-api/README.md#authentication-boundary-and-user-context)
for the responsibility boundary and current limitations, and
[persistence setup](rawberry-api/PERSISTENCE.md) for storage configuration.
