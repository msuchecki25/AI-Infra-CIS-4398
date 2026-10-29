from typing import Any

# Recover crashed generations after five minutes; reject late completions.
TURN_TIMEOUT_SECONDS = 300


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
