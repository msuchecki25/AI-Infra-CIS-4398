import re
from typing import Any


def rank_chunks(chunks: list[dict[str, Any]], query: str, limit: int) -> list[dict[str, Any]]:
    """Prototype keyword ranking, applied only to already owner-filtered chunks."""
    def terms(text: str) -> set[str]:
        return {term for part in text.lower().split() if (term := re.sub(r"[^a-z0-9]", "", part))}

    if limit <= 0:
        return []
    query_terms = terms(query)
    scored = [(len(query_terms & terms(chunk["text"])), chunk) for chunk in chunks]
    scored = [(score, chunk) for score, chunk in scored if score > 0]
    scored.sort(key=lambda entry: entry[0], reverse=True)
    return [chunk for _, chunk in scored[:limit]]
