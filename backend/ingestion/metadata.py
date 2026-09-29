"""Metadata helpers kept separate for future non-transcript modalities."""

from __future__ import annotations

from backend.models import Chunk


def pinecone_metadata(chunk: Chunk) -> dict[str, str | float | int]:
    """Return Pinecone-safe metadata while retaining source attribution."""

    return chunk.metadata()
