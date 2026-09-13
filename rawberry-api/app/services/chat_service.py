from app.models import ChatRequest, ChatResponse, ItemRecord
from app.store import InMemoryStore


class ChatService:
    def __init__(self, store: InMemoryStore) -> None:
        self.store = store

    def get_recent_items(self) -> list[ItemRecord]:
        return [ItemRecord(**item) for item in self.store.recent_items(3)]

    def generate_reply(self, request: ChatRequest) -> ChatResponse:
        return ChatResponse(
            reply=f"You said: {request.message}",
            recent_items=self.get_recent_items(),
        )
