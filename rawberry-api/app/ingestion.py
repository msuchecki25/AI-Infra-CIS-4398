"""Text extraction and chunking shared by /upload and the batch ingestion pipeline.

Both entry points pass the resulting chunks to Repository.save_documents, which
embeds them, so every source document is split the same way.
"""
from io import BytesIO

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.user_models import DocumentChunk

# 900 characters stays well inside the embedding model's input limit (auto_truncate is off).
CHUNK_SIZE = 900
CHUNK_OVERLAP = 100


class UnreadableDocument(ValueError):
    """The file has the right signature but its text cannot be read."""


def extract_pages(ext: str, raw_bytes: bytes) -> list[tuple[int | None, str]]:
    """Return (page_number, text) pairs; TXT has no pages and DOCX is not extracted yet.

    TXT must be UTF-8, so UnicodeDecodeError propagates to the caller.
    """
    if ext == ".txt":
        return [(None, raw_bytes.decode("utf-8"))]
    if ext == ".pdf":
        from pypdf import PdfReader

        try:
            reader = PdfReader(BytesIO(raw_bytes))
            # Page numbers start at 1 so citations match what the reader sees.
            # PostgreSQL TEXT rejects NUL characters, which some PDFs emit.
            return [(number, (page.extract_text() or "").replace("\x00", ""))
                    for number, page in enumerate(reader.pages, start=1)]
        except Exception as exc:
            # pypdf raises many exception types for damaged or encrypted files.
            raise UnreadableDocument() from exc
    return []


def split_pages(pages: list[tuple[int | None, str]], document_id: str) -> list[DocumentChunk]:
    """Split page by page so each chunk keeps its page; indexes run across the document."""
    splitter = RecursiveCharacterTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
    chunks: list[DocumentChunk] = []
    for page_number, text in pages:
        for piece in splitter.split_text(text):
            piece = piece.strip()
            if piece:
                chunks.append(DocumentChunk(document_id=document_id, chunk_index=len(chunks),
                                            page_number=page_number, text=piece, status="pending"))
    return chunks
