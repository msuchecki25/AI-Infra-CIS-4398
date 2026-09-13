from fastapi import FastAPI

from app.api.routes import router
from app.store import InMemoryStore


def create_app() -> FastAPI:
    app = FastAPI(title="RAWBerry API Starter")
    app.state.store = InMemoryStore()
    app.include_router(router)
    return app


app = create_app()