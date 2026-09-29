"""Small, deterministic guardrails surrounding model invocation."""

from __future__ import annotations

import re

from backend.models import RetrievedChunk
from backend.utils.errors import UnsafePromptError

INJECTION = re.compile(r"\b(ignore|override|reveal|show)\b.{0,40}\b(instruction|system prompt|previous prompt|developer message)\b", re.I)


def validate_question(question: str) -> None:
    """Reject direct attempts to turn the video assistant into a prompt-exfiltration tool."""

    if not question.strip() or len(question) > 2000 or INJECTION.search(question):
        raise UnsafePromptError()


def has_evidence(chunks: list[RetrievedChunk]) -> bool:
    """Require nonempty source material before asking an LLM for a grounded answer."""

    return bool(chunks and any(chunk.text.strip() for chunk in chunks))


def sanitize_answer(answer: str) -> str:
    """Keep model output compact; citations always come from structured retrieval metadata."""

    cleaned = answer.strip()
    return cleaned[:4000] if cleaned else "The transcript does not provide enough information to answer that."
