from app.config import Settings, get_settings
from app.models import ChatRequest, ChatResponse, ItemRecord
from app.retrieval.embeddings import HashEmbeddingProvider
from app.retrieval.service import RetrievalService
from app.services.gemini_service import GeminiChatClient, MockChatClient
from app.store import InMemoryStore


class ChatService:
    def __init__(
        self,
        store: InMemoryStore,
        settings: Settings | None = None,
        llm_client=None,
    ) -> None:
        self.store = store
        self.settings = settings or get_settings()
        self.llm_client = llm_client or self._build_llm_client()
        self.retrieval_service = RetrievalService(
            HashEmbeddingProvider(),
            store.retrieval_repository,
        )

    def _build_llm_client(self):
        if GeminiChatClient(self.settings).should_use_real_client():
            return GeminiChatClient(self.settings)
        return MockChatClient()

    def get_recent_items(self, owner_id: str | None = None) -> list[ItemRecord]:
        return [
            ItemRecord(**item)
            for item in self.store.recent_items(3, owner_id=owner_id)
        ]

    def get_relevant_chunks(
        self,
        message: str,
        limit: int = 3,
        owner_id: str | None = None,
    ) -> list[str]:
        return [
            result.content
            for result in self.retrieval_service.retrieve(
                message,
                limit=limit,
                owner_id=owner_id,
            )
        ]

    def generate_reply_from_message(
        self,
        message: str,
        context_chunks: list[str] | None = None,
        system_prompt: str = "",
    ) -> str:
        prompt_parts: list[str] = []
        if system_prompt:
            prompt_parts.append(
                "User response preferences (follow when relevant):\n" + system_prompt
            )
        if context_chunks:
            prompt_parts.append(
                "Use the following document context to answer the question. "
                "If it does not contain the answer, say so.\n"
                + "\n\n".join(context_chunks)
            )
        prompt_parts.append(("User question:\n" if prompt_parts else "") + message)
        return self.llm_client.generate_reply("\n\n".join(prompt_parts))

    def generate_reply(self, request: ChatRequest) -> ChatResponse:
        context_chunks = self.get_relevant_chunks(
            request.message,
            owner_id=str(request.userid),
        )
        reply = self.generate_reply_from_message(
            request.message,
            context_chunks=context_chunks,
            system_prompt=self.store.get_system_prompt(request.userid),
        )
        return ChatResponse(
            reply=reply,
            recent_items=self.get_recent_items(owner_id=str(request.userid)),
        )
