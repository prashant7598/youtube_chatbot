"""Application service coordinating the modular transcript-only RAG flow."""

from __future__ import annotations

import logging
import asyncio
from functools import cached_property

from backend.config import Settings, get_settings
from backend.evaluation.langsmith import LangSmithTracer
from backend.generation.generator import HuggingFaceGenerator, citations_for
from backend.generation.guardrails import has_evidence, validate_question
from backend.indexing.embeddings import HuggingFaceEndpointEmbedder
from backend.indexing.pinecone_store import PineconeVectorStore
from backend.ingestion.chunking import TranscriptChunker
from backend.ingestion.transcript import TranscriptProvider, YouTubeTranscriptProvider
from backend.ingestion.youtube import canonical_video_url, extract_video_id
from backend.memory.conversation import ConversationMemory
from backend.models import ChatResult, Transcript, TranscriptSegment
from backend.retrieval.compression import ContextCompressor
from backend.retrieval.hybrid_retriever import HybridRetriever
from backend.retrieval.multi_query import MultiQueryGenerator
from backend.retrieval.query_rewriter import QueryRewriter
from backend.retrieval.reranker import CrossEncoderReranker, LexicalReranker
from backend.retrieval.router import QueryRoute, QueryRouter
from backend.utils.errors import InvalidSessionError
from backend.utils.errors import ConfigurationError

logger = logging.getLogger(__name__)


class YoutubeRagService:
    """Keeps the API thin while every RAG layer remains replaceable and testable."""

    def __init__(
        self,
        settings: Settings | None = None,
        transcript_provider: TranscriptProvider | None = None,
        memory: ConversationMemory | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.transcript_provider = transcript_provider or YouTubeTranscriptProvider(self.settings)
        self.memory = memory or ConversationMemory()
        self.router = QueryRouter()
        self.compressor = ContextCompressor()
        self.tracer = LangSmithTracer(self.settings)

    @cached_property
    def embeddings(self) -> HuggingFaceEndpointEmbedder:
        return HuggingFaceEndpointEmbedder(self.settings)

    @cached_property
    def store(self) -> PineconeVectorStore:
        return PineconeVectorStore(self.settings)

    @cached_property
    def generator(self) -> HuggingFaceGenerator:
        return HuggingFaceGenerator(self.settings)

    @cached_property
    def reranker(self):
        if self.settings.reranker_mode == "cross_encoder":
            try:
                return CrossEncoderReranker()
            except Exception:
                logger.warning("Cross-encoder unavailable; using lexical reranker")
        return LexicalReranker()

    async def load_video(
        self,
        video_value: str,
        title: str = "",
        transcript_segments: list | None = None,
        transcript_language: str | None = None,
    ) -> dict[str, object]:
        """Fetch, chunk, and index a video only when its cached transcript has changed."""

        video_id = extract_video_id(video_value)
        self._require_indexing_configuration()
        video_url = canonical_video_url(video_id)
        safe_title = title.strip()[:300] or f"YouTube video {video_id}"
        with self.tracer.trace("youtube_ingestion", "chain", {"video_id": video_id}) as trace:
            transcript = self._browser_transcript(
                video_id,
                video_url,
                safe_title,
                transcript_segments,
                transcript_language,
            ) or await self.transcript_provider.fetch(video_id, video_url, safe_title)
            chunks = TranscriptChunker(self.settings).split(transcript)
            if not chunks:
                # Provider already checks this; retained as a defense against custom providers.
                from backend.utils.errors import TranscriptUnavailableError

                raise TranscriptUnavailableError()
            if await asyncio.to_thread(self.store.is_current, chunks[0]):
                trace.update({"chunks": len(chunks), "reused": True})
                return {"video_id": video_id, "title": transcript.title, "chunks_indexed": len(chunks), "reused": True}
            vectors = await self._embed_documents([chunk.text for chunk in chunks])
            await asyncio.to_thread(self.store.replace_video, chunks, vectors)
            trace.update({"chunks": len(chunks), "reused": False})
            return {"video_id": video_id, "title": transcript.title, "chunks_indexed": len(chunks), "reused": False}

    async def chat(self, video_id: str, question: str, session_id: str, title: str = "") -> ChatResult:
        """Run a grounded answer flow scoped to the supplied video and session."""

        if not session_id.strip() or len(session_id) > 128:
            raise InvalidSessionError()
        video_id = extract_video_id(video_id)
        validate_question(question)
        history = self.memory.history(session_id, video_id)
        decision = self.router.route(question, bool(history))
        if decision.route == QueryRoute.CONVERSATIONAL:
            return ChatResult(
                answer="Ask me anything about the current video's transcript.",
                sources=[],
                route=decision.route,
                num_candidates=0,
                queries=[],
                retrieval_latency_ms=0,
            )
        if decision.route == QueryRoute.OUT_OF_SCOPE:
            return ChatResult(
                answer="I can answer questions about the current video's transcript.",
                sources=[],
                route=decision.route,
                num_candidates=0,
                queries=[],
                retrieval_latency_ms=0,
            )

        # Rewriting and multi-query generation can use an LLM when configured, but always fall back safely.
        rewriter = QueryRewriter(self._configured_generator())
        query = await rewriter.rewrite(question, history, title)
        queries = await MultiQueryGenerator(self._configured_generator()).generate(query, decision.route)
        retriever = HybridRetriever(self.store, self.embeddings, self.reranker, self.settings)
        with self.tracer.trace("retrieval", "retriever", {"video_id": video_id, "queries": queries}) as trace:
            chunks, latency = await asyncio.to_thread(retriever.retrieve, video_id, queries, decision.candidate_multiplier)
            compressed = self.compressor.compress(query, chunks, self.settings.max_context_chars)
            trace.update({"candidate_count": len(chunks), "context_count": len(compressed), "latency_ms": latency})
        if not has_evidence(compressed):
            answer = "The transcript does not provide enough information to answer that."
            self.memory.add(session_id, video_id, question, answer)
            return ChatResult(answer, [], decision.route, len(chunks), queries, latency)

        with self.tracer.trace("generation", "llm", {"route": decision.route, "context_count": len(compressed)}) as trace:
            answer = await self.generator.answer(decision.route, question, compressed)
            trace["source_count"] = min(len(compressed), 3)
        self.memory.add(session_id, video_id, question, answer)
        return ChatResult(answer, citations_for(compressed), decision.route, len(chunks), queries, latency)

    def reset(self, session_id: str, video_id: str | None = None) -> int:
        """Clear one session's current-video memory without affecting other users."""

        if not session_id.strip():
            raise InvalidSessionError()
        normalized_video = extract_video_id(video_id) if video_id else None
        return self.memory.clear(session_id, normalized_video)

    def _configured_generator(self) -> HuggingFaceGenerator | None:
        """Avoid failing pre-retrieval when operators intentionally run retrieval-only diagnostics."""

        try:
            return self.generator
        except Exception:
            return None

    def _require_indexing_configuration(self) -> None:
        """Report missing external services before initiating transcript or vector work."""

        missing = []
        if self.settings.hf_token is None:
            missing.append("HF_TOKEN")
        if self.settings.pinecone_api_key is None:
            missing.append("PINECONE_API_KEY")
        if missing:
            names = " and ".join(missing)
            raise ConfigurationError(f"{names} must be set in .env before loading a video. Restart the backend afterwards.")

    async def _embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Use the async Hugging Face adapter when available; retain simple test doubles."""

        async_method = getattr(self.embeddings, "aembed_documents", None)
        if async_method is not None:
            return await async_method(texts)
        return await asyncio.to_thread(self.embeddings.embed_documents, texts)

    @staticmethod
    def _browser_transcript(
        video_id: str,
        video_url: str,
        title: str,
        segments: list | None,
        language: str | None,
    ) -> Transcript | None:
        """Prefer captions read by the active YouTube tab when it can access a track."""

        if not segments:
            return None
        normalized = [
            TranscriptSegment(
                text=str(segment.text).strip(),
                start_time=float(segment.start_time),
                duration=float(segment.duration),
            )
            for segment in segments
            if str(segment.text).strip()
        ]
        if not normalized:
            return None
        return Transcript(
            video_id=video_id,
            video_url=video_url,
            title=title,
            language=(language or "unknown")[:32],
            source="browser-captions",
            segments=normalized,
        )
