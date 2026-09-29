"""Bounded in-process memory for conversational references in one video session."""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock


@dataclass(frozen=True)
class ConversationTurn:
    question: str
    answer: str


class ConversationMemory:
    """Memory is deliberately keyed by both session and video to prevent cross-video bleed."""

    def __init__(self, max_turns: int = 6) -> None:
        self._max_turns = max_turns
        self._sessions: dict[tuple[str, str], list[ConversationTurn]] = {}
        self._lock = RLock()

    def history(self, session_id: str, video_id: str) -> list[ConversationTurn]:
        with self._lock:
            return list(self._sessions.get((session_id, video_id), []))

    def add(self, session_id: str, video_id: str, question: str, answer: str) -> None:
        with self._lock:
            key = (session_id, video_id)
            turns = self._sessions.setdefault(key, [])
            turns.append(ConversationTurn(question=question, answer=answer))
            del turns[:-self._max_turns]

    def clear(self, session_id: str, video_id: str | None = None) -> int:
        with self._lock:
            keys = [key for key in self._sessions if key[0] == session_id and (video_id is None or key[1] == video_id)]
            for key in keys:
                del self._sessions[key]
            return len(keys)
