from app.config import Settings, get_settings
from app.models import ChatRequest, ChatResponse, ItemRecord
from app.services.gemini_service import GeminiChatClient
from app.store import InMemoryStore


class ChatService:
    def __init__(
        self,
        store: InMemoryStore,
        settings: Settings | None = None,
        llm_client: GeminiChatClient | None = None,
    ) -> None:
        self.store = store
        self.settings = settings or get_settings()
        self.llm_client = llm_client or GeminiChatClient(self.settings)

    def get_recent_items(self) -> list[ItemRecord]:
        return [ItemRecord(**item) for item in self.store.recent_items(3)]

    def generate_reply_from_message(self, message: str) -> str:
        return self.llm_client.generate_reply(message)

    def generate_reply(self, request: ChatRequest) -> ChatResponse:
        return ChatResponse(
            reply=self.generate_reply_from_message(request.message),
            recent_items=self.get_recent_items(),
        )
