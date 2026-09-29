import pytest

from backend.ingestion.youtube import canonical_video_url, extract_video_id
from backend.utils.errors import InvalidVideoUrlError


@pytest.mark.parametrize(
    "value",
    [
        "dQw4w9WgXcQ",
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=3",
        "https://youtu.be/dQw4w9WgXcQ",
        "https://www.youtube.com/shorts/dQw4w9WgXcQ",
        "https://www.youtube.com/embed/dQw4w9WgXcQ",
        "https://www.youtube.com/live/dQw4w9WgXcQ",
    ],
)
def test_extract_video_id(value):
    assert extract_video_id(value) == "dQw4w9WgXcQ"


def test_rejects_non_youtube_url():
    with pytest.raises(InvalidVideoUrlError):
        extract_video_id("https://example.com/watch?v=dQw4w9WgXcQ")


def test_canonical_url():
    assert canonical_video_url("dQw4w9WgXcQ") == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
