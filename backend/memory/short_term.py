"""
memory/short_term.py — In-process conversation memory with asyncio.Lock.

Stores the last N turns per session. Thread-safe, no external dependencies.
Resets on server restart — use long_term.py for persistence.
"""
from __future__ import annotations

import asyncio
from collections import deque
from datetime import datetime
from typing import Any, Dict, List, Optional


class ConversationMemory:
    """Per-session rolling window of conversation turns."""

    def __init__(self, max_turns: int = 20):
        self._store: Dict[str, deque] = {}
        self._lock  = asyncio.Lock()
        self.max_turns = max_turns

    async def add_turn(
        self,
        session_id: str,
        role: str,       # "user" | "assistant"
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        async with self._lock:
            if session_id not in self._store:
                self._store[session_id] = deque(maxlen=self.max_turns)
            self._store[session_id].append({
                "role":      role,
                "content":   content,
                "timestamp": datetime.utcnow().isoformat(),
                "metadata":  metadata or {},
            })

    async def get_history(
        self,
        session_id: str,
        last_n: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Return full turn history (or last N turns)."""
        async with self._lock:
            turns = list(self._store.get(session_id, []))
        return turns[-last_n:] if last_n else turns

    async def get_messages_for_claude(
        self,
        session_id: str,
    ) -> List[Dict[str, str]]:
        """
        Return history formatted as [{role, content}] for Claude's messages= param.
        Excludes metadata and timestamp fields.
        """
        history = await self.get_history(session_id)
        return [{"role": t["role"], "content": t["content"]} for t in history]

    async def clear(self, session_id: str) -> None:
        async with self._lock:
            self._store.pop(session_id, None)

    async def all_sessions(self) -> List[str]:
        async with self._lock:
            return list(self._store.keys())


# Global singleton
short_term_memory = ConversationMemory(max_turns=20)
