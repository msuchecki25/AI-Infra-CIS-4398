from uuid import uuid4

from app.models import IngestRequest, IngestResponse, ItemRecord
from app.store import InMemoryStore

#DB team will eventually replace this service with a more robust ingestion service 
# that handles chunking, vectorization, and RAG retrieval. For now, this service 
# simply saves the ingested text to an in-memory store.
class IngestService:
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
