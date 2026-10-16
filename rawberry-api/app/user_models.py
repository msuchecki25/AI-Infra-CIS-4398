"""User-scoped contracts; identity is supplied by the trusted upstream service."""
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class IngestRequest(RequestModel):
    text: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DocumentRecord(BaseModel):
    id: str
    user_id: str
    filename: str
    file_type: str
    size_bytes: int
    chunk_count: int = 0
    embedding_status: str = "pending"
    metadata: dict[str, Any] = Field(default_factory=dict)


class DocumentChunk(BaseModel):
    document_id: str
    chunk_index: int
    page_number: int | None = None
    text: str
    status: str = "pending"


class SystemPromptRequest(RequestModel):
    prompt: str = Field(default="", max_length=2000)


class SystemPromptResponse(BaseModel):
    user_id: str
    prompt: str


class ConversationRequest(RequestModel):
    title: str = Field(default="New conversation", min_length=1, max_length=200)


class ConversationRecord(BaseModel):
    id: str
    user_id: str
    title: str
    created_at: datetime
    updated_at: datetime


class ChatRequest(RequestModel):
    conversation_id: UUID
    message: str = Field(min_length=1, max_length=20000)


class ChatResponse(BaseModel):
    conversation_id: str
    turn_id: str
    reply: str
    recent_items: list[dict[str, Any]]


class ChatStatusEvent(BaseModel):
    request_id: str
    status: Literal["received", "generating", "completed", "failed"]
    message: str
    response: ChatResponse | None = None


class MessageRecord(BaseModel):
    id: str
    turn_id: str
    role: Literal["user", "assistant"]
    content: str
    status: Literal["pending", "completed", "failed"]
    created_at: datetime
