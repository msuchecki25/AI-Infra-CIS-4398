from uuid import uuid4

from app.models import IngestRequest, IngestResponse, ItemRecord
from app.store import InMemoryStore


class IngestService:
    def __init__(self, store: InMemoryStore) -> None:
        self.store = store

    def ingest(self, request: IngestRequest) -> IngestResponse:
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
