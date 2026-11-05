"""File rules, text extraction and chunking shared by /upload and the batch ingestion pipeline.

Both entry points accept the same file types and size, pass the resulting chunks to
Repository.save_documents, which embeds them, so every source document is split the same way.
"""
from io import BytesIO

from langchain_text_splitters import RecursiveCharacterTextSplitter


from bisect import bisect_right
import re

from app.services.document_cleaner import clean_pages

from app.user_models import DocumentChunk

MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024
ALLOWED_EXTENSIONS = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".txt": "text/plain",
}
# DOCX is a ZIP archive, so it starts with the ZIP local file header.
FILE_SIGNATURES = {".pdf": b"%PDF-", ".docx": b"PK\x03\x04"}

# 900 characters stays well inside the embedding model's input limit (auto_truncate is off).
CHUNK_SIZE = 900
CHUNK_OVERLAP = 100


class InvalidFileContent(ValueError):
    """The file's bytes don't match its extension."""


class UnreadableDocument(ValueError):
    """The file has the right signature but its text cannot be read."""


def extract_pages(ext: str, raw_bytes: bytes) -> list[tuple[int | None, str]]:
    """Return (page_number, text) pairs; TXT and DOCX have no pages.

    TXT must be UTF-8, so UnicodeDecodeError propagates to the caller.
    """
    # Cheap signature checks run before any parsing.
    if not raw_bytes.startswith(FILE_SIGNATURES.get(ext, b"")):
        raise InvalidFileContent()
    if ext == ".txt":
        return [(None, raw_bytes.decode("utf-8"))]
    if ext == ".docx":
        return [(None, _extract_docx_text(raw_bytes))]
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


def _extract_docx_text(raw_bytes: bytes) -> str:
    """Join paragraphs and table rows in document order; headers, footers and images are skipped."""
    from docx import Document
    from docx.table import Table

    try:
        document = Document(BytesIO(raw_bytes))
        blocks = []
        for block in document.iter_inner_content():
            if isinstance(block, Table):
                # One line per row keeps each row's cells together in the same chunk.
                blocks.extend(" | ".join(cell.text for cell in row.cells) for row in block.rows)
            else:
                blocks.append(block.text)
    except Exception as exc:
        # python-docx raises several exception types for damaged or non-Word ZIP files.
        raise UnreadableDocument() from exc
    # Same NUL stripping as PDF; PostgreSQL TEXT rejects it.
    return "\n".join(blocks).replace("\x00", "")



def split_pages(
    pages: list[tuple[int | None, str]],
    document_id: str,
    *,
    line_sources: list[tuple[int, ...]] | None = None,
    source_map: list[dict] | None = None,
) -> list[DocumentChunk]:
    """Split text and optionally record original source locations."""

    if source_map is not None:
        if line_sources is None or len(line_sources) != len(pages):
            raise ValueError("Source lines must match extracted pages.")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        add_start_index=source_map is not None,
    )

    chunks: list[DocumentChunk] = []

    for page_index, (page_number, text) in enumerate(pages):
        if source_map is None:
            pieces = [
                (piece, None)
                for piece in splitter.split_text(text)
            ]
        else:
            documents = splitter.create_documents([text])
            pieces = [
                (
                    document.page_content,
                    document.metadata.get("start_index"),
                )
                for document in documents
            ]

            line_starts = [0]
            line_starts.extend(
                match.end()
                for match in re.finditer("\n", text)
            )

        for piece, start in pieces:
            piece = piece.strip()

            if not piece:
                continue

            chunk_index = len(chunks)

            chunks.append(
                DocumentChunk(
                    document_id=document_id,
                    chunk_index=chunk_index,
                    page_number=page_number,
                    text=piece,
                    status="pending",
                )
            )

            if source_map is not None:
                if start is None or start < 0:
                    raise ValueError(
                        "Could not locate chunk in cleaned text."
                    )

                lines = line_sources[page_index]

                first = bisect_right(line_starts, start) - 1
                last = bisect_right(
                    line_starts,
                    start + len(piece) - 1,
                ) - 1

                source_map.append({
                    "chunk_index": chunk_index,
                    "page_number": page_number,
                    "source_start_line": lines[first],
                    "source_end_line": lines[last],
                })

    return chunks


def prepare_document(
    pages: list[tuple[int | None, str]],
    document_id: str,
) -> tuple[list[DocumentChunk], dict]:
    """Clean extracted text before creating chunks."""

    cleaned = clean_pages(pages)

    source_map = []

    chunks = split_pages(
        [
            (page.page_number, page.text)
            for page in cleaned.pages
        ],
        document_id,
        line_sources=[
            page.source_lines
            for page in cleaned.pages
        ],
        source_map=source_map,
    )

    metadata = {
        "version": 1,
        "warnings": list(cleaned.warnings),
        "chunk_source_map": source_map,
    }

    return chunks, metadata

