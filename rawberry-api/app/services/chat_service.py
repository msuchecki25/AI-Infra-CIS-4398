from app.config import Settings, get_settings
from app.models import ChatRequest, ChatResponse, ItemRecord
from app.services.gemini_service import GeminiChatClient, MockChatClient
from app.store import InMemoryStore

#API team works on this service 
# this class is responsible for handling chat requests and generating responses 
# using either the Gemini client or a mock client.
#this class is currently missing the RAG retrieval and vector database integration 
# (to send the recent items to the LLM for context), 
# which will be added in the future.
class ChatService:
    def __init__(
        self,
        store: InMemoryStore,
        settings: Settings | None = None,
        llm_client=None,
    ) -> None:
        # Prepare storage, settings, and the selected chat client.
        self.store = store
        self.settings = settings or get_settings()
        self.llm_client = llm_client or self._build_llm_client()

    def _build_llm_client(self):
        # Use Gemini when configured; otherwise use the local mock client.
        if GeminiChatClient(self.settings).should_use_real_client():
            return GeminiChatClient(self.settings)
        return MockChatClient()

    def get_recent_items(self) -> list[ItemRecord]:
        # Return the three most recently ingested items.
        # This will be done through a vector database and RAG retrieval in the future.
        return [ItemRecord(**item) for item in self.store.recent_items(3)]

    def get_relevant_chunks(self, message: str, limit: int = 3) -> list[str]:
        chunks = self.store.search_chunks(message, limit=limit)
        return [str(chunk.get("text", "")).strip() for chunk in chunks if str(chunk.get("text", "")).strip()]

    def generate_reply_from_message(self, message: str, context_chunks: list[str] | None = None, system_prompt: str = "") -> str:
        if context_chunks:
            retrieved_context = " ".join(context_chunks)
            message = f"Use the following document context to answer the question: {retrieved_context}. Question: {message}"
        if system_prompt:
            message = (
                "User response preferences (follow when relevant):\n"
                f"{system_prompt}\n\n"
                f"User message:\n{message}"
            )
        return self.llm_client.generate_reply(message)

    def generate_reply(self, request: ChatRequest) -> ChatResponse:
        context_chunks = self.get_relevant_chunks(request.message)
        reply = self.generate_reply_from_message(
            request.message,
            context_chunks=context_chunks,
            system_prompt=self.store.get_system_prompt(request.userid),
        )

        # Return the reply along with recent stored items.
        return ChatResponse(
            reply=reply,
            recent_items=self.get_recent_items(),
        )
