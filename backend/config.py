"""
config.py — Centralized configuration using pydantic-settings.
All secrets come from environment variables (never hardcoded).

FIX: ANTHROPIC_API_KEY is now Optional so the app can import cleanly
even if .env is not yet configured. A clear error is raised at first use
instead of at import time (better DX).
"""
from __future__ import annotations

from functools import lru_cache
from typing import List, Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── App ──────────────────────────────────────────────────────────────────
    APP_NAME: str = "Ask-the-Web Agent"
    APP_VERSION: str = "1.0.0"
    # FIX: DEBUG defaults True so /docs is available in development
    DEBUG: bool = True
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ]

    # ── Anthropic (Claude) ────────────────────────────────────────────────────
    # FIX: Optional with None default — validated at first use, not import time
    ANTHROPIC_API_KEY: Optional[str] = None
    CLAUDE_MODEL: str = "claude-sonnet-4-6"
    CLAUDE_MAX_TOKENS: int = 4096
    CLAUDE_TEMPERATURE: float = 0.0

    # ── Search APIs ───────────────────────────────────────────────────────────
    TAVILY_API_KEY: Optional[str] = None
    SERPAPI_KEY: Optional[str] = None

    # ── Database (optional — app works without it) ────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/askweb"
    DATABASE_POOL_SIZE: int = 10

    # ── Redis (optional caching) ──────────────────────────────────────────────
    REDIS_URL: Optional[str] = None
    CACHE_TTL_SECONDS: int = 300

    # ── Agent behaviour ───────────────────────────────────────────────────────
    MAX_AGENT_ITERATIONS: int = 10
    MAX_SEARCH_RESULTS: int = 5
    MAX_PARALLEL_SEARCHES: int = 3
    REFLECTION_ENABLED: bool = True
    MULTI_AGENT_ENABLED: bool = True

    # ── Logging ───────────────────────────────────────────────────────────────
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "text"   # "text" for local dev; "json" for production

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
        "extra": "ignore",       # ignore unknown env vars (avoids crashes)
    }

    def get_anthropic_key(self) -> str:
        """
        Returns the API key or raises a clear, actionable error.
        Call this instead of accessing ANTHROPIC_API_KEY directly.
        """
        if not self.ANTHROPIC_API_KEY:
            raise RuntimeError(
                "\n\n❌  ANTHROPIC_API_KEY is not set!\n"
                "    1. Copy .env.example → .env\n"
                "    2. Add your key: ANTHROPIC_API_KEY=sk-ant-...\n"
                "    3. Restart the server\n"
            )
        return self.ANTHROPIC_API_KEY


@lru_cache
def get_settings() -> Settings:
    """Cached singleton — import this everywhere."""
    return Settings()
