"""Browser-safe request and response models."""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator


class TranscriptSegmentRequest(BaseModel):
    """A timestamped caption segment read from the active YouTube tab."""

    text: str = Field(min_length=1, max_length=4000)
    start_time: float = Field(ge=0)
    duration: float = Field(ge=0, le=3600)


class VideoLoadRequest(BaseModel):
    video_url: str | None = Field(default=None, max_length=2048)
    video_id: str | None = Field(default=None, max_length=32)
    title: str = Field(default="", max_length=300)
    transcript_language: str | None = Field(default=None, max_length=32)
    transcript_segments: list[TranscriptSegmentRequest] | None = Field(default=None, max_length=6000)

    @model_validator(mode="after")
    def has_video_reference(self) -> "VideoLoadRequest":
        if not self.video_url and not self.video_id:
            raise ValueError("video_url or video_id is required")
        return self

    @property
    def video_value(self) -> str:
        return self.video_url or self.video_id or ""


class VideoLoadResponse(BaseModel):
    video_id: str
    title: str
    chunks_indexed: int
    reused: bool


class ChatRequest(BaseModel):
    video_id: str = Field(min_length=1, max_length=32)
    question: str = Field(min_length=1, max_length=2000)
    session_id: str = Field(min_length=1, max_length=128)
    video_title: str = Field(default="", max_length=300)


class SourceResponse(BaseModel):
    video_id: str
    start_time: float
    end_time: float
    text: str


class RetrievalInfo(BaseModel):
    strategy: str
    num_candidates: int
    queries: list[str]
    latency_ms: int


class ChatResponse(BaseModel):
    answer: str
    sources: list[SourceResponse]
    video_id: str
    session_id: str
    retrieval_info: RetrievalInfo


class ResetRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=128)
    video_id: str | None = Field(default=None, max_length=32)


class ResetResponse(BaseModel):
    cleared_scopes: int


class HealthResponse(BaseModel):
    status: str
    environment: str
    pinecone_configured: bool
    huggingface_configured: bool
    langsmith_tracing: bool


class ErrorResponse(BaseModel):
    error: str
    message: str
