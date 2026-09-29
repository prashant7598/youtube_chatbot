"""Typed domain models shared across ingestion, retrieval, and generation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class TranscriptSegment:
    text: str
    start_time: float
    duration: float

    @property
    def end_time(self) -> float:
        return self.start_time + self.duration


@dataclass(frozen=True)
class Transcript:
    video_id: str
    video_url: str
    title: str
    language: str
    source: str
    segments: list[TranscriptSegment]


@dataclass(frozen=True)
class Chunk:
    id: str
    video_id: str
    video_url: str
    title: str
    language: str
    transcript_source: str
    text: str
    start_time: float
    end_time: float
    chunk_id: int
    content_hash: str

    def metadata(self) -> dict[str, Any]:
        return {
            "video_id": self.video_id,
            "video_url": self.video_url,
            "title": self.title,
            "language": self.language,
            "transcript_source": self.transcript_source,
            "text": self.text,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "chunk_id": self.chunk_id,
            "content_hash": self.content_hash,
        }


@dataclass
class RetrievedChunk:
    id: str
    text: str
    video_id: str
    start_time: float
    end_time: float
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)
    vector: list[float] | None = None


@dataclass(frozen=True)
class Citation:
    video_id: str
    start_time: float
    end_time: float
    text: str


@dataclass(frozen=True)
class ChatResult:
    answer: str
    sources: list[Citation]
    route: str
    num_candidates: int
    queries: list[str]
    retrieval_latency_ms: int
