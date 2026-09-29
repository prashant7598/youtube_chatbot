"""Robust parsing for the YouTube URL forms accepted by the API."""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse

from backend.utils.errors import InvalidVideoUrlError

VIDEO_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{11}$")
YOUTUBE_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtube-nocookie.com",
    "www.youtube-nocookie.com",
}


def extract_video_id(value: str) -> str:
    """Extract an 11-character video ID from a supported URL or a raw ID."""

    candidate = value.strip()
    if VIDEO_ID_PATTERN.fullmatch(candidate):
        return candidate

    parsed = urlparse(candidate if "://" in candidate else f"https://{candidate}")
    host = parsed.netloc.lower().split(":")[0]
    path_parts = [part for part in parsed.path.split("/") if part]
    video_id: str | None = None

    if host in {"youtu.be", "www.youtu.be"} and path_parts:
        video_id = path_parts[0]
    elif host in YOUTUBE_HOSTS:
        if parsed.path == "/watch":
            video_id = parse_qs(parsed.query).get("v", [None])[0]
        elif len(path_parts) >= 2 and path_parts[0] in {"shorts", "embed", "live", "v", "vi"}:
            video_id = path_parts[1]

    if video_id and VIDEO_ID_PATTERN.fullmatch(video_id):
        return video_id
    raise InvalidVideoUrlError()


def canonical_video_url(video_id: str) -> str:
    """Return the canonical, privacy-neutral YouTube watch URL."""

    return f"https://www.youtube.com/watch?v={video_id}"
