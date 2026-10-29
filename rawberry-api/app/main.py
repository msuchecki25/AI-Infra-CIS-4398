import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.config import get_settings
from app.repository import ConversationBusy, Repository, ResourceNotFound, StorageError
from app.services.chat_service import GenerationError
from app.store import InMemoryStore


# Create the FastAPI app, shared store, and routes.
def create_app(store: Repository | None = None) -> FastAPI:
    if store is None:
        database_url = get_settings().database_url
        if database_url:
            from app.postgres_repository import PostgresRepository
            store = PostgresRepository(database_url)
        else:
            store = InMemoryStore()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        check_ready = getattr(app.state.store, "check_ready", None)
        if check_ready is not None:
            await asyncio.to_thread(check_ready)
        yield

    app = FastAPI(title="RAWBerry API Starter", lifespan=lifespan)
    app.state.store = store

    @app.exception_handler(ResourceNotFound)
    async def not_found_handler(request: Request, exc: ResourceNotFound) -> JSONResponse:
        return JSONResponse(status_code=404, content={"success": False, "error_code": "NOT_FOUND", "message": "Resource not found."})

    @app.exception_handler(ConversationBusy)
    async def busy_handler(request: Request, exc: ConversationBusy) -> JSONResponse:
        return JSONResponse(status_code=409, content={"success": False, "error_code": "CONVERSATION_BUSY", "message": "Conversation generation is pending or this turn has expired."})

    @app.exception_handler(GenerationError)
    async def generation_handler(request: Request, exc: GenerationError) -> JSONResponse:
        return JSONResponse(status_code=502, content={"success": False, "error_code": "GENERATION_FAILED", "message": "The response could not be generated."})

    @app.exception_handler(StorageError)
    async def storage_exception_handler(request: Request, exc: StorageError) -> JSONResponse:
        return JSONResponse(status_code=503, content={
            "success": False,
            "error_code": "STORAGE_UNAVAILABLE",
            "message": "Storage is temporarily unavailable.",
        })

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
