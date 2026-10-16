from typing import Annotated

from fastapi import Header, HTTPException, Request


async def require_user(
    request: Request,
    user_id: Annotated[str, Header(alias="X-User-ID", min_length=1, max_length=128, pattern=r"^[!-~]+$")],
) -> str:
    """Validate upstream identity syntax; this does not authenticate the caller."""
    if len(request.headers.getlist("x-user-id")) != 1:
        raise HTTPException(422, "Exactly one X-User-ID header is required.")
    if any(key in request.query_params for key in ("owner_id", "userid", "user_id")):
        raise HTTPException(422, "Supply identity only through X-User-ID.")
    if request.headers.get("content-type", "").startswith("multipart/form-data"):
        form = await request.form()
        if any(key in form for key in ("owner_id", "userid", "user_id")):
            raise HTTPException(422, "Supply identity only through X-User-ID.")
    return user_id
