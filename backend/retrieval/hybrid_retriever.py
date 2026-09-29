"""Video-isolated semantic retrieval, lexical blending, MMR, and reranking."""

from __future__ import annotations

import re
from time import perf_counter

from backend.config import Settings
from backend.indexing.embeddings import EmbeddingProvider
from backend.indexing.pinecone_store import VectorStore
from backend.models import RetrievedChunk
from backend.retrieval.mmr import select_mmr
from backend.retrieval.reranker import Reranker

TOKEN = re.compile(r"[a-z0-9]{2,}")


class HybridRetriever:
    """Combine dense Pinecone candidates with lightweight lexical evidence ranking."""

    def __init__(self, store: VectorStore, embeddings: EmbeddingProvider, reranker: Reranker, settings: Settings) -> None:
        self._store = store
        self._embeddings = embeddings
        self._reranker = reranker
        self._settings = settings

    def retrieve(self, video_id: str, queries: list[str], candidate_multiplier: int) -> tuple[list[RetrievedChunk], int]:
        started = perf_counter()
        candidates: dict[str, RetrievedChunk] = {}
        requested = min(self._settings.retrieval_candidates * candidate_multiplier, 50)
        for query in queries:
            vector = self._embeddings.embed_query(query)
            for candidate in self._store.query(vector, video_id, requested):
                existing = candidates.get(candidate.id)
                if existing is None or candidate.score > existing.score:
                    candidates[candidate.id] = candidate
        blended = self._blend_lexical(queries[0], list(candidates.values()))
        reranked = self._reranker.rerank(queries[0], blended)
        selected = select_mmr(reranked, self._settings.final_context_chunks)
        return selected, int((perf_counter() - started) * 1000)

    @staticmethod
    def _blend_lexical(query: str, candidates: list[RetrievedChunk]) -> list[RetrievedChunk]:
        query_tokens = set(TOKEN.findall(query.lower()))
        for candidate in candidates:
            text_tokens = set(TOKEN.findall(candidate.text.lower()))
            lexical = len(query_tokens & text_tokens) / max(len(query_tokens), 1)
            candidate.score = 0.8 * candidate.score + 0.2 * lexical
        return candidates
