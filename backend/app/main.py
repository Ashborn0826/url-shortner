from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import redirect, urls
from app.config import settings


def create_app() -> FastAPI:
    # FastAPI's default /docs, /redoc, /openapi.json are moved to
    # /_internal/* so they don't shadow root-level short-code redirects.
    # Otherwise "docs" / "redoc" / "openapi" would be unreachable as
    # custom short codes — they'd return Swagger UI HTML instead of 302.
    app = FastAPI(
        title="URL Shortener",
        version="0.1.0",
        docs_url="/_internal/docs",
        redoc_url="/_internal/redoc",
        openapi_url="/_internal/openapi.json",
    )

    # CORS for the React frontend (Vite dev server on :5173).
    # In production both apps live behind the same domain and CORS is
    # not needed; this is a dev convenience.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(urls.router)
    app.include_router(redirect.router)
    return app


app = create_app()