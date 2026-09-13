from typing import Any

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
