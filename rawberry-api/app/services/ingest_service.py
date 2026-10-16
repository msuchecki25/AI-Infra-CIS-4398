from __future__ import annotations

import os
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status

from app.models import IngestResponse, ItemRecord, UploadResponse
from app.user_models import DocumentChunk, DocumentRecord, IngestRequest
from app.repository import Repository

# Extraction and embedding generation remain the database/RAG team's next stage.
class IngestService:
    MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024
    ALLOWED_EXTENSIONS = {".pdf": "application/pdf", ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document", ".txt": "text/plain"}

    def __init__(self, store: Repository) -> None:
        # Store the location where ingested items will be saved.
        self.store = store

    # Plain text ingestion remains separate from the uploaded-document chunk pipeline.
    def ingest(self, user_id: str, request: IngestRequest) -> IngestResponse:
        # Create, save, and return an item from the submitted text.
        item = ItemRecord(
            id=str(uuid4()),
            text=request.text,
            metadata=request.metadata or {},
        )

        self.store.add(user_id, item.model_dump())

        return IngestResponse(
            message="Item ingested successfully",
            item=item,
            count=len(self.store.list_items(user_id)),
        )

    def _validate_file_content(self, filename: str, raw_bytes: bytes) -> str | None:
        ext = os.path.splitext(filename)[1].lower()
        if ext == ".txt":
            try:
                return raw_bytes.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "success": False,
                        "error_code": "INVALID_TEXT_ENCODING",
                        "message": "Text files must use UTF-8 encoding.",
                    },
                ) from exc
        if ext == ".pdf" and raw_bytes.startswith(b"%PDF-"):
            return None
        if ext == ".docx" and raw_bytes.startswith(b"PK\x03\x04"):
            return None
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "success": False,
                "error_code": "INVALID_FILE_CONTENT",
                "message": "File content does not match its filename extension.",
            },
        )

    def _chunk_text(self, document_id: str, text: str) -> list[DocumentChunk]:
        max_chars = 900
        chunks: list[DocumentChunk] = []
        for idx, start in enumerate(range(0, len(text), max_chars)):
            chunk_text = text[start:start + max_chars].strip()
            if not chunk_text:
                continue
            chunks.append(
                DocumentChunk(
                    document_id=document_id,
                    chunk_index=idx,
                    page_number=None,
                    text=chunk_text,
                    status="pending",
                )
            )
        return chunks

    def upload_document(self, user_id: str, files: list[UploadFile]) -> list[UploadResponse]:
        if not files:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"success": False, "error_code": "NO_FILES", "message": "At least one file is required."},
            )

        validated_files: list[tuple[UploadFile, str, str, int]] = []
        for uploaded_file in files:
            filename = uploaded_file.filename or "upload.bin"
            ext = os.path.splitext(filename)[1].lower()
            if ext not in self.ALLOWED_EXTENSIONS:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "success": False,
                        "error_code": "INVALID_FILE_TYPE",
                        "message": "Only PDF, DOCX, and TXT files are supported.",
                    },
                )

            raw_bytes = uploaded_file.file.read(self.MAX_FILE_SIZE_BYTES + 1)
            if not raw_bytes:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"success": False, "error_code": "EMPTY_FILE", "message": "Uploaded file is empty."},
                )
            if len(raw_bytes) > self.MAX_FILE_SIZE_BYTES:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail={"success": False, "error_code": "FILE_TOO_LARGE", "message": "File exceeds 25MB limit."},
                )

            self._validate_file_content(filename, raw_bytes)
            uploaded_file.file.seek(0)
            validated_files.append((uploaded_file, filename, ext, len(raw_bytes)))

        responses: list[UploadResponse] = []
        documents: list[tuple[dict, bytes, list[dict]]] = []
        for uploaded_file, filename, ext, size_bytes in validated_files:
            raw_bytes = uploaded_file.file.read(self.MAX_FILE_SIZE_BYTES + 1)
            text = self._validate_file_content(filename, raw_bytes)
            document_id = str(uuid4())
            chunks = self._chunk_text(document_id, text) if text is not None else []
            document = DocumentRecord(
                id=document_id,
                filename=filename,
                file_type=ext,
                size_bytes=size_bytes,
                user_id=user_id,
                chunk_count=len(chunks),
                embedding_status="pending",
                metadata={"source": "upload_endpoint"},
            )

            documents.append((document.model_dump(), raw_bytes, [chunk.model_dump() for chunk in chunks]))

            responses.append(
                UploadResponse(
                    success=True,
                    document_id=document.id,
                    filename=document.filename,
                    status="uploaded",
                    chunk_count=len(chunks),
                    message="Document uploaded successfully; processing is pending.",
                    embedding_status="pending",
                )
            )

        self.store.save_documents(user_id, documents)
        return responses
