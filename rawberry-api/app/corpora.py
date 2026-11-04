"""Shared corpus scopes reuse repository owner filtering independently of chat owners."""
import os
import secrets
from typing import Annotated

from fastapi import Header, HTTPException

from app.user_models import ChatDomain


def corpus_owner(domain: ChatDomain) -> str:
    if domain not in ("medical", "education"):
        raise ValueError("Unknown corpus")
    return "corpus:" + domain


def require_developer(api_key: Annotated[str | None, Header(alias="X-Developer-Key")] = None) -> None:
    expected = os.getenv("DEVELOPER_UPLOAD_API_KEY", "")
    if not expected:
        raise HTTPException(503, "Developer uploads are not configured.")
    if not api_key or not secrets.compare_digest(api_key.encode(), expected.encode()):
        raise HTTPException(403, "Developer credentials required.")
