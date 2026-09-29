"""Embedding adapter isolated from the vector-store implementation."""

from __future__ import annotations

import logging
from typing import Protocol

from backend.config import Settings
from backend.utils.errors import ConfigurationError, ExternalServiceError

logger = logging.getLogger(__name__)


class EmbeddingProvider(Protocol):
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed document text."""

    def embed_query(self, text: str) -> list[float]:
        """Embed one user query."""


class HuggingFaceEndpointEmbedder:
    """Hosted Hugging Face embeddings compatible with the original notebook model."""

    def __init__(self, settings: Settings) -> None:
        if settings.hf_token is None:
            raise ConfigurationError("HF_TOKEN is required to create embeddings. Add it to .env and restart the API.")
        try:
            from langchain_huggingface import HuggingFaceEndpointEmbeddings

            self._client = HuggingFaceEndpointEmbeddings(
                repo_id=settings.hf_embedding_model,
                task="feature-extraction",
                huggingfacehub_api_token=settings.hf_token.get_secret_value(),
            )
            # The adapter does not expose timeout directly, but its HF clients do.
            self._client.client.timeout = settings.embedding_timeout_seconds
            self._client.async_client.timeout = settings.embedding_timeout_seconds
        except ConfigurationError:
            raise
        except Exception as error:
            logger.exception("Unable to initialize Hugging Face embedding client")
            raise ExternalServiceError("The embedding service could not be initialized.") from error

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        try:
            return self._client.embed_documents(texts)
        except Exception as error:
            logger.warning("Embedding request failed: %s", type(error).__name__)
            raise ExternalServiceError("The embedding service could not process this transcript.") from error

    def embed_query(self, text: str) -> list[float]:
        try:
            return self._client.embed_query(text)
        except Exception as error:
            logger.warning("Query embedding request failed: %s", type(error).__name__)
            raise ExternalServiceError("The embedding service could not process this question.") from error

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed documents without blocking FastAPI's event loop."""

        try:
            return await self._client.aembed_documents(texts)
        except Exception as error:
            logger.warning("Async embedding request failed: %s", type(error).__name__)
            raise ExternalServiceError("The embedding service timed out or could not process this transcript.") from error
