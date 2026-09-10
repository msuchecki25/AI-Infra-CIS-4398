# RAWBerry API

This folder contains the FastAPI backend for the RAWBerry project.

## Purpose

The `rawberry-api` folder is the API layer for the application. Its current job is to provide a simple, testable backend contract for the frontend while the database/RAG pipeline is still being developed elsewhere.

## Current implementation

This backend is currently a starter API with in-memory storage.

### Available endpoints

- `GET /` — returns the API status and available routes
- `GET /health` — health check
- `GET /get` — returns ingested items
- `POST /chat` — accepts a chat message and returns a simple reply
- `POST /ingest` — stores text and optional metadata

## Current responsibilities of this folder

- FastAPI application setup
- Request/response modeling
- API route definitions
- Basic validation
- In-memory data handling for local development

## Out of scope for this folder

This folder is not yet responsible for:

- document chunking
- embedding generation
- vector search
- PostgreSQL or pgvector setup
- Gemini/LLM integration
- persistent storage
- authentication and authorization

## Folder contents

- `app/main.py` — FastAPI application
- `requirements.txt` — Python dependencies

## Run locally

```bash
cd rawberry-api
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Then open the Swagger UI at:

```text
http://127.0.0.1:8000/docs
```

## Notes

- The current storage is in-memory only, so data resets when the server restarts.
- The endpoint design is intentionally simple and should evolve as the database/RAG layer is added.

The immediate goal is NOT to build the entire RAG architecture.

The first goal is to establish:

```text
Frontend
   |
   v
FastAPI
   |
   v
JSON Response
```

Then:

```text
Frontend
   |
   v
FastAPI
   |
   v
Database/RAG
   |
   v
FastAPI
   |
   v
Frontend
```

Then:

```text
Frontend
   |
   v
FastAPI
   |
   v
RAG Retrieval
   |
   v
Gemini
   |
   v
FastAPI
   |
   v
Frontend
```

---

# 8. Current Starter API

The current prototype contains approximately these endpoints:

```text
GET  /
GET  /get
POST /chat
POST /ingest
```

The current `/chat` endpoint is a MOCK endpoint.

It currently echoes the user's message rather than calling Gemini.

Example:

```json
{
    "message": "What does the document say?"
}
```

may currently produce:

```json
{
    "reply": "You said: What does the document say?",
    "recent_items": []
}
```

This behavior is intentional during initial API development.

---

# 9. Current Temporary Memory Store

The starter API currently uses an in-memory Python structure similar to:

```python
memory_store: list[dict[str, Any]] = []
```

This is TEMPORARY.

It is only being used to learn/test FastAPI and establish API behavior.

Important:

* It is not a database.
* Data disappears when the FastAPI process restarts.
* It should eventually be replaced by calls to the Database/RAG layer.
* Do not build production functionality around `memory_store`.

---

# 10. Recommended Immediate Endpoints

## GET /health

Purpose:

Determine whether the RAWBerry API service is running.

Expected response:

```json
{
    "status": "healthy"
}
```

---

## POST /ingest

Purpose:

Receive a document upload from the frontend and initiate the document-processing pipeline.

Eventually supported formats:

* PDF
* DOCX
* TXT

Expected eventual flow:

```text
POST /ingest
      |
      v
Validate file
      |
      v
Send to ingestion pipeline
      |
      v
Database team:
extract -> clean -> chunk -> embed -> store
      |
      v
Return document information
```

Example future response:

```json
{
    "success": true,
    "document_id": "abc123",
    "filename": "research.pdf",
    "status": "processed"
}
```

The current implementation may accept text instead of a binary file while the API prototype is being developed.

---

## POST /chat

Purpose:

Submit a user question to RAWBerry.

Example future request:

```json
{
    "conversation_id": "chat123",
    "message": "What were the main findings of the study?"
}
```

Example future response:

```json
{
    "message_id": "msg456",
    "answer": "The study found that...",
    "sources": [
        {
            "document_id": "abc123",
            "filename": "research.pdf",
            "page": 7,
            "relevance": 0.94
        }
    ],
    "faithfulness_score": 0.91
}
```

The current implementation may simply echo the message while infrastructure is being developed.

---

# 11. Planned API Features

The API will eventually support features including:

### Document Ingestion

Upload documents and initiate the RAG ingestion pipeline.

### Retrieval & Citation

Retrieve approximately 3-5 relevant document chunks for a query and return source information with generated answers.

### Conversation Instances

Each conversation should have an independent context window.

### Conversation History

Users should be able to return to previous conversations.

### Context Injection

Relevant context from previous chats may be added to another conversation when requested.

### Specialized Chats

Users can select specialized AI assistants with different configurations/domains.

### System Prompts

Users can configure instructions controlling how the AI responds.

### Faithfulness Score

Responses may include a score representing how strongly the generated answer is supported by retrieved information.

### Chat Status

The frontend should be able to display states such as:

```text
Thinking
Retrieving Documents
Generating Response
```

### Authentication / Authorization

Users should have accounts and only be able to access their private conversations unless a conversation has explicitly been shared.

### Shareable Links

Conversation owners can generate read-only share links.

A recipient may view a shared conversation, but only the original owner should be able to continue or modify the original conversation.

---

# 12. Technology Stack

Current/planned technologies:

```text
Language:
Python

API Framework:
FastAPI

Development Server:
Uvicorn / FastAPI CLI

API Documentation:
OpenAPI / Swagger

Cloud:
Google Cloud Platform (GCP)

API Hosting:
Google Cloud Run

AI:
Google Gemini

Embeddings:
Google Gemini embedding model

Relational Database:
PostgreSQL

Vector Search:
pgvector or another approved vector database

Version Control:
Git / GitHub
```

Technology choices may evolve as the project develops.

---

# 13. GCP Constraints

The team currently has limited Google Cloud credits.

Development should therefore prioritize low-cost/serverless resources.

For the API, the preferred initial deployment target is:

```text
FastAPI
   |
   v
Docker Container
   |
   v
Google Cloud Run
```

Avoid creating expensive persistent compute resources unless they are required.

Do not assume GPUs are required for the API.

Cost efficiency is an explicit project requirement.

---

# 14. API Development Priorities

Development should occur incrementally.

## Phase 1 — API Skeleton

Implement and verify:

```text
GET /health
POST /chat
POST /ingest
```

Goal:

```text
Frontend -> FastAPI -> JSON
```

No real RAG or Gemini integration is required yet.

---

## Phase 2 — Frontend Integration

Define stable request and response contracts.

Goal:

```text
RAWBerry Frontend
        |
        v
     FastAPI
        |
        v
 predictable JSON
```

Frontend teams should be able to develop against the API even if backend functionality is mocked.

---

## Phase 3 — Database/RAG Integration

Replace temporary memory structures with Database/RAG service calls.

Goal:

```text
FastAPI
   |
   v
Database/RAG Service
   |
   v
PostgreSQL + Vector Search
```

---

## Phase 4 — Gemini Integration

Implement the actual RAG generation pipeline.

Goal:

```text
Question
   |
   v
Retrieve top chunks
   |
   v
Construct prompt
   |
   v
Gemini
   |
   v
Answer + citations
```

---

## Phase 5 — Advanced Features

After the core RAG pipeline works, implement:

* Conversation history
* Context windows
* Authentication
* Authorization
* System prompts
* Specialized chats
* Faithfulness score
* Chat status
* Shareable links
* Streaming
* Rate limiting

---

# 15. Performance Requirements

The final system is expected to work toward:

* Beginning response generation/streaming within approximately 3 seconds
* Completing normal responses under 500 words within approximately 15 seconds
* Supporting approximately 10 concurrent users
* Returning HTTP `429 Too Many Requests` when capacity is exceeded rather than crashing
* Maintaining reliable availability during project demonstrations

Do not prematurely optimize these requirements during the initial API prototype.

---

# 16. Security Requirements

The final system must enforce user isolation.

Important principles:

```text
User A
  |
  +----> User A conversations      ALLOWED

User A
  |
  +----> User B conversations      DENIED
```

Passwords must never be stored as plaintext.

Authorization must be checked server-side.

The frontend must NEVER be trusted to enforce access control by itself.

Shareable links are an explicit exception to private conversation access, but shared conversations should remain read-only for users other than the original owner unless requirements change.

---

# 17. FastAPI Development

During local development, the API should normally be accessible at:

```text
http://localhost:8000
```

Interactive Swagger documentation:

```text
http://localhost:8000/docs
```

OpenAPI specification:

```text
http://localhost:8000/openapi.json
```

Typical development command:

```bash
uvicorn main:app --reload
```

If the project structure becomes:

```text
app/
    main.py
```

use:

```bash
uvicorn app.main:app --reload
```

---

# 18. Suggested Future Project Structure

As the API grows, prefer modular organization rather than putting everything in `main.py`.

```text
rawberry-api/
|
├── app/
│   ├── main.py
│   │
│   ├── routers/
│   │   ├── health.py
│   │   ├── ingest.py
│   │   ├── chat.py
│   │   ├── conversations.py
│   │   ├── auth.py
│   │   └── share.py
│   │
│   ├── services/
│   │   ├── rag_service.py
│   │   ├── gemini_service.py
│   │   └── database_service.py
│   │
│   ├── models/
│   │   ├── requests.py
│   │   └── responses.py
│   │
│   └── config.py
│
├── tests/
│
├── requirements.txt
├── Dockerfile
├── .gitignore
└── README.md
```

Do NOT create this entire structure prematurely.

Refactor into modules as functionality grows.

---

# 19. Guidance for GitHub Copilot / AI Coding Assistants

When generating code for this repository, follow these project boundaries.

## DO

* Use Python and FastAPI.
* Prefer simple, readable implementations.
* Use Pydantic models for request/response validation.
* Use type hints.
* Keep REST endpoints thin.
* Move substantial business logic into service modules as the project grows.
* Return predictable JSON structures.
* Use appropriate HTTP status codes.
* Use asynchronous functions when operations are genuinely asynchronous/I/O-bound.
* Design APIs that can later integrate with PostgreSQL, pgvector, and Gemini.
* Keep frontend and backend loosely coupled.
* Add comments when architectural reasoning is not obvious.
* Preserve compatibility with deployment to Google Cloud Run.
* Keep secrets in environment variables.
* Write code that can be tested independently.

## DO NOT

* Implement a second vector database inside the API layer.
* Put database credentials directly in source code.
* Put Gemini/API keys directly in source code.
* Store passwords in plaintext.
* Trust user IDs supplied by the frontend for authorization.
* Couple frontend code directly to PostgreSQL.
* Put the entire project permanently inside `main.py`.
* Replace the Database/RAG team's responsibilities without coordination.
* Assume `memory_store` is production persistence.
* Introduce unnecessary infrastructure or expensive GCP resources.
* Overengineer early prototypes.
* Implement advanced features before the core API path works.

---

# 20. Most Important Architectural Rule

The primary boundary between the two AI Infrastructure subteams is:

> **The Database/RAG team decides how information is processed, stored, indexed, and retrieved. The API team decides how RAWBerry applications access and use that information.**

For example:

```text
DATABASE/RAG TEAM

search_chunks(query, limit=5)
        |
        v
[
  {
    "text": "...",
    "document_id": "...",
    "page": 4,
    "score": 0.94
  }
]
```

The API team can consume that functionality to implement:

```text
POST /chat
```

without needing to know the exact SQL or vector-search implementation.

---

# 21. Current API Team Goal

The immediate API-team objective is:

```text
1. FastAPI runs locally
          |
          v
2. /health works
          |
          v
3. /chat works with mock response
          |
          v
4. /ingest accepts input
          |
          v
5. Frontend can call FastAPI
          |
          v
6. Deploy API to Cloud Run
          |
          v
7. Connect Database/RAG retrieval
          |
          v
8. Connect Gemini
          |
          v
9. Complete RAG pipeline
```

Do not skip directly to Step 9.

The project should always maintain a small working vertical slice while additional components are integrated.

---

# 22. Definition of Core Success

The first major backend success is:

```text
User asks question
       |
       v
RAWBerry Frontend
       |
       v
FastAPI /chat
       |
       v
RAG retrieval
       |
       v
Top relevant document chunks
       |
       v
Gemini
       |
       v
Grounded answer
       |
       v
FastAPI
       |
       v
RAWBerry Frontend
```

Once this works reliably, advanced RAWBerry features can be layered on top.
