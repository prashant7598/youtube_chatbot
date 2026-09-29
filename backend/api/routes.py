"""HTTP endpoints; all exceptions are converted to safe browser-facing messages."""

from __future__ import annotations

from fastapi import APIRouter, Request

from backend.api.schemas import (
    ChatRequest,
    ChatResponse,
    HealthResponse,
    ResetRequest,
    ResetResponse,
    RetrievalInfo,
    SourceResponse,
    VideoLoadRequest,
    VideoLoadResponse,
)
from backend.service import YoutubeRagService

router = APIRouter(prefix="/api")


def service_for(request: Request) -> YoutubeRagService:
    return request.app.state.rag_service


@router.get("/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    settings = service_for(request).settings
    return HealthResponse(
        status="ok",
        environment=settings.environment,
        pinecone_configured=settings.pinecone_api_key is not None,
        huggingface_configured=settings.hf_token is not None,
        langsmith_tracing=settings.langsmith_tracing and settings.langsmith_api_key is not None,
    )


@router.post("/video/load", response_model=VideoLoadResponse)
async def load_video(payload: VideoLoadRequest, request: Request) -> VideoLoadResponse:
    result = await service_for(request).load_video(
        payload.video_value,
        payload.title,
        transcript_segments=payload.transcript_segments,
        transcript_language=payload.transcript_language,
    )
    return VideoLoadResponse(**result)


@router.post("/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest, request: Request) -> ChatResponse:
    result = await service_for(request).chat(payload.video_id, payload.question, payload.session_id, payload.video_title)
    return ChatResponse(
        answer=result.answer,
        sources=[SourceResponse(**source.__dict__) for source in result.sources],
        video_id=payload.video_id,
        session_id=payload.session_id,
        retrieval_info=RetrievalInfo(
            strategy=result.route,
            num_candidates=result.num_candidates,
            queries=result.queries,
            latency_ms=result.retrieval_latency_ms,
        ),
    )


@router.post("/reset", response_model=ResetResponse)
async def reset(payload: ResetRequest, request: Request) -> ResetResponse:
    return ResetResponse(cleared_scopes=service_for(request).reset(payload.session_id, payload.video_id))
