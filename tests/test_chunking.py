from backend.ingestion.chunking import TranscriptChunker
from backend.models import Transcript, TranscriptSegment


def test_chunker_keeps_time_and_video_metadata(test_settings):
    transcript = Transcript(
        video_id="dQw4w9WgXcQ",
        video_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        title="Example",
        language="en",
        source="manual",
        segments=[TranscriptSegment("First complete idea. " * 12, 4, 20), TranscriptSegment("Second idea.", 24, 3)],
    )
    chunks = TranscriptChunker(test_settings).split(transcript)
    assert chunks
    assert chunks[0].video_id == transcript.video_id
    assert chunks[0].start_time == 4
    assert all(chunk.end_time >= chunk.start_time for chunk in chunks)
    assert all(chunk.metadata()["content_hash"] for chunk in chunks)
