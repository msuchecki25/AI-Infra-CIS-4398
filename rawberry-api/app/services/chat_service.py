import json
import logging

from app.config import Settings, get_settings
from app.repository import Repository, StorageError, ConversationBusy
from app.services.gemini_service import GeminiChatClient, MockChatClient
from app.user_models import ChatRequest, ChatResponse

logger = logging.getLogger(__name__)


class GenerationError(Exception):
    pass


class ChatService:
    def __init__(self, store: Repository, settings: Settings | None = None, llm_client=None) -> None:
        self.store = store
        self.settings = settings or get_settings()
        self.llm_client = llm_client or self._build_llm_client()

    def _build_llm_client(self):
        client = GeminiChatClient(self.settings)
        return client if client.should_use_real_client() else MockChatClient()

    def prepare_turn(self, user_id: str, request: ChatRequest) -> dict:
        return self.store.start_turn(user_id, str(request.conversation_id), request.message)

    def generate_reply(self, user_id: str, request: ChatRequest, turn: dict | None = None) -> ChatResponse:
        conversation_id = str(request.conversation_id)
        turn = turn if turn is not None else self.prepare_turn(user_id, request)
        try:
            chunks = self.store.search_chunks(user_id, request.message, limit=3)
            preferences = self.store.get_system_prompt(user_id)
            message = request.message
            if chunks:
                context = ' '.join(chunk['text'] for chunk in chunks)
                message = f'Use the following document context to answer the question: {context}. Question: {message}'
            # Only completed turns from this conversation, bounded by count and size.
            history = []
            remaining = 12000
            for previous in reversed(turn['history']):
                entry = json.dumps({'user': previous['prompt'], 'assistant': previous['reply']})
                if len(entry) > remaining:
                    break
                history.append(entry)
                remaining -= len(entry)
            if history:
                message = 'Conversation history (prior messages):\n' + '\n'.join(reversed(history)) + '\nCurrent message:\n' + message
            if preferences:
                message = f'User response preferences (follow when relevant):\n{preferences}\n\nUser message:\n{message}'
            recent = self.store.recent_items(user_id, 3)
            reply = self.llm_client.generate_reply(message)
        except Exception as exc:
            try:
                self.store.finish_turn(user_id, conversation_id, turn['id'], None)
            except (StorageError, ConversationBusy):
                logger.warning('Could not record failed generation; pending turn will expire.')
            if isinstance(exc, StorageError):
                raise
            raise GenerationError() from exc
        self.store.finish_turn(user_id, conversation_id, turn['id'], reply)
        return ChatResponse(conversation_id=conversation_id, turn_id=turn['id'], reply=reply, recent_items=recent)
