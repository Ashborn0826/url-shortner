from fastapi import FastAPI

from app.api import redirect, urls


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

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(urls.router)
    app.include_router(redirect.router)
    return app


app = create_app()