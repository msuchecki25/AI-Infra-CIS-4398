from typing import Any

#A temporary storage class used by the FastAPI backend 
# to test ingestion and retrieval before integrating the 
# real vector database and RAG retrieval system.
class InMemoryStore:
    def __init__(self) -> None:
        # Start with an empty temporary collection.
        self._items: list[dict[str, Any]] = []
        self._documents: list[dict[str, Any]] = []
        self._document_contents: dict[str, bytes] = {}
        self._chunks: list[dict[str, Any]] = []
        self._system_prompts: dict[int, str] = {}

    def add(self, item: dict[str, Any]) -> None:
        # Add one item to the collection.
        self._items.append(item)

    def add_document(self, document: dict[str, Any], content: bytes) -> None:
        self._documents.append(document)
        self._document_contents[str(document["id"])] = content

    def add_chunk(self, chunk: dict[str, Any]) -> None:
        self._chunks.append(chunk)

    def list_items(self) -> list[dict[str, Any]]:
        # Return all stored items as a new list.
        return list(self._items)

    def recent_items(self, count: int = 3) -> list[dict[str, Any]]:
        # Return the most recently added items.
        return self._items[-count:]

    def list_documents(self) -> list[dict[str, Any]]:
        return list(self._documents)

    def get_document_content(self, document_id: str) -> bytes | None:
        return self._document_contents.get(document_id)

    def list_chunks(self) -> list[dict[str, Any]]:
        return list(self._chunks)

    def search_chunks(self, query: str, limit: int = 3) -> list[dict[str, Any]]:
        if not query:
            return []

        import re

        query_terms = {
            re.sub(r"[^a-z0-9]", "", term.lower())
            for term in query.split()
            if re.sub(r"[^a-z0-9]", "", term.lower())
        }
        scored_chunks: list[tuple[float, dict[str, Any]]] = []

        for chunk in self._chunks:
            chunk_text = str(chunk.get("text", "")).lower()
            chunk_terms = {
                re.sub(r"[^a-z0-9]", "", term)
                for term in chunk_text.split()
                if re.sub(r"[^a-z0-9]", "", term)
            }
            match_count = sum(1 for term in query_terms if term in chunk_terms)
            if match_count == 0:
                continue
            score = match_count + (0.1 if chunk.get("document_id") else 0)
            scored_chunks.append((score, chunk))

        scored_chunks.sort(key=lambda item: item[0], reverse=True)
        return [chunk for _, chunk in scored_chunks[:limit]]

    def get_system_prompt(self, userid: int) -> str:
        return self._system_prompts.get(userid, "")

    def set_system_prompt(self, userid: int, prompt: str) -> None:
        if prompt:
            self._system_prompts[userid] = prompt
        else:
            self._system_prompts.pop(userid, None)
