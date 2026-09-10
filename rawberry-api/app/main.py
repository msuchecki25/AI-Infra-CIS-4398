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
def read_root():
    return {
        "message": "RAWBerry API is running",
        "available_endpoints": [
            "/health",
            "/documents",
            "/chat",
            "/ingest",
        ],
    }


@app.get("/health")
def health():
    return {
        "status": "healthy"
    }


@app.get("/documents")
def get_documents():
    return {
        "items": memory_store,
        "count": len(memory_store),
    }


@app.post("/chat")
def chat(request: ChatRequest):
    return {
        "reply": f"You said: {request.message}",
        "recent_items": memory_store[-3:],
    }


@app.post("/ingest")
def ingest(request: IngestRequest):
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