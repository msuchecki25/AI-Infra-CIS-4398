import asyncio
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import StreamingResponse

from app.models import GetItemsResponse, HealthResponse, IngestResponse, ItemRecord, RootResponse, UploadErrorResponse, UploadResponse
from app.repository import Repository
from app.services.chat_service import ChatService
from app.services.ingest_service import IngestService
from app.user_context import require_user
from app.user_models import (ChatRequest, ChatResponse, ChatStatusEvent, ConversationRecord,
                             ConversationRequest, DocumentRecord, IngestRequest, MessageRecord,
                             SystemPromptRequest, SystemPromptResponse)

router = APIRouter()
User = Annotated[str, Depends(require_user)]


def get_store(request: Request) -> Repository:
    return request.app.state.store


def get_chat_service(store: Repository = Depends(get_store)) -> ChatService:
    return ChatService(store)


def get_ingest_service(store: Repository = Depends(get_store)) -> IngestService:
    return IngestService(store)


@router.get('/', response_model=RootResponse)
def read_root() -> RootResponse:
    return RootResponse(message='RAWBerry API is running', available_endpoints=[
        '/health', '/get', '/documents', '/upload', '/ingest', '/chat', '/chat/stream',
        '/me/system-prompt', '/conversations', '/conversations/{conversation_id}/messages',
    ])


@router.get('/health', response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status='healthy')


@router.get('/get', response_model=GetItemsResponse)
def get_items(user_id: User, store: Repository = Depends(get_store)) -> GetItemsResponse:
    items = [ItemRecord(**item) for item in store.list_items(user_id)]
    return GetItemsResponse(items=items, count=len(items))


@router.get('/documents', response_model=list[DocumentRecord])
def get_documents(user_id: User, store: Repository = Depends(get_store)):
    return store.list_documents(user_id)


@router.post('/ingest', response_model=IngestResponse, status_code=201)
def ingest(request: IngestRequest, user_id: User, service: IngestService = Depends(get_ingest_service)):
    return service.ingest(user_id, request)


@router.post('/upload', response_model=list[UploadResponse], responses={
    400: {'model': UploadErrorResponse}, 413: {'model': UploadErrorResponse},
})
def upload_document(
    user_id: User,
    files: Annotated[list[UploadFile], File(..., json_schema_extra={'items': {'type': 'string', 'format': 'binary'}})],
    service: IngestService = Depends(get_ingest_service),
):
    return service.upload_document(user_id, files)


@router.get('/me/system-prompt', response_model=SystemPromptResponse)
def get_system_prompt(user_id: User, store: Repository = Depends(get_store)):
    return SystemPromptResponse(user_id=user_id, prompt=store.get_system_prompt(user_id))


@router.put('/me/system-prompt', response_model=SystemPromptResponse)
def set_system_prompt(request: SystemPromptRequest, user_id: User, store: Repository = Depends(get_store)):
    prompt = request.prompt.strip()
    store.set_system_prompt(user_id, prompt)
    return SystemPromptResponse(user_id=user_id, prompt=prompt)


@router.post('/conversations', response_model=ConversationRecord, status_code=201)
def create_conversation(request: ConversationRequest, user_id: User, store: Repository = Depends(get_store)):
    return store.create_conversation(user_id, request.title)


@router.get('/conversations', response_model=list[ConversationRecord])
def list_conversations(user_id: User, store: Repository = Depends(get_store)):
    return store.list_conversations(user_id)


@router.get('/conversations/{conversation_id}/messages', response_model=list[MessageRecord])
def list_messages(conversation_id: UUID, user_id: User, store: Repository = Depends(get_store)):
    return store.list_messages(user_id, str(conversation_id))


@router.post('/chat', response_model=ChatResponse)
def chat(request: ChatRequest, user_id: User, service: ChatService = Depends(get_chat_service)):
    return service.generate_reply(user_id, request)


@router.post('/chat/stream', response_class=StreamingResponse,
             responses={200: {'content': {'text/event-stream': {}}}})
def chat_stream(request: ChatRequest, user_id: User, service: ChatService = Depends(get_chat_service)):
    # Verify ownership and reserve the turn before committing the HTTP 200 stream.
    turn = service.prepare_turn(user_id, request)
    request_id = str(uuid4())

    async def events():
        for status, message in [('received', 'Your message was received.'), ('generating', 'Generating a response.')]:
            yield _format_status_event(ChatStatusEvent(request_id=request_id, status=status, message=message))
        try:
            response = await asyncio.to_thread(service.generate_reply, user_id, request, turn)
        except Exception:
            yield _format_status_event(ChatStatusEvent(request_id=request_id, status='failed',
                                                       message='The response could not be generated.'))
            return
        yield _format_status_event(ChatStatusEvent(request_id=request_id, status='completed',
                                                   message='Response complete.', response=response))

    return StreamingResponse(events(), media_type='text/event-stream',
                             headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})


def _format_status_event(event: ChatStatusEvent) -> str:
    return f'event: status\ndata: {event.model_dump_json()}\n\n'
