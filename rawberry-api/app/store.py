"""User-scoped temporary repository for development and isolated tests."""
from copy import deepcopy
from datetime import datetime, timezone
from threading import RLock
from typing import Any
from uuid import uuid4

from app.conversation import CONVERSATION_TTL_SECONDS, TURN_TIMEOUT_SECONDS, describe_exchange, messages_from_turns
from app.repository import ConversationBusy, ResourceNotFound
from app.retrieval.chunk_search import search_owned_chunks


class InMemoryStore:
    def _now(self):
        return datetime.now(timezone.utc)

    def __init__(self) -> None:
        self._documents: list[dict[str, Any]] = []
        self._document_contents: dict[str, bytes] = {}
        self._chunks: list[dict[str, Any]] = []
        self._system_prompts: dict[str, str] = {}
        self._conversations: dict[str, dict[str, Any]] = {}
        self._turns: dict[str, list[dict[str, Any]]] = {}
        self._lock = RLock()


    def save_documents(self, user_id: str, documents: list[tuple[dict[str, Any], bytes, list[dict[str, Any]]]]) -> list[str]:
        prepared = deepcopy(documents)
        with self._lock:
            for document, content, chunks in prepared:
                self._documents.append({**document, 'user_id': user_id})
                self._document_contents[document['id']] = content
                self._chunks.extend({**chunk, 'document_id': document['id']} for chunk in chunks)
        return [document['embedding_status'] for document, _, _ in prepared]

    def list_documents(self, user_id: str) -> list[dict[str, Any]]:
        with self._lock:
            return deepcopy([d for d in self._documents if d.get('user_id') == user_id])

    def get_document_content(self, user_id: str, document_id: str) -> bytes:
        with self._lock:
            if not any(d['id'] == document_id for d in self.list_documents(user_id)):
                raise ResourceNotFound()
            return self._document_contents[document_id]

    def list_chunks(self, user_id: str) -> list[dict[str, Any]]:
        with self._lock:
            document_ids = {d['id'] for d in self.list_documents(user_id)}
            return deepcopy([c for c in self._chunks if c['document_id'] in document_ids])

    def search_chunks(self, user_id: str, query: str, limit: int = 3) -> list[dict[str, Any]]:
        return search_owned_chunks(user_id, self.list_chunks(user_id), query, limit)

    def get_system_prompt(self, user_id: str) -> str:
        with self._lock:
            return self._system_prompts.get(user_id, '')

    def set_system_prompt(self, user_id: str, prompt: str) -> None:
        with self._lock:
            if prompt:
                self._system_prompts[user_id] = prompt
            else:
                self._system_prompts.pop(user_id, None)

    def create_conversation(self, user_id: str, title: str) -> dict[str, Any]:
        now = self._now()
        conversation = dict(id=str(uuid4()), user_id=user_id, title=title, description=None,
                            created_at=now, updated_at=now)
        with self._lock:
            self._conversations[conversation['id']] = conversation
            self._turns[conversation['id']] = []
        return deepcopy(conversation)

    def list_conversations(self, user_id: str) -> list[dict[str, Any]]:
        with self._lock:
            return deepcopy([c for c in self._conversations.values() if c['user_id'] == user_id
                             and (self._now() - c['updated_at']).total_seconds() < CONVERSATION_TTL_SECONDS])

    def _owned_conversation(self, user_id: str, conversation_id: str) -> dict[str, Any]:
        conversation = self._conversations.get(conversation_id)
        if (conversation is None or conversation['user_id'] != user_id
                or (self._now() - conversation['updated_at']).total_seconds() >= CONVERSATION_TTL_SECONDS):
            raise ResourceNotFound()
        return conversation

    def list_messages(self, user_id: str, conversation_id: str) -> list[dict[str, Any]]:
        with self._lock:
            self._owned_conversation(user_id, conversation_id)
            return messages_from_turns(deepcopy(self._turns[conversation_id]))

    def start_turn(self, user_id: str, conversation_id: str, message: str) -> dict[str, Any]:
        with self._lock:
            conversation = self._owned_conversation(user_id, conversation_id)
            now = self._now()
            turns = self._turns[conversation_id]
            for turn in turns:
                if turn['status'] == 'pending':
                    if (now - turn['created_at']).total_seconds() < TURN_TIMEOUT_SECONDS:
                        raise ConversationBusy()
                    turn.update(status='failed', completed_at=now)
            history = deepcopy([t for t in turns if t['status'] == 'completed'][-10:])
            turn = dict(id=str(uuid4()), prompt=message, reply=None, status='pending',
                        created_at=now, completed_at=None)
            turns.append(turn)
            conversation['updated_at'] = now
            return {**deepcopy(turn), 'history': history}

    def finish_turn(self, user_id: str, conversation_id: str, turn_id: str, reply: str | None) -> None:
        with self._lock:
            conversation = self._owned_conversation(user_id, conversation_id)
            turn = next((t for t in self._turns[conversation_id] if t['id'] == turn_id), None)
            if turn is None:
                raise ResourceNotFound()
            if turn['status'] != 'pending':
                raise ConversationBusy()
            now = self._now()
            turn.update(status='completed' if reply is not None else 'failed', reply=reply, completed_at=now)
            if reply is not None and conversation['description'] is None:
                conversation['description'] = describe_exchange(turn['prompt'], reply)
            conversation['updated_at'] = now

    def purge_expired_conversations(self, batch_size: int = 500) -> int:
        if batch_size <= 0:
            raise ValueError('batch_size must be positive')
        with self._lock:
            now = self._now()
            expired = [identifier for identifier, conversation in self._conversations.items()
                       if (now - conversation['updated_at']).total_seconds() >= CONVERSATION_TTL_SECONDS
                       and not any(turn['status'] == 'pending'
                                   and (now - turn['created_at']).total_seconds() < TURN_TIMEOUT_SECONDS
                                   for turn in self._turns[identifier])][:batch_size]
            for identifier in expired:
                del self._turns[identifier]
                del self._conversations[identifier]
            return len(expired)
