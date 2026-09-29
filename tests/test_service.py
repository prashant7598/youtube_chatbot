import pytest

from backend.api.schemas import TranscriptSegmentRequest
from backend.models import RetrievedChunk
from backend.retrieval.compression import ContextCompressor
from backend.service import YoutubeRagService
from tests.conftest import FakeEmbeddings, FakeGenerator, FakeStore, FakeTranscriptProvider


@pytest.mark.asyncio
async def test_load_then_chat_returns_structured_citation(test_settings):
    service = YoutubeRagService(test_settings, transcript_provider=FakeTranscriptProvider())
    service.__dict__["embeddings"] = FakeEmbeddings()
    service.__dict__["store"] = FakeStore()
    service.__dict__["generator"] = FakeGenerator()

    loaded = await service.load_video("dQw4w9WgXcQ", "Example video")
    result = await service.chat("dQw4w9WgXcQ", "Why is backpropagation important?", "session-a", "Example video")

    assert loaded["reused"] is False
    assert result.sources
    assert result.sources[0].start_time == 12
    assert result.route == "conceptual_explanation"


@pytest.mark.asyncio
async def test_load_video_uses_browser_captions_without_provider_call(test_settings):
    class FailingProvider:
        async def fetch(self, *_args, **_kwargs):
            raise AssertionError("Browser captions should bypass the server-side transcript provider")

    service = YoutubeRagService(test_settings, transcript_provider=FailingProvider())
    service.__dict__["embeddings"] = FakeEmbeddings()
    service.__dict__["store"] = FakeStore()
    result = await service.load_video(
        "dQw4w9WgXcQ",
        "Captioned example",
        transcript_segments=[TranscriptSegmentRequest(text="The browser caption track is available.", start_time=8, duration=3)],
        transcript_language="en",
    )

    assert result["chunks_indexed"] == 1
    assert service.store.chunks[0].transcript_source == "browser-captions"
    assert service.store.chunks[0].start_time == 8


def test_compressor_keeps_a_compact_chunk_intact_when_only_one_sentence_matches():
    chunk = RetrievedChunk(
        id="chunk",
        text="This video demonstrates the extension. It verifies browser captions are stored in Pinecone.",
        video_id="video-id",
        start_time=0,
        end_time=10,
        score=1.0,
    )

    compressed = ContextCompressor().compress("What does this video verify?", [chunk], max_chars=8500)

    assert compressed[0].text == chunk.text
