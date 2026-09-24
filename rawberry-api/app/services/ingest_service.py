from __future__ import annotations

import os
from uuid import uuid4

from fastapi import HTTPException, UploadFile

from app.models import DocumentChunk, DocumentRecord, IngestRequest, IngestResponse, ItemRecord, UploadResponse
from app.store import InMemoryStore

#DB team will eventually replace this service with a more robust ingestion service 
# that handles chunking, vectorization, and RAG retrieval. For now, this service 
# simply saves the ingested text to an in-memory store.
class IngestService:
    MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024
    ALLOWED_EXTENSIONS = {".pdf": "application/pdf", ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document", ".txt": "text/plain"}

    def __init__(self, store: InMemoryStore) -> None:
        # Store the location where ingested items will be saved.
        self.store = store

    #this is a temporary ingestion method that saves items to the in-memory store.
    #creates one record for each ingestion request, no chunking yet, no vector database yet, 
    # no RAG retrieval yet.
    def ingest(self, request: IngestRequest) -> IngestResponse:
        # Create, save, and return an item from the submitted text.
        item = ItemRecord(
            id=str(uuid4()),
            text=request.text,
            metadata=request.metadata or {},
        )

        self.store.add(item.model_dump())

        return IngestResponse(
            message="Item ingested successfully",
            item=item,
            count=len(self.store.list_items()),
        )

    def _normalize_text(self, filename: str, raw_bytes: bytes) -> str:
        ext = os.path.splitext(filename)[1].lower()
        if ext == ".txt":
            return raw_bytes.decode("utf-8", errors="replace")
        if ext in {".pdf", ".docx"}:
            # Provisional implementation: treat any non-txt binary as raw text for now.
            return raw_bytes.decode("utf-8", errors="replace")
        raise HTTPException(status_code=400, detail="Unsupported file type")

    def _chunk_text(self, document_id: str, owner_id: str | None, text: str) -> list[DocumentChunk]:
        max_chars = 900
        chunks: list[DocumentChunk] = []
        for idx, start in enumerate(range(0, len(text), max_chars)):
            chunk_text = text[start:start + max_chars].strip()
            if not chunk_text:
                continue
            chunks.append(
                DocumentChunk(
                    document_id=document_id,
                    owner_id=owner_id,
                    chunk_index=idx,
                    page_number=(idx + 1),
                    text=chunk_text,
                    status="pending",
                )
            )
        return chunks

    def upload_document(self, files: list[UploadFile], owner_id: str | None = None) -> UploadResponse:
        if not files:
            raise HTTPException(status_code=400, detail="At least one file is required")

        uploaded_file = files[0]
        filename = uploaded_file.filename or "upload.bin"
        ext = os.path.splitext(filename)[1].lower()

        if ext not in self.ALLOWED_EXTENSIONS:
            raise HTTPException(status_code=400, detail={"success": False, "error_code": "INVALID_FILE_TYPE", "message": "Only PDF, DOCX, and TXT files are supported."})

        raw_bytes = uploaded_file.file.read()
        if len(raw_bytes) == 0:
            raise HTTPException(status_code=400, detail={"success": False, "error_code": "EMPTY_FILE", "message": "Uploaded file is empty."})
        if len(raw_bytes) > self.MAX_FILE_SIZE_BYTES:
            raise HTTPException(status_code=400, detail={"success": False, "error_code": "FILE_TOO_LARGE", "message": "File exceeds 25MB limit."})

        document_id = str(uuid4())
        text = self._normalize_text(filename, raw_bytes)
        chunks = self._chunk_text(document_id, owner_id, text)

        document = DocumentRecord(
            id=document_id,
            filename=filename,
            file_type=ext,
            size_bytes=len(raw_bytes),
            owner_id=owner_id,
            chunk_count=len(chunks),
            embedding_status="pending",
            metadata={"source": "upload_endpoint"},
        )

        self.store.add_document(document.model_dump())
        for chunk in chunks:
            self.store.add_chunk(chunk.model_dump())

        return UploadResponse(
            success=True,
            document_id=document.id,
            filename=document.filename,
            status="uploaded",
            chunk_count=len(chunks),
            message="Document uploaded and chunked successfully",
            embedding_status="pending",
        )
