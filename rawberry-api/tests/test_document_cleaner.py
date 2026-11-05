
"""Tests for document cleaning and ingestion integration."""

from io import BytesIO

import pytest
from fastapi.testclient import TestClient

from app.ingestion import prepare_document
from app.main import create_app
from app.services.document_cleaner import (
    EmptyExtractedText,
    clean_pages,
)
from app.store import InMemoryStore
from pdf_samples import make_pdf

import ingestion_pipeline


def test_normalize_spaces_and_preserve_repeated_facts():
    result = clean_pages([
        (
            None,
            "  # Heading \r\n\r\n\r\n"
            "Revenue    $1200\r\n"
            "Revenue $1200",
        )
    ])

    page = result.pages[0]

    assert page.text == (
        "# Heading\n\n"
        "Revenue $1200\n"
        "Revenue $1200"
    )
    assert page.source_lines == (1, 2, 4, 5)
    assert len(result.warnings) == 1


def test_preserve_table_and_list_formatting():
    result = clean_pages([
        (
            None,
            "| Name   | Score |\n"
            "  - Nested   item",
        )
    ])

    assert result.pages[0].text == (
        "| Name   | Score |\n"
        "  - Nested   item"
    )


def test_unicode_normalization():
    result = clean_pages([
        (None, "\ufeffCafe\u0301 \u00a0 123")
    ])

    assert result.pages[0].text == "Café 123"


def test_empty_extraction_fails():
    with pytest.raises(EmptyExtractedText):
        clean_pages([
            (None, " \n\n "),
            (2, ""),
        ])


def test_pdf_pages_and_source_lines():
    chunks, metadata = prepare_document(
        [
            (1, "Alpha    first page"),
            (2, " "),
            (3, "Gamma   third page"),
        ],
        "test-document",
    )

    assert [chunk.page_number for chunk in chunks] == [1, 3]

    assert [chunk.text for chunk in chunks] == [
        "Alpha first page",
        "Gamma third page",
    ]

    assert [
        entry["page_number"]
        for entry in metadata["chunk_source_map"]
    ] == [1, 3]

    assert all(
        entry["source_start_line"] == 1
        for entry in metadata["chunk_source_map"]
    )


def test_long_text_uses_existing_chunker():
    text = " ".join(f"word{i}" for i in range(600))

    chunks, metadata = prepare_document(
        [(None, text)],
        "test-document",
    )

    assert len(chunks) > 1
    assert all(len(chunk.text) <= 900 for chunk in chunks)

    assert len(metadata["chunk_source_map"]) == len(chunks)

    assert [
        chunk.chunk_index for chunk in chunks
    ] == list(range(len(chunks)))


def test_txt_upload_cleans_text_and_preserves_bytes():
    store = InMemoryStore()

    raw = (
        b"Heading    One\r\n\r\n\r\n"
        b"Revenue    $1200\r\n"
        b"Revenue $1200"
    )

    
    with TestClient(
        create_app(store=store),
        headers={
            "X-User-ID": "alice",
            "X-Developer-Key": "test-upload-key",
        },
    ) as client:


        response = client.post(
            "/uploadedu",
            files=[
                (
                    "files",
                    ("notes.txt", raw, "text/plain"),
                )
            ],
        )

        assert response.status_code == 200, response.text

        document_id = response.json()[0]["document_id"]
        chunks = store.list_chunks("corpus:education")

        assert len(chunks) == 1
        assert chunks[0]["text"] == (
            "Heading One\n\n"
            "Revenue $1200\n"
            "Revenue $1200"
        )

        
        assert store.get_document_content(
            "corpus:education", document_id
        ) == raw


        saved = store.list_documents("corpus:education")[0]
        metadata = saved["metadata"]["cleaning"]

        assert metadata["version"] == 1
        assert metadata["chunk_source_map"] == [{
            "chunk_index": 0,
            "page_number": None,
            "source_start_line": 1,
            "source_end_line": 5,
        }]


def test_blank_txt_upload_is_rejected():
    store = InMemoryStore()

    
    with TestClient(
        create_app(store=store),
        headers={
            "X-User-ID": "alice",
            "X-Developer-Key": "test-upload-key",
        },
    ) as client:


        response = client.post(
            "/uploadedu",
            files=[
                (
                    "files",
                    ("blank.txt", b" \n\n ", "text/plain"),
                )
            ],
        )

        assert response.status_code == 400
        assert response.json()["error_code"] == (
            "EMPTY_EXTRACTED_TEXT"
        )
        assert store.list_documents("corpus:education") == []


def test_scanned_pdf_is_rejected():
    store = InMemoryStore()

    
    with TestClient(
        create_app(store=store),
        headers={
            "X-User-ID": "alice",
            "X-Developer-Key": "test-upload-key",
        },
    ) as client:


        response = client.post(
            "/uploadedu",
            files=[
                (
                    "files",
                    (
                        "scan.pdf",
                        make_pdf(""),
                        "application/pdf",
                    ),
                )
            ],
        )

        assert response.status_code == 400
        assert response.json()["error_code"] == (
            "EMPTY_EXTRACTED_TEXT"
        )
        assert store.list_documents("corpus:education") == []


def test_docx_upload_is_cleaned():
    from docx import Document

    word = Document()
    word.add_paragraph("Hello     from Word")

    buffer = BytesIO()
    word.save(buffer)

    store = InMemoryStore()

    
    with TestClient(
        create_app(store=store),
        headers={
            "X-User-ID": "alice",
            "X-Developer-Key": "test-upload-key",
        },
    ) as client:


        response = client.post(
            "/uploadedu",
            files=[
                (
                    "files",
                    (
                        "notes.docx",
                        buffer.getvalue(),
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    ),
                )
            ],
        )

        assert response.status_code == 200, response.text

        chunks = store.list_chunks("corpus:education")
        assert len(chunks) == 1
        assert chunks[0]["text"] == "Hello from Word"


def test_failed_batch_saves_nothing():
    store = InMemoryStore()

    
    with TestClient(
        create_app(store=store),
        headers={
            "X-User-ID": "alice",
            "X-Developer-Key": "test-upload-key",
        },
    ) as client:


        response = client.post(
            "/uploadedu",
            files=[
                (
                    "files",
                    ("good.txt", b"Valid text", "text/plain"),
                ),
                (
                    "files",
                    ("bad.txt", b" \n ", "text/plain"),
                ),
            ],
        )

        assert response.status_code == 400
        assert store.list_documents("corpus:education") == []
        assert store.list_chunks("corpus:education") == []


def test_batch_ingestion_uses_same_cleaning():
    store = InMemoryStore()
    raw = b"Quarterly    revenue"

    document_id = ingestion_pipeline.ingest_document(
        store,
        "alice",
        "report.txt",
        raw,
        [(None, raw.decode("utf-8"))],
    )

    assert document_id is not None

    chunks = store.list_chunks("alice")

    assert len(chunks) == 1
    assert chunks[0]["text"] == "Quarterly revenue"

    document = store.list_documents("alice")[0]

    assert document["metadata"]["cleaning"]["version"] == 1
