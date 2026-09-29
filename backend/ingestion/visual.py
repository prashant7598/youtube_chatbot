"""Extension point for future timestamp-aligned visual context retrieval."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class VisualContext:
    """A future frame, slide, OCR, or chart retrieval result aligned to video time."""

    video_id: str
    start_time: float
    end_time: float
    description: str
    modality: str


class VisualContextProvider(Protocol):
    """Contract for later frame/OCR/slide indexes; transcript RAG does not depend on it."""

    async def retrieve(self, video_id: str, query: str, limit: int = 3) -> list[VisualContext]:
        """Return timestamp-aligned visual evidence for the active video."""


class NoopVisualContextProvider:
    """Default placeholder keeps transcript-only deployments lightweight."""

    async def retrieve(self, video_id: str, query: str, limit: int = 3) -> list[VisualContext]:
        return []
