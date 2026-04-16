"""
memory/long_term.py — Persistent memory backed by PostgreSQL.

FIX: Reordered imports so logger is always available before settings.
FIX: AsyncSession/MemoryEntry only referenced inside DB_AVAILABLE guard.
FIX: DB connection failure is fully caught with fallback to in-memory list.
"""
from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any, Dict, List, Optional

# Logger first — always available
from utils.logger import logger

# Optional DB imports — gracefully degrade if not installed/reachable
DB_AVAILABLE = False
try:
    import asyncpg  # noqa: F401 — side-effect: ensures asyncpg is installed
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
    from sqlalchemy import String, Text, DateTime, JSON, func, select
    DB_AVAILABLE = True
except ImportError:
    logger.warning("SQLAlchemy/asyncpg not installed — long-term memory uses in-memory fallback")

from config import get_settings

settings = get_settings()


# ── ORM Model ─────────────────────────────────────────────────────────────────

if DB_AVAILABLE:
    class _Base(DeclarativeBase):
        pass

    class MemoryEntry(_Base):
        __tablename__ = "memory_entries"

        id:           Mapped[int]           = mapped_column(primary_key=True)
        session_id:   Mapped[str]           = mapped_column(String(128), index=True)
        content_hash: Mapped[str]           = mapped_column(String(64), unique=True)
        fact:         Mapped[str]           = mapped_column(Text)
        source_url:   Mapped[Optional[str]] = mapped_column(Text, nullable=True)
        tags:         Mapped[Optional[dict]]= mapped_column(JSON, nullable=True)
        created_at:   Mapped[datetime]      = mapped_column(DateTime, default=datetime.utcnow)


# ── LongTermMemory ─────────────────────────────────────────────────────────────

class LongTermMemory:
    """
    Stores important facts across sessions.
    Gracefully falls back to an in-memory list when PostgreSQL is unavailable.
    """

    def __init__(self):
        self._engine = None
        self._fallback: List[Dict[str, Any]] = []

    async def initialize(self) -> None:
        """Connect to DB and create tables. Falls back silently on failure."""
        if not DB_AVAILABLE:
            logger.info("LongTermMemory: in-memory fallback mode (no DB libs)")
            return

        try:
            self._engine = create_async_engine(
                settings.DATABASE_URL,
                pool_size=settings.DATABASE_POOL_SIZE,
                echo=False,
                connect_args={"server_settings": {"application_name": "ask-web-agent"}},
            )
            async with self._engine.begin() as conn:
                await conn.run_sync(_Base.metadata.create_all)
            logger.info("LongTermMemory: connected to PostgreSQL ✅")
        except Exception as e:
            logger.warning(f"LongTermMemory: DB unavailable ({type(e).__name__}: {e}) — fallback mode")
            self._engine = None

    async def save_fact(
        self,
        fact: str,
        session_id: str = "global",
        source_url: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> None:
        """Persist a fact. Silently skips duplicates (content-addressed)."""
        content_hash = hashlib.sha256(fact.encode()).hexdigest()

        if self._engine and DB_AVAILABLE:
            try:
                async with AsyncSession(self._engine) as sess:
                    existing = await sess.scalar(
                        select(MemoryEntry).where(MemoryEntry.content_hash == content_hash)
                    )
                    if not existing:
                        sess.add(MemoryEntry(
                            session_id=session_id,
                            content_hash=content_hash,
                            fact=fact,
                            source_url=source_url,
                            tags={"tags": tags or []},
                        ))
                        await sess.commit()
                return
            except Exception as e:
                logger.warning(f"LongTermMemory.save_fact DB error: {e}")

        # Fallback
        if not any(e["hash"] == content_hash for e in self._fallback):
            self._fallback.append({
                "hash":       content_hash,
                "fact":       fact,
                "session_id": session_id,
                "source_url": source_url,
                "tags":       tags or [],
                "created_at": datetime.utcnow().isoformat(),
            })

    async def search_facts(
        self,
        query: str,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """Keyword search across stored facts."""
        keywords = [w for w in query.lower().split() if len(w) > 2]

        if self._engine and DB_AVAILABLE and keywords:
            try:
                async with AsyncSession(self._engine) as sess:
                    rows = (await sess.execute(
                        select(MemoryEntry)
                        .where(func.lower(MemoryEntry.fact).contains(keywords[0]))
                        .order_by(MemoryEntry.created_at.desc())
                        .limit(limit)
                    )).scalars().all()
                return [
                    {
                        "fact":       r.fact,
                        "source_url": r.source_url,
                        "tags":       r.tags,
                        "created_at": r.created_at.isoformat(),
                    }
                    for r in rows
                ]
            except Exception as e:
                logger.warning(f"LongTermMemory.search_facts DB error: {e}")

        # Fallback: simple keyword scoring
        scored = []
        for entry in self._fallback:
            score = sum(1 for kw in keywords if kw in entry["fact"].lower())
            if score > 0:
                scored.append((score, entry))
        scored.sort(key=lambda x: -x[0])
        return [e for _, e in scored[:limit]]


# Singleton
long_term_memory = LongTermMemory()
