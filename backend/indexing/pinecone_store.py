"""Pinecone adapter with video-level metadata filtering and duplicate avoidance."""

from __future__ import annotations

import logging
import time
from typing import Any, Protocol

from backend.config import Settings
from backend.ingestion.metadata import pinecone_metadata
from backend.models import Chunk, RetrievedChunk
from backend.utils.errors import ConfigurationError, ExternalServiceError

logger = logging.getLogger(__name__)


class VectorStore(Protocol):
    def is_current(self, first_chunk: Chunk) -> bool:
        """Return whether this exact video content has already been indexed."""

    def replace_video(self, chunks: list[Chunk], vectors: list[list[float]]) -> None:
        """Upsert a video's vectors, replacing stale chunks when source captions changed."""

    def query(self, vector: list[float], video_id: str, top_k: int) -> list[RetrievedChunk]:
        """Retrieve candidates isolated to one YouTube video."""


class PineconeVectorStore:
    """Production vector store. One shared index is separated by ``video_id`` metadata."""

    def __init__(self, settings: Settings) -> None:
        if settings.pinecone_api_key is None:
            raise ConfigurationError(
                "PINECONE_API_KEY is required for indexing. Add Pinecone credentials to .env and restart the API."
            )
        self._settings = settings
        try:
            from pinecone import Pinecone

            self._client = Pinecone(api_key=settings.pinecone_api_key.get_secret_value())
            self._index: Any | None = None
        except ConfigurationError:
            raise
        except Exception as error:
            logger.exception("Unable to initialize Pinecone client")
            raise ExternalServiceError("Pinecone could not be initialized. Check the server configuration.") from error

    def _get_index(self, dimension: int | None = None):
        if self._index is not None:
            return self._index
        try:
            created = not self._client.has_index(self._settings.pinecone_index)
            if created:
                if dimension is None:
                    raise ExternalServiceError("The Pinecone index does not exist yet. Load a video to create it.")
                from pinecone import ServerlessSpec

                self._client.create_index(
                    name=self._settings.pinecone_index,
                    dimension=dimension,
                    metric="cosine",
                    spec=ServerlessSpec(cloud=self._settings.pinecone_cloud, region=self._settings.pinecone_region),
                )
            self._wait_until_ready()
            self._index = self._client.Index(self._settings.pinecone_index)
            return self._index
        except ExternalServiceError:
            raise
        except Exception as error:
            logger.warning("Pinecone index operation failed: %s", type(error).__name__)
            raise ExternalServiceError("Pinecone could not prepare the shared vector index.") from error

    def _wait_until_ready(self) -> None:
        """Pinecone creates serverless indexes asynchronously; wait before first upsert/query."""

        deadline = time.monotonic() + self._settings.pinecone_ready_timeout_seconds
        while time.monotonic() < deadline:
            description = self._client.describe_index(self._settings.pinecone_index)
            status = self._response_value(description, "status", {})
            ready = self._response_value(status, "ready", False)
            if ready:
                return
            time.sleep(1)
        raise ExternalServiceError("The Pinecone index is still preparing. Please try loading the video again shortly.")

    def is_current(self, first_chunk: Chunk) -> bool:
        try:
            index = self._get_index()
            response = index.fetch(ids=[first_chunk.id], namespace=self._settings.pinecone_namespace)
            vector = self._response_value(response, "vectors", {}).get(first_chunk.id)
            metadata = self._response_value(vector, "metadata", {}) if vector else {}
            return bool(metadata and metadata.get("content_hash") == first_chunk.content_hash)
        except ExternalServiceError:
            return False
        except Exception as error:
            logger.warning("Pinecone duplicate check failed: %s", type(error).__name__)
            return False

    def replace_video(self, chunks: list[Chunk], vectors: list[list[float]]) -> None:
        if not chunks or len(chunks) != len(vectors):
            raise ValueError("Chunk and embedding counts must match.")
        try:
            index = self._get_index(dimension=len(vectors[0]))
            # Delete only this video's previous rows before replacing changed transcript content.
            self._delete_existing_video(index, chunks[0].video_id)
            records = [
                {"id": chunk.id, "values": vector, "metadata": pinecone_metadata(chunk)}
                for chunk, vector in zip(chunks, vectors, strict=True)
            ]
            for start in range(0, len(records), 100):
                index.upsert(vectors=records[start : start + 100], namespace=self._settings.pinecone_namespace)
        except Exception as error:
            logger.warning("Pinecone upsert failed: %s", type(error).__name__)
            raise ExternalServiceError("Pinecone could not save this video's transcript.") from error

    def _delete_existing_video(self, index: Any, video_id: str) -> None:
        """Remove stale chunks, accepting Pinecone's empty-namespace response on first load."""

        try:
            index.delete(
                filter={"video_id": {"$eq": video_id}},
                namespace=self._settings.pinecone_namespace,
            )
        except Exception as error:
            # Pinecone returns a 404 for filter deletion in a namespace that has never
            # received a vector. That is the expected state for a first video load.
            if type(error).__name__ == "NotFoundException" and "Namespace not found" in str(error):
                logger.info("Pinecone namespace does not exist yet; starting a new transcript collection.")
                return
            raise

    def query(self, vector: list[float], video_id: str, top_k: int) -> list[RetrievedChunk]:
        try:
            index = self._get_index()
            response = index.query(
                vector=vector,
                top_k=top_k,
                include_metadata=True,
                include_values=True,
                filter={"video_id": {"$eq": video_id}},
                namespace=self._settings.pinecone_namespace,
            )
            matches = self._response_value(response, "matches", [])
            return [self._to_retrieved(match) for match in matches]
        except ExternalServiceError:
            raise
        except Exception as error:
            logger.warning("Pinecone query failed: %s", type(error).__name__)
            raise ExternalServiceError("Pinecone could not retrieve transcript context.") from error

    @staticmethod
    def _response_value(value: Any, key: str, default: Any) -> Any:
        if value is None:
            return default
        if isinstance(value, dict):
            return value.get(key, default)
        return getattr(value, key, default)

    def _to_retrieved(self, match: Any) -> RetrievedChunk:
        metadata = self._response_value(match, "metadata", {}) or {}
        return RetrievedChunk(
            id=str(self._response_value(match, "id", "")),
            text=str(metadata.get("text", "")),
            video_id=str(metadata.get("video_id", "")),
            start_time=float(metadata.get("start_time", 0)),
            end_time=float(metadata.get("end_time", 0)),
            score=float(self._response_value(match, "score", 0)),
            metadata=dict(metadata),
            vector=list(self._response_value(match, "values", []) or []),
        )
