"""Caption-provider abstraction with cache, language fallback, and safe failures."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Protocol

from backend.config import Settings
from backend.models import Transcript, TranscriptSegment
from backend.utils.errors import (
    ExternalServiceError,
    TranscriptBlockedError,
    TranscriptUnavailableError,
    VideoUnavailableError,
)

logger = logging.getLogger(__name__)


class TranscriptProvider(Protocol):
    """A replaceable source of timestamped captions."""

    async def fetch(self, video_id: str, video_url: str, title: str) -> Transcript:
        """Fetch a transcript or raise a user-safe ``AppError``."""


class YouTubeTranscriptProvider:
    """Use youtube-transcript-api without authentication or browser credentials."""

    preferred_languages = ("hi", "en")

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._cache_dir: Path = settings.transcript_cache_dir

    async def fetch(self, video_id: str, video_url: str, title: str) -> Transcript:
        cached = self._read_cache(video_id)
        if cached is not None:
            return cached

        last_error: Exception | None = None
        for attempt in range(self._settings.transcript_retries + 1):
            try:
                transcript = await asyncio.to_thread(self._fetch_once, video_id, video_url, title)
                self._write_cache(transcript)
                return transcript
            except (TranscriptUnavailableError, TranscriptBlockedError, VideoUnavailableError):
                raise
            except Exception as error:  # Provider internals vary by library release.
                last_error = error
                if attempt < self._settings.transcript_retries:
                    await asyncio.sleep(0.4 * (2**attempt))

        logger.warning("Transcript provider failed for video_id=%s: %s", video_id, type(last_error).__name__)
        raise ExternalServiceError("The transcript provider could not be reached. Please try again.")

    def _fetch_once(self, video_id: str, video_url: str, title: str) -> Transcript:
        try:
            from youtube_transcript_api import YouTubeTranscriptApi

            api = YouTubeTranscriptApi()
            try:
                fetched = api.fetch(video_id, languages=list(self.preferred_languages))
            except Exception:
                # Captions can exist only in another language. Choose one available transcript rather than fail.
                fetched = self._fetch_available_language(api, video_id)
            raw_segments = self._raw_segments(fetched)
            language = getattr(fetched, "language_code", None) or getattr(fetched, "language", None) or "unknown"
            is_generated = bool(getattr(fetched, "is_generated", False))
            source = "auto-generated" if is_generated else "manual"
            segments = [
                TranscriptSegment(
                    text=str(item.get("text", "")).strip(),
                    start_time=float(item.get("start", item.get("start_time", 0))),
                    duration=float(item.get("duration", 0)),
                )
                for item in raw_segments
                if str(item.get("text", "")).strip()
            ]
            if not segments:
                raise TranscriptUnavailableError()
            return Transcript(video_id, video_url, title, str(language), source, segments)
        except (TranscriptUnavailableError, TranscriptBlockedError, VideoUnavailableError):
            raise
        except Exception as error:
            raise self._classify_error(error) from error

    @staticmethod
    def _fetch_available_language(api, video_id: str):
        transcript_list = api.list(video_id)
        transcript = next(iter(transcript_list), None)
        if transcript is None:
            raise TranscriptUnavailableError()
        return transcript.fetch()

    @staticmethod
    def _raw_segments(fetched) -> list[dict[str, float | str]]:
        if hasattr(fetched, "to_raw_data"):
            return fetched.to_raw_data()
        return [
            {
                "text": getattr(item, "text", ""),
                "start": getattr(item, "start", getattr(item, "start_time", 0)),
                "duration": getattr(item, "duration", 0),
            }
            for item in fetched
        ]

    @staticmethod
    def _classify_error(error: Exception):
        name = type(error).__name__.lower()
        message = str(error).lower()
        if any(token in name or token in message for token in ("ipblocked", "requestblocked", "blocking requests", "too many requests")):
            return TranscriptBlockedError()
        if any(token in name or token in message for token in ("transcriptsdisabled", "notranscriptfound", "could not retrieve a transcript", "no transcript")):
            return TranscriptUnavailableError()
        if any(token in name or token in message for token in ("video unavailable", "videounavailable")):
            return VideoUnavailableError()
        return error

    def _cache_path(self, video_id: str) -> Path:
        return self._cache_dir / f"{video_id}.json"

    def _read_cache(self, video_id: str) -> Transcript | None:
        path = self._cache_path(video_id)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return Transcript(
                video_id=data["video_id"],
                video_url=data["video_url"],
                title=data["title"],
                language=data["language"],
                source=data["source"],
                segments=[TranscriptSegment(**segment) for segment in data["segments"]],
            )
        except FileNotFoundError:
            return None
        except (OSError, ValueError, KeyError, TypeError):
            logger.warning("Ignoring unreadable transcript cache for video_id=%s", video_id)
            return None

    def _write_cache(self, transcript: Transcript) -> None:
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "video_id": transcript.video_id,
            "video_url": transcript.video_url,
            "title": transcript.title,
            "language": transcript.language,
            "source": transcript.source,
            "cached_at": time.time(),
            "segments": [segment.__dict__ for segment in transcript.segments],
        }
        self._cache_path(transcript.video_id).write_text(json.dumps(payload, ensure_ascii=True), encoding="utf-8")
