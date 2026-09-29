"""Maximal marginal relevance selection for diversity in final evidence."""

from __future__ import annotations

import math

from backend.models import RetrievedChunk


def select_mmr(candidates: list[RetrievedChunk], limit: int, lambda_mult: float = 0.72) -> list[RetrievedChunk]:
    """Choose relevant chunks while penalizing near-duplicate vector content."""

    remaining = list(candidates)
    selected: list[RetrievedChunk] = []
    while remaining and len(selected) < limit:
        best = max(
            remaining,
            key=lambda candidate: lambda_mult * candidate.score
            - (1 - lambda_mult) * max((_cosine(candidate.vector, chosen.vector) for chosen in selected), default=0.0),
        )
        selected.append(best)
        remaining.remove(best)
    return selected


def _cosine(left: list[float] | None, right: list[float] | None) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    denominator = math.sqrt(sum(value * value for value in left)) * math.sqrt(sum(value * value for value in right))
    return sum(a * b for a, b in zip(left, right, strict=True)) / denominator if denominator else 0.0
