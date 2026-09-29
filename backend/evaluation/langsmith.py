"""Minimal LangSmith run instrumentation with no-op behavior when tracing is disabled."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import logging
from time import perf_counter
from typing import Any, Iterator
from uuid import uuid4

from backend.config import Settings

logger = logging.getLogger(__name__)


class LangSmithTracer:
    """Emit retrieval and LLM runs only when explicitly configured through environment variables."""

    def __init__(self, settings: Settings) -> None:
        self._enabled = settings.langsmith_tracing and settings.langsmith_api_key is not None
        self._project = settings.langsmith_project
        self._client = None
        if self._enabled:
            try:
                from langsmith import Client

                self._client = Client(api_key=settings.langsmith_api_key.get_secret_value())
            except Exception as error:
                logger.warning("LangSmith tracing disabled: %s", type(error).__name__)
                self._enabled = False

    @contextmanager
    def trace(self, name: str, run_type: str, inputs: dict[str, Any]) -> Iterator[dict[str, Any]]:
        """Track latency, result shape, and errors without putting credentials in trace inputs."""

        started = perf_counter()
        run_id = None
        payload: dict[str, Any] = {}
        if self._enabled and self._client is not None:
            try:
                run_id = uuid4()
                self._client.create_run(
                    id=run_id,
                    name=name,
                    run_type=run_type,
                    inputs=inputs,
                    project_name=self._project,
                    start_time=datetime.now(timezone.utc),
                )
            except Exception:
                logger.debug("Unable to start LangSmith trace", exc_info=True)
        try:
            yield payload
        except Exception as error:
            if run_id is not None:
                try:
                    self._client.update_run(run_id, error=str(type(error).__name__), end_time=datetime.now(timezone.utc))
                except Exception:
                    logger.debug("Unable to update failed LangSmith trace", exc_info=True)
            raise
        else:
            if run_id is not None:
                payload.setdefault("latency_ms", int((perf_counter() - started) * 1000))
                try:
                    self._client.update_run(run_id, outputs=payload, end_time=datetime.now(timezone.utc))
                except Exception:
                    logger.debug("Unable to update LangSmith trace", exc_info=True)
