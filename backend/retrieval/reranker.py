"""Pluggable rerankers; lexical is safe as the no-extra-model default."""

from __future__ import annotations

import re
from typing import Protocol

from backend.models import RetrievedChunk

TOKEN = re.compile(r"[a-z0-9]{2,}")


class Reranker(Protocol):
    def rerank(self, query: str, candidates: list[RetrievedChunk]) -> list[RetrievedChunk]:
        """Return candidates ordered by evidence relevance."""


class LexicalReranker:
    """Blend semantic score with transparent token-overlap relevance."""

    def rerank(self, query: str, candidates: list[RetrievedChunk]) -> list[RetrievedChunk]:
        query_tokens = set(TOKEN.findall(query.lower()))
        for candidate in candidates:
            content_tokens = set(TOKEN.findall(candidate.text.lower()))
            lexical = len(query_tokens & content_tokens) / max(len(query_tokens), 1)
            candidate.score = 0.72 * candidate.score + 0.28 * lexical
        return sorted(candidates, key=lambda candidate: candidate.score, reverse=True)


class CrossEncoderReranker:
    """Optional local cross-encoder reranker; install sentence-transformers to use it."""

    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2") -> None:
        from sentence_transformers import CrossEncoder

        self._model = CrossEncoder(model_name)

    def rerank(self, query: str, candidates: list[RetrievedChunk]) -> list[RetrievedChunk]:
        scores = self._model.predict([(query, candidate.text) for candidate in candidates])
        for candidate, score in zip(candidates, scores, strict=True):
            candidate.score = float(score)
        return sorted(candidates, key=lambda candidate: candidate.score, reverse=True)
