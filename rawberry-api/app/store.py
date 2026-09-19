from typing import Any

#A temporary storage class used by the FastAPI backend 
# to test ingestion and retrieval before integrating the 
# real vector database and RAG retrieval system.
class InMemoryStore:
    def __init__(self) -> None:
        # Start with an empty temporary collection.
        self._items: list[dict[str, Any]] = []

    def add(self, item: dict[str, Any]) -> None:
        # Add one item to the collection.
        self._items.append(item)

    def list_items(self) -> list[dict[str, Any]]:
        # Return all stored items as a new list.
        return list(self._items)

    def recent_items(self, count: int = 3) -> list[dict[str, Any]]:
        # Return the most recently added items.
        return self._items[-count:]
