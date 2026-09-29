"""Hugging Face generation adapter and source-aware response assembly."""

from __future__ import annotations

import logging

from backend.config import Settings
from backend.generation.guardrails import sanitize_answer
from backend.generation.prompts import build_prompt
from backend.models import Citation, RetrievedChunk
from backend.retrieval.router import QueryRoute
from backend.utils.errors import ConfigurationError, ExternalServiceError

logger = logging.getLogger(__name__)


class HuggingFaceGenerator:
    """Use the notebook's Hugging Face Llama-style endpoint behind a narrow interface."""

    def __init__(self, settings: Settings) -> None:
        if settings.hf_token is None:
            raise ConfigurationError("HF_TOKEN is required to generate answers. Add it to .env and restart the API.")
        self._settings = settings
        try:
            from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint

            endpoint = HuggingFaceEndpoint(
                repo_id=settings.hf_llm_model,
                task="text-generation",
                max_new_tokens=settings.llm_max_new_tokens,
                timeout=settings.llm_timeout_seconds,
                huggingfacehub_api_token=settings.hf_token.get_secret_value(),
            )
            self._model = ChatHuggingFace(llm=endpoint)
        except ConfigurationError:
            raise
        except Exception as error:
            logger.exception("Unable to initialize Hugging Face generator")
            raise ExternalServiceError("The answer-generation service could not be initialized.") from error

    async def complete(self, prompt: str, max_tokens: int = 300) -> str:
        try:
            result = await self._model.ainvoke(prompt)
            content = getattr(result, "content", result)
            return str(content)
        except Exception as error:
            logger.warning("LLM generation failed: %s", type(error).__name__)
            raise ExternalServiceError("The answer-generation service timed out or returned an invalid response.") from error

    async def answer(self, route: QueryRoute, question: str, chunks: list[RetrievedChunk]) -> str:
        context = "\n\n".join(
            f"[Source {index + 1}; {chunk.start_time:.0f}s-{chunk.end_time:.0f}s]\n{chunk.text}"
            for index, chunk in enumerate(chunks)
        )
        return sanitize_answer(await self.complete(build_prompt(route, question, context), self._settings.llm_max_new_tokens))


def citations_for(chunks: list[RetrievedChunk], limit: int = 3) -> list[Citation]:
    """Create citations from retrieval metadata, never from text emitted by the LLM."""

    unique: list[Citation] = []
    seen: set[tuple[str, int]] = set()
    for chunk in chunks:
        key = (chunk.video_id, int(chunk.start_time))
        if key not in seen:
            seen.add(key)
            unique.append(Citation(chunk.video_id, chunk.start_time, chunk.end_time, chunk.text))
        if len(unique) == limit:
            break
    return unique
