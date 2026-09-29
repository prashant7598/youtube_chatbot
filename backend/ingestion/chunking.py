"""Sentence-aware, timestamp-preserving transcript chunking."""

from __future__ import annotations

import hashlib
import re

from backend.config import Settings
from backend.models import Chunk, Transcript, TranscriptSegment

SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+")


class TranscriptChunker:
    """Build overlapping chunks aligned to transcript timestamps instead of raw strings."""

    def __init__(self, settings: Settings) -> None:
        self._chunk_size = settings.chunk_size
        self._overlap = settings.chunk_overlap

    def split(self, transcript: Transcript) -> list[Chunk]:
        normalized_segments = [part for segment in transcript.segments for part in self._split_long_segment(segment)]
        full_text = " ".join(segment.text for segment in normalized_segments)
        content_hash = hashlib.sha256(full_text.encode("utf-8")).hexdigest()
        groups: list[list[TranscriptSegment]] = []
        current: list[TranscriptSegment] = []
        current_length = 0

        for segment in normalized_segments:
            segment_length = len(segment.text) + 1
            if current and current_length + segment_length > self._chunk_size:
                groups.append(current)
                current = self._overlap_tail(current)
                current_length = sum(len(item.text) + 1 for item in current)
            current.append(segment)
            current_length += segment_length
        if current:
            groups.append(current)

        chunks: list[Chunk] = []
        for index, group in enumerate(groups):
            text = " ".join(item.text for item in group).strip()
            if not text:
                continue
            chunks.append(
                Chunk(
                    id=f"{transcript.video_id}:{index:04d}",
                    video_id=transcript.video_id,
                    video_url=transcript.video_url,
                    title=transcript.title,
                    language=transcript.language,
                    transcript_source=transcript.source,
                    text=text,
                    start_time=group[0].start_time,
                    end_time=group[-1].end_time,
                    chunk_id=index,
                    content_hash=content_hash,
                )
            )
        return chunks

    def _overlap_tail(self, segments: list[TranscriptSegment]) -> list[TranscriptSegment]:
        selected: list[TranscriptSegment] = []
        selected_length = 0
        for segment in reversed(segments):
            selected.insert(0, segment)
            selected_length += len(segment.text) + 1
            if selected_length >= self._overlap:
                break
        return selected

    def _split_long_segment(self, segment: TranscriptSegment) -> list[TranscriptSegment]:
        if len(segment.text) <= self._chunk_size:
            return [segment]
        sentences = [item.strip() for item in SENTENCE_BOUNDARY.split(segment.text) if item.strip()]
        if len(sentences) < 2:
            sentences = [segment.text[i : i + self._chunk_size] for i in range(0, len(segment.text), self._chunk_size)]
        total_characters = max(sum(len(sentence) for sentence in sentences), 1)
        elapsed = segment.start_time
        parts: list[TranscriptSegment] = []
        for sentence in sentences:
            duration = segment.duration * len(sentence) / total_characters
            parts.append(TranscriptSegment(sentence, elapsed, duration))
            elapsed += duration
        return parts
