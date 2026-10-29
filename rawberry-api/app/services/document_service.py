from __future__ import annotations

import os
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status

from app.ingestion import UnreadableDocument, extract_pages, split_pages
from app.models import UploadResponse
from app.user_models import DocumentRecord
from app.repository import Repository

# TXT and PDF text is chunked here; DOCX extraction remains pending. PostgreSQL embeds chunks on save.
class DocumentService:
    MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024
    ALLOWED_EXTENSIONS = {".pdf": "application/pdf", ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document", ".txt": "text/plain"}

    def __init__(self, store: Repository) -> None:
        # Store uploaded files and their extracted chunks through the repository.
        self.store = store


    def _extract_pages(self, ext: str, raw_bytes: bytes) -> list[tuple[int | None, str]]:
        # Cheap signature checks run before any parsing.
        if (ext == ".pdf" and not raw_bytes.startswith(b"%PDF-")) or (
                ext == ".docx" and not raw_bytes.startswith(b"PK\x03\x04")):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "success": False,
                    "error_code": "INVALID_FILE_CONTENT",
                    "message": "File content does not match its filename extension.",
                },
            )
        try:
            return extract_pages(ext, raw_bytes)
        except UnicodeDecodeError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "success": False,
                    "error_code": "INVALID_TEXT_ENCODING",
                    "message": "Text files must use UTF-8 encoding.",
                },
            ) from exc
        except UnreadableDocument as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "success": False,
                    "error_code": "UNREADABLE_FILE",
                    "message": "The file could not be read. It may be damaged or password-protected.",
                },
            ) from exc

    def upload_document(self, user_id: str, files: list[UploadFile]) -> list[UploadResponse]:
        if not files:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"success": False, "error_code": "NO_FILES", "message": "At least one file is required."},
            )

        # Validate and extract every file before saving any, so one bad file rejects the batch.
        validated_files: list[tuple[str, str, bytes, list[tuple[int | None, str]]]] = []
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

            validated_files.append((filename, ext, raw_bytes, self._extract_pages(ext, raw_bytes)))

        responses: list[UploadResponse] = []
        documents: list[tuple[dict, bytes, list[dict]]] = []
        for filename, ext, raw_bytes, pages in validated_files:
            document_id = str(uuid4())
            chunks = split_pages(pages, document_id)
            document = DocumentRecord(
                id=document_id,
                filename=filename,
                file_type=ext,
                size_bytes=len(raw_bytes),
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

        statuses = self.store.save_documents(user_id, documents)
        # Report what storage actually indexed; DOCX and PDFs without a text layer have no chunks.
        for response, embedding_status in zip(responses, statuses, strict=True):
            response.embedding_status = embedding_status
            if embedding_status == "completed":
                response.message = "Document uploaded and indexed successfully."
        return responses
