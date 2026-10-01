from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.store import InMemoryStore


# Create the FastAPI app, shared store, and routes.
def create_app() -> FastAPI:
    app = FastAPI(title="RAWBerry API Starter")
    app.state.store = InMemoryStore()

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        detail = exc.detail
        if isinstance(detail, dict) and "success" in detail:
            return JSONResponse(status_code=exc.status_code, content=detail)
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "error_code": "HTTP_ERROR",
                "message": str(detail),
            },
        )

    app.include_router(router)
    return app


app = create_app()