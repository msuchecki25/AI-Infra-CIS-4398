from typing import Any


class InMemoryStore:
    def __init__(self) -> None:
        self._items: list[dict[str, Any]] = []

    def add(self, item: dict[str, Any]) -> None:
        self._items.append(item)

    def list_items(self) -> list[dict[str, Any]]:
        return list(self._items)

    def recent_items(self, count: int = 3) -> list[dict[str, Any]]:
        return self._items[-count:]
