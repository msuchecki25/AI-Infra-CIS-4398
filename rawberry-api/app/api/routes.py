from fastapi import APIRouter, Depends, Request, status

from app.models import (
    ChatRequest,
    ChatResponse,
    GetItemsResponse,
    HealthResponse,
    IngestRequest,
    IngestResponse,
    ItemRecord,
    RootResponse,
)
from app.services.chat_service import ChatService
from app.services.ingest_service import IngestService
from app.store import InMemoryStore

router = APIRouter()


def get_store(request: Request) -> InMemoryStore:
    return request.app.state.store


def get_chat_service(store: InMemoryStore = Depends(get_store)) -> ChatService:
    return ChatService(store)


def get_ingest_service(store: InMemoryStore = Depends(get_store)) -> IngestService:
    return IngestService(store)


@router.get("/", response_model=RootResponse)
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


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="healthy")


@router.get("/get", response_model=GetItemsResponse)
def get_items(store: InMemoryStore = Depends(get_store)) -> GetItemsResponse:
    items = [ItemRecord(**item) for item in store.list_items()]
    return GetItemsResponse(items=items, count=len(items))


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest, service: ChatService = Depends(get_chat_service)) -> ChatResponse:
    return service.generate_reply(request)


@router.post("/ingest", response_model=IngestResponse, status_code=status.HTTP_201_CREATED)
def ingest(request: IngestRequest, service: IngestService = Depends(get_ingest_service)) -> IngestResponse:
    return service.ingest(request)
