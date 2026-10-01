import asyncio
from uuid import uuid4

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile, status
from fastapi.responses import StreamingResponse

from app.models import (
    ChatRequest,
    ChatResponse,
    ChatStatusEvent,
    GetItemsResponse,
    HealthResponse,
    IngestRequest,
    IngestResponse,
    ItemRecord,
    RootResponse,
<<<<<<< HEAD
    UploadErrorResponse,
    UploadResponse,
=======
    SystemPromptRequest,
    SystemPromptResponse,
>>>>>>> feature/user-system-prompts
)
from app.services.chat_service import ChatService
from app.services.ingest_service import IngestService
from app.store import InMemoryStore

router = APIRouter()


# Get the shared in-memory store from the FastAPI application.
def get_store(request: Request) -> InMemoryStore:
    return request.app.state.store


# Create the chat service using the shared store.
def get_chat_service(store: InMemoryStore = Depends(get_store)) -> ChatService:
    return ChatService(store)


# Create the ingestion service using the shared store.
def get_ingest_service(store: InMemoryStore = Depends(get_store)) -> IngestService:
    return IngestService(store)


@router.get("/", response_model=RootResponse)
# Report that the API is running and list its endpoints.
def read_root() -> RootResponse:
    return RootResponse(
        message="RAWBerry API is running",
        available_endpoints=[
            "/health",
            "/get",
            "/chat",
            "/chat/stream",
            "/ingest",
        ],
    )


@router.get("/health", response_model=HealthResponse)
# Return a healthy status for health checks.
def health() -> HealthResponse:
    return HealthResponse(status="healthy")

#temporary way to get items from the store, will be replaced with RAG retrieval and 
# vector database integration in the future
@router.get("/get", response_model=GetItemsResponse)
# Return all items currently stored in memory.
def get_items(store: InMemoryStore = Depends(get_store)) -> GetItemsResponse:
    items = [ItemRecord(**item) for item in store.list_items()]
    return GetItemsResponse(items=items, count=len(items))


@router.post("/chat", response_model=ChatResponse)
# Generate a response to the user's chat message.
def chat(request: ChatRequest, service: ChatService = Depends(get_chat_service)) -> ChatResponse:
    return service.generate_reply(request)


<<<<<<< HEAD
@router.post(
    "/chat/stream",
    response_class=StreamingResponse,
    responses={200: {"content": {"text/event-stream": {}}}},
)
def chat_stream(request: ChatRequest, service: ChatService = Depends(get_chat_service)) -> StreamingResponse:
    request_id = str(uuid4())

    async def events():
        yield _format_status_event(
            ChatStatusEvent(
                request_id=request_id,
                status="received",
                message="Your message was received.",
            )
        )
        yield _format_status_event(
            ChatStatusEvent(
                request_id=request_id,
                status="generating",
                message="Generating a response.",
            )
        )
        try:
            response = await asyncio.to_thread(service.generate_reply, request)
        except Exception:
            yield _format_status_event(
                ChatStatusEvent(
                    request_id=request_id,
                    status="failed",
                    message="The response could not be generated.",
                )
            )
            return

        yield _format_status_event(
            ChatStatusEvent(
                request_id=request_id,
                status="completed",
                message="Response complete.",
                response=response,
            )
        )

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _format_status_event(event: ChatStatusEvent) -> str:
    return f"event: status\ndata: {event.model_dump_json()}\n\n"
=======
@router.get("/users/{userid}/system-prompt", response_model=SystemPromptResponse)
def get_system_prompt(userid: int, store: InMemoryStore = Depends(get_store)) -> SystemPromptResponse:
    return SystemPromptResponse(userid=userid, prompt=store.get_system_prompt(userid))


@router.put("/users/{userid}/system-prompt", response_model=SystemPromptResponse)
def set_system_prompt(
    userid: int,
    request: SystemPromptRequest,
    store: InMemoryStore = Depends(get_store),
) -> SystemPromptResponse:
    prompt = request.prompt.strip()
    store.set_system_prompt(userid, prompt)
    return SystemPromptResponse(userid=userid, prompt=prompt)
>>>>>>> feature/user-system-prompts


@router.post("/ingest", response_model=IngestResponse, status_code=status.HTTP_201_CREATED)
# Store the submitted text and return the new item.
def ingest(request: IngestRequest, service: IngestService = Depends(get_ingest_service)) -> IngestResponse:
    return service.ingest(request)


@router.post(
    "/upload",
    response_model=list[UploadResponse],
    responses={
        400: {"model": UploadErrorResponse},
        413: {"model": UploadErrorResponse},
    },
)
def upload_document(
    files: Annotated[list[UploadFile], File(...)],
    owner_id: Annotated[str | None, Form()] = None,
    service: IngestService = Depends(get_ingest_service),
) -> list[UploadResponse]:
    return service.upload_document(files, owner_id=owner_id)
