"""FastAPI entry point for the Chrome extension backend."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.api.routes import router
from backend.config import get_settings
from backend.service import YoutubeRagService
from backend.utils.errors import AppError
from backend.utils.logging import configure_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    app.state.rag_service = YoutubeRagService(settings)
    yield


def create_app() -> FastAPI:
    """Create an application instance suitable for uvicorn and isolated API tests."""

    app = FastAPI(title="YouTube RAG API", version="1.0.0", lifespan=lifespan)
    settings = get_settings()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[origin for origin in settings.allowed_cors_origins if "*" not in origin],
        allow_origin_regex=r"chrome-extension://.*",
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type"],
    )

    @app.exception_handler(AppError)
    async def app_error_handler(_: Request, error: AppError) -> JSONResponse:
        return JSONResponse(status_code=error.status_code, content={"error": error.code, "message": error.public_message})

    @app.exception_handler(Exception)
    async def unexpected_error_handler(_: Request, error: Exception) -> JSONResponse:
        logging.getLogger(__name__).exception("Unhandled request failure")
        return JSONResponse(
            status_code=500,
            content={"error": "internal_error", "message": "The server could not complete this request."},
        )

    app.include_router(router)
    return app


app = create_app()
