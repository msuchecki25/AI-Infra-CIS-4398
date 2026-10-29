from typing import Any

# Recover crashed generations after five minutes; reject late completions.
TURN_TIMEOUT_SECONDS = 300
CONVERSATION_TTL_SECONDS = 24 * 60 * 60


def describe_exchange(question: str, answer: str) -> str:
    """A bounded, extractive description; no extra model call or source context."""
    def excerpt(text: str, limit: int) -> str:
        text = ' '.join(text.split())
        if len(text) <= limit:
            return text
        prefix = text[:limit - 1]
        if ' ' in prefix:
            prefix = prefix.rsplit(' ', 1)[0]
        return prefix.rstrip() + '…'

    return f'Question: {excerpt(question, 120)} Answer: {excerpt(answer, 160)}'


def messages_from_turns(turns: list[dict[str, Any]]) -> list[dict[str, Any]]:
    messages = []
    for turn in turns:
        base = {"turn_id": turn["id"], "status": turn["status"]}
        messages.append({**base, "id": turn["id"] + ":user", "role": "user",
                         "content": turn["prompt"], "created_at": turn["created_at"]})
        if turn["status"] == "completed":
            messages.append({**base, "id": turn["id"] + ":assistant", "role": "assistant",
                             "content": turn["reply"], "created_at": turn["completed_at"]})
    return messages
