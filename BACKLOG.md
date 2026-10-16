# RAWBerry sprint backlog

Prepared from the working tree on October 8, 2026. These are proposed backlog items, not committed sprint scope. Points are relative estimates for team refinement; owners identify the responsible subteam rather than an assigned person. Sprint groupings indicate sequence, not dates or guaranteed capacity.

## Current baseline

The API implements health checks, text ingestion, multi-file uploads with a 25 MB per-file limit, basic TXT chunking, keyword retrieval, optional Vertex AI Gemini calls, per-user in-memory response preferences, and SSE chat lifecycle events. PostgreSQL/pgvector schema files and API tests exist. Storage remains in memory; PDF/DOCX uploads retain bytes but produce no extracted chunks; embedding status remains pending. No frontend implementation is present in this repository.

## Proposed Sprint 1: align contracts and establish persistence

### RB-01 — Align API, frontend, and database contracts
**Priority:** P0 · **Estimate:** 3 points · **Owner:** API + Database/RAG · **Dependencies:** None

As an integrating developer, I need agreed identifiers and payloads so uploads, retrieval, and chat work across services.

Acceptance criteria:
- Agree on one identifier strategy: uploaded documents currently use UUID strings while SQL document IDs are BIGINT; reconcile integer user IDs and string owner IDs.
- Document how `data.window` maps to a conversation and how `data.agent` selects an assistant; neither currently affects chat behavior.
- Define ingestion and retrieval interfaces, including chunk text, document/chunk IDs, filename, nullable page, relevance score, and ownership scope.
- Publish current request/response examples and error contracts, including `/upload` and required chat fields; update the root endpoint listing and stale README descriptions.

### RB-02 — Add repeatable database migrations
**Priority:** P0 · **Estimate:** 3 points · **Owner:** Database/RAG · **Dependencies:** RB-01

As a developer, I need reproducible schema setup so local and deployed environments use the same database structure.

Acceptance criteria:
- Introduce versioned migrations for the existing schema and the identifier decisions from RB-01.
- Provide ID generation, required status/role seed data, and fields needed for upload metadata, processing state, and source locations.
- Define the embedding model/dimension configuration and validate vector dimensions before storage.
- Verify a fresh database setup and an upgrade of an existing database; document commands and environment variables without secrets.

### RB-03 — Replace temporary storage with persistent repositories
**Priority:** P0 · **Estimate:** 5 points · **Owner:** API + Database/RAG · **Dependencies:** RB-02

As a user, I need uploaded documents and preferences to survive API restarts.

Acceptance criteria:
- Persist ingested text, document metadata, chunks, and system prompts through an agreed repository interface.
- Store original file bytes in the team-approved durable storage location and persist their reference.
- Keep in-memory storage available for isolated tests and explicitly configured local development.
- Verify data survives an API restart and is visible across API instances; roll back database writes on persistence failures and define cleanup for file writes.

### RB-04 — Authenticate requests and enforce owner isolation
**Priority:** P0 · **Estimate:** 5 points · **Owner:** API · **Dependencies:** RB-01, RB-03

As a user, I need my documents and preferences to be accessible only to authorized users.

Acceptance criteria:
- Integrate the team's agreed identity mechanism; derive ownership from verified identity rather than trusting submitted `userid` or `owner_id`.
- Enforce ownership on uploads, ingestion, item listing, retrieval, chat context, and system-prompt reads/writes.
- Return consistent unauthorized/forbidden responses and prevent another user's content appearing in `recent_items` or generated context.
- Add two-user tests covering both direct access attempts and retrieval leakage.

## Proposed Sprint 2: complete document ingestion

### RB-05 — Extract text from PDF and DOCX uploads
**Priority:** P1 · **Estimate:** 5 points · **Owner:** Database/RAG · **Dependencies:** RB-01, RB-03

As a user, I need supported file formats to become searchable content.

Acceptance criteria:
- Extract text from text-based PDFs and DOCX files as well as UTF-8 TXT files.
- Validate DOCX structure beyond its ZIP signature; handle corrupt, encrypted, and textless files with documented processing errors.
- Preserve actual PDF page locations; use nullable pages or meaningful section locations for formats without reliable pages.
- Declare scanned-PDF OCR out of scope for this item and report when a document requires OCR.
- Verify extraction with representative fixtures for each supported format and failure case.

### RB-06 — Implement retrieval-ready chunking
**Priority:** P1 · **Estimate:** 3 points · **Owner:** Database/RAG · **Dependencies:** RB-05

As a user, I need relevant passages to retain enough context for useful answers.

Acceptance criteria:
- Replace fixed 900-character slices with configurable, model-budget-aware chunk sizes and overlap.
- Preserve document ownership, stable chunk order, source locations, and identifiers.
- Stop assigning chunk indexes as page numbers; retain real page metadata or null.
- Verify coverage of extracted text, expected overlap, and handling of whitespace-only documents.

### RB-07 — Generate and persist document embeddings
**Priority:** P1 · **Estimate:** 5 points · **Owner:** Database/RAG · **Dependencies:** RB-02, RB-06

As a user, I need my uploaded documents indexed for semantic search.

Acceptance criteria:
- Generate embeddings using the agreed model and store vectors with model/version metadata and chunk references.
- Transition processing state to ready only after required chunks are indexed; retain actionable failure states.
- Bound provider requests and retry transient failures without duplicating chunk/model embeddings.
- Verify a successful indexing run and interrupted-run recovery with mocked provider failures.

### RB-08 — Expose ingestion progress and recovery
**Priority:** P1 · **Estimate:** 5 points · **Owner:** API + Database/RAG · **Dependencies:** RB-03, RB-05, RB-07

As a user, I need to know when an upload is searchable and whether processing failed.

Acceptance criteria:
- Run extraction/indexing through a durable background processing mechanism agreed by both subteams.
- Add an owner-scoped document status endpoint reporting uploaded, processing, ready, or failed states and safe error details.
- Add document listing and an authorized retry operation that avoids duplicate processing.
- Define batch semantics and total request/file-count limits in addition to the existing per-file limit.
- Verify queued work and status survive an API restart.

## Proposed Sprint 3: deliver grounded chat

### RB-09 — Integrate semantic retrieval into chat
**Priority:** P1 · **Estimate:** 5 points · **Owner:** Database/RAG + API · **Dependencies:** RB-04, RB-07

As a user, I need chat to find relevant passages even when my question uses different wording.

Acceptance criteria:
- Embed queries and retrieve a configurable top 3–5 chunks through the agreed service interface.
- Filter by verified owner and selected document/conversation scope before returning results.
- Return text and source metadata together, with defined ranking and insufficient-match behavior.
- Demonstrate retrieval on paraphrased questions and verify that unindexed documents and another user's chunks are excluded.

### RB-10 — Generate grounded answers with traceable citations
**Priority:** P1 · **Estimate:** 5 points · **Owner:** API · **Dependencies:** RB-09

As a user, I need to see which document passages support an answer.

Acceptance criteria:
- Build bounded prompts with labeled retrieved passages and clear instructions for unsupported questions.
- Treat document text as untrusted context and keep user preferences subordinate to grounding instructions.
- Extend the agreed chat response with sources containing document/chunk IDs, filename, valid source location, and retrieval score.
- Validate citation references against retrieved chunks; avoid returning unrelated recent items as implied evidence.
- Verify supported answers, insufficient context, and misleading instructions embedded in a document.

### RB-11 — Make Gemini failures predictable
**Priority:** P1 · **Estimate:** 3 points · **Owner:** API · **Dependencies:** RB-01

As a user, I need clear failures when generation is unavailable.

Acceptance criteria:
- Validate real-mode configuration and avoid silently selecting mock chat when real mode is requested but the project is missing.
- Configure timeouts and bounded retries for transient provider errors; reuse clients with an appropriate application lifecycle.
- Handle empty or blocked responses explicitly instead of returning a provider object string or echo as a successful real answer.
- Return safe, consistent errors for `/chat` and a terminal failed event for `/chat/stream`; test configuration, timeout, quota, and empty-response cases.

### RB-12 — Report actual retrieval and generation progress
**Priority:** P2 · **Estimate:** 3 points · **Owner:** API · **Dependencies:** RB-09, RB-11

As a user, I need chat status to describe the work happening on my request.

Acceptance criteria:
- Extend existing SSE lifecycle events with retrieval progress driven by real service stages.
- Preserve one request ID and exactly one completed or failed terminal event.
- Define disconnect handling and ensure concurrent requests do not block the event loop.
- Document that lifecycle events report progress; token streaming is a separate future enhancement.

## Proposed Sprint 4: conversations and demo readiness

### RB-13 — Persist independent conversation history
**Priority:** P1 · **Estimate:** 5 points · **Owner:** API + Database/RAG · **Dependencies:** RB-03, RB-04, RB-10

As a user, I need to resume previous chats without mixing their context.

Acceptance criteria:
- Implement owner-scoped conversation creation, listing, and message-history retrieval using the agreed window/conversation contract.
- Persist user messages, assistant replies, and citation links in order.
- Include a bounded history from the selected conversation in generation and isolate other conversations.
- Persist the selected assistant configuration and define supported `data.agent` values rather than silently ignoring them.
- Verify conversation history survives restart and remains isolated between users and sessions.

### RB-14 — Automate integration checks and prepare Cloud Run deployment
**Priority:** P1 · **Estimate:** 5 points · **Owner:** API + Infrastructure · **Dependencies:** RB-08, RB-10, RB-11

As a team, we need repeatable verification and a reliable demonstration environment.

Acceptance criteria:
- Add CI for existing tests and meaningful integration tests spanning upload, indexing, retrieval, and cited chat; use provider stubs by default.
- Supply local API/database startup instructions and update configuration documentation.
- Prepare deployment configuration using the existing Dockerfile, environment-based secrets, least-privilege service identity, and approved frontend CORS origins.
- Demonstrate health/readiness checks, safe structured logs with request IDs, and a smoke test in the agreed environment.
- Document cost limits, scaling settings, and rollback; deployment remains subject to the team's infrastructure authorization.

### RB-15 — Validate concurrency and enforce capacity limits
**Priority:** P2 · **Estimate:** 3 points · **Owner:** API + Infrastructure · **Dependencies:** RB-14

As a user, I need the service to remain responsive during the team demonstration.

Acceptance criteria:
- Exercise a representative workload with approximately 10 concurrent users and record latency, errors, and environment details.
- Measure the documented targets: generation/streaming begins around 3 seconds and normal answers under 500 words complete around 15 seconds; distinguish receipt events from actual generation start.
- Implement bounded request capacity and return HTTP 429 when exceeded, with documented retry behavior.
- Check both chat routes and ingestion under concurrent load; identify remaining bottlenecks and estimated provider cost.

## Later backlog

- **RB-16 — Read-only conversation sharing:** create revocable owner-managed links; recipients can view but cannot modify the original conversation. Depends on RB-04 and RB-13.
- **RB-17 — Explicit context transfer:** let an owner select history to copy into another conversation, with provenance and context limits. Depends on RB-13.
- **RB-18 — Grounding evaluation:** define a labeled evaluation set and measure citation correctness and unsupported claims before introducing a user-visible faithfulness score. Depends on RB-10.
- **RB-19 — Token streaming:** stream generated text incrementally while preserving status events, citations, cancellation, and error handling. Depends on RB-10 through RB-12.
- **RB-20 — Scanned-document OCR:** assess representative scans, extraction quality, processing time, and cost before adding OCR ingestion. Depends on RB-05 and RB-08.

## Planning and completion rules

P0 items unblock integration or ownership enforcement; P1 items deliver the core persistent RAG workflow; P2 items improve progress reporting and operational reliability. Do not expose private documents in a shared environment before RB-04 is complete. Pull tickets into actual sprints according to measured team capacity and dependencies; split 5-point items when refinement reveals multiple independently reviewable changes.

Each implemented item is done when its acceptance criteria are demonstrated, appropriate tests pass, request/response documentation is updated, and both responsible subteams review any changed integration contract.
