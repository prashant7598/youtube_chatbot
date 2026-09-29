"""Extract query-relevant sentences while retaining attribution metadata."""

from __future__ import annotations

import re

from backend.models import RetrievedChunk

SPLIT_SENTENCES = re.compile(r"(?<=[.!?])\s+")
TOKENS = re.compile(r"[a-z0-9]{2,}")


class ContextCompressor:
    """Reduce context tokens without losing source timestamp information."""

    def compress(self, query: str, chunks: list[RetrievedChunk], max_chars: int) -> list[RetrievedChunk]:
        query_tokens = set(TOKENS.findall(query.lower()))
        result: list[RetrievedChunk] = []
        used = 0
        for chunk in chunks:
            sentences = [sentence.strip() for sentence in SPLIT_SENTENCES.split(chunk.text) if sentence.strip()]
            # Normal transcript chunks are already compact. Keeping them whole avoids
            # dropping the answer when a neighbouring sentence matches a generic term.
            if len(chunk.text) <= 1200:
                selected_text = chunk.text
            else:
                relevant = [
                    sentence
                    for sentence in sentences
                    if query_tokens & set(TOKENS.findall(sentence.lower()))
                ]
                selected_text = " ".join(relevant[:4]) or chunk.text
            available = max_chars - used
            if available <= 0:
                break
            selected_text = selected_text[:available].strip()
            if selected_text:
                result.append(
                    RetrievedChunk(
                        id=chunk.id,
                        text=selected_text,
                        video_id=chunk.video_id,
                        start_time=chunk.start_time,
                        end_time=chunk.end_time,
                        score=chunk.score,
                        metadata=chunk.metadata,
                        vector=chunk.vector,
                    )
                )
                used += len(selected_text)
        return result
