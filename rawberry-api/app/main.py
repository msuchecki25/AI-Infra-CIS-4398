from typing import Any
from uuid import uuid4

from fastapi import Depends, FastAPI, Request, status
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = "healthy"


class ItemRecord(BaseModel):
    id: str
    text: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class RootResponse(BaseModel):
    message: str
    available_endpoints: list[str]


class GetItemsResponse(BaseModel):
    items: list[ItemRecord]
    count: int


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)


class ChatResponse(BaseModel):
    reply: str
    recent_items: list[ItemRecord]


class IngestRequest(BaseModel):
    text: str = Field(..., min_length=1)
    metadata: dict[str, Any] | None = None


class IngestResponse(BaseModel):
    message: str
    item: ItemRecord
    count: int


class InMemoryStore:
    def __init__(self) -> None:
        self._items: list[dict[str, Any]] = []

    def add(self, item: dict[str, Any]) -> None:
        self._items.append(item)

    def list_items(self) -> list[dict[str, Any]]:
        return self._items

    def recent_items(self, count: int = 3) -> list[dict[str, Any]]:
        return self._items[-count:]


def get_store(request: Request) -> InMemoryStore:
    return request.app.state.store


def create_app() -> FastAPI:
    app = FastAPI(title="RAWBerry API Starter")
    app.state.store = InMemoryStore()

    @app.get("/", response_model=RootResponse)
    def read_root() -> RootResponse:
        return RootResponse(
            message="RAWBerry API is running",
            available_endpoints=[
                "/health",
                "/get",
                "/chat",
                "/ingest",
            ],
        )

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(status="healthy")

    @app.get("/get", response_model=GetItemsResponse)
    def get_items(store: InMemoryStore = Depends(get_store)) -> GetItemsResponse:
        items = [ItemRecord(**item) for item in store.list_items()]
        return GetItemsResponse(items=items, count=len(items))

    @app.post("/chat", response_model=ChatResponse)
    def chat(request: ChatRequest, store: InMemoryStore = Depends(get_store)) -> ChatResponse:
        recent_items = [ItemRecord(**item) for item in store.recent_items(3)]
        return ChatResponse(
            reply=f"You said: {request.message}",
            recent_items=recent_items,
        )

    @app.post("/ingest", response_model=IngestResponse, status_code=status.HTTP_201_CREATED)
    def ingest(request: IngestRequest, store: InMemoryStore = Depends(get_store)) -> IngestResponse:
        item = ItemRecord(
            id=str(uuid4()),
            text=request.text,
            metadata=request.metadata or {},
        )

        store.add(item.model_dump())

        return IngestResponse(
            message="Item ingested successfully",
            item=item,
            count=len(store.list_items()),
        )

    return app


app = create_app()