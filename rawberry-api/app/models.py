"""Shared response models and aliases for the canonical user-scoped contracts.

Keep request/session definitions in user_models.py; these aliases ensure older
import locations use the same contract rather than defining conflicting versions.
Authentication and account models belong to the upstream application.
"""
from pydantic import BaseModel

from app.user_models import (
    ChatRequest, ChatResponse, ChatStatusEvent, ConversationRecord,
    ConversationRequest, DocumentChunk, DocumentRecord, MessageRecord,
    SystemPromptRequest, SystemPromptResponse,
)


class HealthResponse(BaseModel):
    status: str = "healthy"


class RootResponse(BaseModel):
    message: str
    available_endpoints: list[str]


class UploadResponse(BaseModel):
    success: bool
    document_id: str
    filename: str
    status: str
    chunk_count: int
    message: str
    embedding_status: str = "pending"


class UploadErrorResponse(BaseModel):
    success: bool = False
    error_code: str
    message: str
