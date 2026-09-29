from __future__ import annotations

import pytest

from backend.config import Settings
from backend.models import RetrievedChunk, Transcript, TranscriptSegment


class FakeTranscriptProvider:
    async def fetch(self, video_id: str, video_url: str, title: str) -> Transcript:
        return Transcript(
            video_id=video_id,
            video_url=video_url,
            title=title,
            language="en",
            source="manual",
            segments=[
                TranscriptSegment("Backpropagation computes gradients by applying the chain rule.", 12, 5),
                TranscriptSegment("It is important because neural networks use those gradients to update weights.", 18, 6),
            ],
        )


class FakeEmbeddings:
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[float(len(text)), 1.0] for text in texts]

    def embed_query(self, _text: str) -> list[float]:
        return [1.0, 1.0]

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        return self.embed_documents(texts)


class FakeStore:
    def __init__(self) -> None:
        self.chunks = []
        self.vectors = []

    def is_current(self, _first_chunk) -> bool:
        return bool(self.chunks)

    def replace_video(self, chunks, vectors) -> None:
        self.chunks, self.vectors = chunks, vectors

    def query(self, _vector, video_id: str, _top_k: int) -> list[RetrievedChunk]:
        return [
            RetrievedChunk(
                id=chunk.id,
                text=chunk.text,
                video_id=video_id,
                start_time=chunk.start_time,
                end_time=chunk.end_time,
                score=0.9 - index * 0.05,
                metadata=chunk.metadata(),
                vector=self.vectors[index],
            )
            for index, chunk in enumerate(self.chunks)
        ]


class FakeGenerator:
    async def complete(self, _prompt: str, max_tokens: int = 300) -> str:
        return "A compact retrieval query"

    async def answer(self, _route, _question: str, _chunks) -> str:
        return "The video says backpropagation computes gradients and uses them to update weights."


@pytest.fixture
def test_settings(tmp_path):
    return Settings(
        transcript_cache_dir=tmp_path / "cache",
        chunk_size=250,
        chunk_overlap=40,
        hf_token="test-hf-token",
        pinecone_api_key="test-pinecone-key",
    )
