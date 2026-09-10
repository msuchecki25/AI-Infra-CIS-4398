from typing import Any
from uuid import uuid4

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="RAWBerry API Starter")


class ChatRequest(BaseModel):
    message: str


class IngestRequest(BaseModel):
    text: str
    metadata: dict[str, Any] | None = None


memory_store: list[dict[str, Any]] = []


@app.get("/")
def read_root() -> dict[str, Any]:
    return {
        "message": "RAWBerry API is running",
        "available_endpoints": [
            "/health",
            "/get",
            "/chat",
            "/ingest",
        ],
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "healthy"
    }


@app.get("/get")
def get_items() -> dict[str, Any]:
    return {
        "items": memory_store,
        "count": len(memory_store),
    }


@app.post("/chat")
def chat(request: ChatRequest) -> dict[str, Any]:
    return {
        "reply": f"You said: {request.message}",
        "recent_items": memory_store[-3:],
    }


@app.post("/ingest")
def ingest(request: IngestRequest) -> dict[str, Any]:
    item = {
        "id": str(uuid4()),
        "text": request.text,
        "metadata": request.metadata or {},
    }

    memory_store.append(item)

    return {
        "message": "Item ingested successfully",
        "item": item,
        "count": len(memory_store),
    }