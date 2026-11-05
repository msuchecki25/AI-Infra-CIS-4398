import argparse
import os
import re
from uuid import uuid4

from app.ingestion import prepare_document
from app.services.document_cleaner import EmptyExtractedText


# app resolves to rawberry-api/app through the repository-level app package
from app.config import get_settings
# the /upload endpoint uses the same file rules, extraction and chunking
from app.ingestion import (ALLOWED_EXTENSIONS, MAX_FILE_SIZE_BYTES, InvalidFileContent,
                           UnreadableDocument, extract_pages, split_pages)
from app.postgres_repository import PostgresRepository
from app.user_models import DocumentRecord

# same owner rule as the user_id CHECK constraint in migration 002
USER_ID_PATTERN = re.compile(r"^[!-~]{1,128}$")


#updated later to fit final format from front end team
def load_documents(doc_path="testdocs"):
    print(f"loading all documents from directory {doc_path}...")

    # check if directory exists
    if not os.path.exists(doc_path):
        raise FileNotFoundError(f"The directory {doc_path} does not exist")

    # each document is (path, raw bytes, [(page_number, text), ...])
    # raw bytes are kept because document_content stores the original file
    documents = []
    for filename in sorted(os.listdir(doc_path)):
        path = os.path.join(doc_path, filename)
        ext = os.path.splitext(filename)[1].lower()
        if not os.path.isfile(path) or ext not in ALLOWED_EXTENSIONS:
            continue
        # same files the /upload endpoint rejects, skipped so one bad file doesn't stop the batch
        if os.path.getsize(path) > MAX_FILE_SIZE_BYTES:
            print(f"Skipping {path}, larger than the {MAX_FILE_SIZE_BYTES // (1024 * 1024)}MB limit")
            continue
        with open(path, "rb") as file:
            raw_bytes = file.read()
        if not raw_bytes:
            print(f"Skipping empty file {path}")
            continue
        try:
            pages = extract_pages(ext, raw_bytes)
        except (InvalidFileContent, UnicodeDecodeError, UnreadableDocument):
            print(f"Skipping unreadable file {path}")
            continue
        documents.append((path, raw_bytes, pages))

    # ensure documents actually contains documents
    if len(documents) == 0:
        raise FileNotFoundError(f"No {', '.join(ALLOWED_EXTENSIONS)} files found in {doc_path} directory. Add files first.")

    # output checks, shows first 2 docs
    for i, (path, raw_bytes, pages) in enumerate(documents[:2]):
        print(f"Document{i+1}")
        print(f" Source {path} ({len(raw_bytes)} bytes, {len(pages)} page(s))")
    return documents


def split_documents(pages, document_id):
    print("Splitting documents into chunks...")
    # 900 char chunks with 100 char overlap, split page by page so every chunk keeps its page number
    return split_pages(pages, document_id)


def ingest_document(repository, user_id, path, raw_bytes, pages):
 
    document_id = str(uuid4())

    try:
        chunks, cleaning_metadata = prepare_document(
            pages, document_id
        )
    except EmptyExtractedText:
        print(f"No readable text extracted from {path}, skipping")
        return None


    document = DocumentRecord(
        id=document_id,
        user_id=user_id,
        filename=os.path.basename(path),
        file_type=os.path.splitext(path)[1].lower(),
        size_bytes=len(raw_bytes),
        chunk_count=len(chunks),
        embedding_status="pending",
        
        metadata={
            "source": "ingestion_pipeline",
            "path": path,
            "cleaning": cleaning_metadata,
        },

    )
    # same (document, bytes, chunks) shape the /upload endpoint saves
    # the repository embeds every chunk with the pinned Vertex model before writing,
    # so a failed embedding leaves no partial rows
    statuses = repository.save_documents(user_id, [(document.model_dump(), raw_bytes, [c.model_dump() for c in chunks])])
    print(f"Ingested {document.filename}: {len(chunks)} chunks, embedding {statuses[0]}, document id {document_id}")
    return document_id


def main():
    from dotenv import load_dotenv
    load_dotenv()

    parser = argparse.ArgumentParser(description="Load, chunk, and embed documents into the RAWBerry database.")
    parser.add_argument("--doc-path", default="testdocs")
    parser.add_argument("--user-id", default=os.getenv("INGEST_USER_ID"),
                        help="owner of the documents, the same value the API receives as X-User-ID")
    args = parser.parse_args()

    if not args.user_id or not USER_ID_PATTERN.match(args.user_id):
        parser.error("--user-id (or INGEST_USER_ID) must be 1-128 printable ASCII characters with no spaces")
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        parser.error("DATABASE_URL must be set")
    # embeddings go through Vertex AI with Application Default Credentials
    if not get_settings().google_cloud_project:
        parser.error("GOOGLE_CLOUD_PROJECT must be set for Vertex AI embeddings")

    repository = PostgresRepository(database_url)
    repository.check_ready()

    #loading documents
    documents = load_documents(doc_path=args.doc_path)
    for path, raw_bytes, pages in documents:
        ingest_document(repository, args.user_id, path, raw_bytes, pages)


# ensures that this file only runs when it is ran directly not when imported by another file
if __name__ == "__main__":
    main()
