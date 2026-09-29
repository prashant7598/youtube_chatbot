"""Cheap query router that selects retrieval behavior without an agent round-trip."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class QueryRoute(StrEnum):
    FACTUAL = "factual_lookup"
    CONCEPTUAL = "conceptual_explanation"
    SUMMARY = "summarization"
    COMPARISON = "comparison"
    TIMELINE = "timeline"
    FOLLOW_UP = "conversational_follow_up"
    CONVERSATIONAL = "conversational"
    OUT_OF_SCOPE = "out_of_scope"


@dataclass(frozen=True)
class RouteDecision:
    route: QueryRoute
    candidate_multiplier: int
    chronological: bool = False


class QueryRouter:
    """Route common question types with transparent, testable lexical rules."""

    def route(self, question: str, has_memory: bool) -> RouteDecision:
        lowered = question.lower().strip()
        if not lowered:
            return RouteDecision(QueryRoute.OUT_OF_SCOPE, 1)
        if lowered in {"hi", "hello", "hey", "thanks", "thank you"}:
            return RouteDecision(QueryRoute.CONVERSATIONAL, 1)
        if any(token in lowered for token in ("summarize", "summary", "overview", "recap")):
            return RouteDecision(QueryRoute.SUMMARY, 2, chronological=True)
        if any(token in lowered for token in ("compare", "difference", "versus", " vs ")):
            return RouteDecision(QueryRoute.COMPARISON, 2)
        if any(token in lowered for token in ("when", "timestamp", "time does", "minute", "at what")):
            return RouteDecision(QueryRoute.TIMELINE, 2, chronological=True)
        if has_memory and any(token in lowered.split() for token in ("it", "that", "this", "they", "why", "how")):
            return RouteDecision(QueryRoute.FOLLOW_UP, 2)
        if any(token in lowered for token in ("why", "how does", "explain", "what is", "meaning")):
            return RouteDecision(QueryRoute.CONCEPTUAL, 2)
        return RouteDecision(QueryRoute.FACTUAL, 1)
