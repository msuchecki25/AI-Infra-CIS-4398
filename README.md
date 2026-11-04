# AI-Infra-CIS-4398

RAWBerry provides backend API endpoints for document ingestion, chunking, RAG
retrieval, and AI model integration.

Reviewed medical and education documents enter RAG through `POST /uploadmedical` and `POST /uploadedu` (developer-only); pasted-text `/ingest` is not supported.
Chat questions and answers are stored separately as conversation history.

Authentication, login, registration, and account management belong to the upstream
application. This backend is responsible for user-scoped storage and retrieval
using trusted user context supplied by that application's backend or gateway.
All data endpoints require `X-User-ID` from that trusted upstream service. Storage,
retrieval, preferences, and persistent conversation histories are scoped to that ID.
The header itself is not authentication; upstream must prevent identity spoofing.

See the [API README](rawberry-api/README.md#authentication-boundary-and-user-context)
for the responsibility boundary and current limitations, the
[database README](rawberry-db/README.MD) for schema setup, and
[run instructions](rawberry-api/run.md) for local Google Cloud configuration.
## Requirements
- Python 3.12+


Install all project dependencies from the repository root:

```powershell
python -m pip install -r requirements.txt
```

The root requirements include `rawberry-api/requirements.txt`, which owns shared
backend and ingestion dependencies. Keep additional dependencies for project
scripts and experiments in the root file. Add shared packages only to the API
file so local project installs and API CI receive the same requirements.

For an API-only installation (the same dependency set CI installs), run:

```powershell
python -m pip install -r rawberry-api/requirements.txt
```
