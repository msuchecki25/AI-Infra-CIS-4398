from typing import Any

from app.retrieval.repository import InMemoryRetrievalRepository

#A temporary storage class used by the FastAPI backend 
# to test ingestion and retrieval before integrating the 
# real vector database and RAG retrieval system.
class InMemoryStore:
    def __init__(self) -> None:
        # Start with an empty temporary collection.
        self._items: list[dict[str, Any]] = []
        self._item_owners: dict[str, str | None] = {}
        self._documents: list[dict[str, Any]] = []
        self._document_contents: dict[str, bytes] = {}
        self._chunks: list[dict[str, Any]] = []
        self._system_prompts: dict[int, str] = {}
        self.retrieval_repository = InMemoryRetrievalRepository()
        self._next_chunk_id = 1

    def add(self, item: dict[str, Any], owner_id: str | None = None) -> None:
        # Add one item to the collection.
        self._items.append(item)
        self._item_owners[str(item["id"])] = owner_id

    def add_document(self, document: dict[str, Any], content: bytes) -> None:
        self._documents.append(document)
        self._document_contents[str(document["id"])] = content

    def add_chunk(self, chunk: dict[str, Any], embedding: list[float]) -> None:
        stored_chunk = dict(chunk)
        chunk_id = self._next_chunk_id
        self._next_chunk_id += 1
        stored_chunk["id"] = chunk_id
        self._chunks.append(stored_chunk)
        self.retrieval_repository.upsert(
            chunk_id=chunk_id,
            document_id=str(chunk["document_id"]),
            content=str(chunk["text"]),
            embedding=embedding,
            owner_id=chunk.get("owner_id"),
        )

    def list_items(self) -> list[dict[str, Any]]:
        # Return all stored items as a new list.
        return list(self._items)

    def recent_items(
        self,
        count: int = 3,
        owner_id: str | None = None,
    ) -> list[dict[str, Any]]:
        # Return the most recently added items.
        items = [
            item for item in self._items
            if self._item_owners.get(str(item["id"])) == owner_id
        ]
        return items[-count:]

    def list_documents(self) -> list[dict[str, Any]]:
        return list(self._documents)

    def get_document_content(self, document_id: str) -> bytes | None:
        return self._document_contents.get(document_id)

    def list_chunks(self) -> list[dict[str, Any]]:
        return list(self._chunks)

    def get_system_prompt(self, userid: int) -> str:
        return self._system_prompts.get(userid, "")

    def set_system_prompt(self, userid: int, prompt: str) -> None:
        if prompt:
            self._system_prompts[userid] = prompt
        else:
            self._system_prompts.pop(userid, None)
