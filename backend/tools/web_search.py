"""
tools/web_search.py — Web search tool (Tavily primary, SerpAPI fallback, stub for dev).

FIX: Uses settings.get_anthropic_key() pattern not needed here (no Claude call),
     but TAVILY_API_KEY/SERPAPI_KEY are checked safely via settings.
"""
from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

import httpx

from config import get_settings
from tools.tool_registry import ToolDefinition, registry
from utils.logger import logger

settings = get_settings()


# ── Tavily ────────────────────────────────────────────────────────────────────

async def _tavily_search(
    query: str,
    max_results: int = 5,
    search_depth: str = "advanced",
) -> Dict[str, Any]:
    """Call Tavily Search API — purpose-built for LLM agents."""
    url = "https://api.tavily.com/search"
    payload = {
        "api_key":           settings.TAVILY_API_KEY,
        "query":             query,
        "max_results":       max_results,
        "search_depth":      search_depth,
        "include_answer":    True,
        "include_raw_content": False,
        "include_images":    False,
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()

    results = [
        {
            "title":          r.get("title", ""),
            "url":            r.get("url", ""),
            "snippet":        r.get("content", "")[:800],
            "score":          r.get("score", 0),
            "published_date": r.get("published_date", ""),
        }
        for r in data.get("results", [])
    ]
    return {
        "query":   query,
        "answer":  data.get("answer", ""),
        "results": results,
        "source":  "tavily",
    }


# ── SerpAPI ───────────────────────────────────────────────────────────────────

async def _serpapi_search(query: str, max_results: int = 5) -> Dict[str, Any]:
    """Fallback: Google Search via SerpAPI."""
    params = {
        "q":       query,
        "api_key": settings.SERPAPI_KEY,
        "engine":  "google",
        "num":     max_results,
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get("https://serpapi.com/search", params=params)
        resp.raise_for_status()
        data = resp.json()

    results = [
        {
            "title":          r.get("title", ""),
            "url":            r.get("link", ""),
            "snippet":        r.get("snippet", ""),
            "score":          1.0,
            "published_date": r.get("date", ""),
        }
        for r in data.get("organic_results", [])[:max_results]
    ]
    return {"query": query, "answer": "", "results": results, "source": "serpapi"}


# ── Stub (no keys) ────────────────────────────────────────────────────────────

def _stub_search(query: str, max_results: int = 5) -> Dict[str, Any]:
    """Dev stub — returns placeholder results when no API keys are configured."""
    logger.warning(
        "⚠️  No search API keys set. Configure TAVILY_API_KEY in .env for real results."
    )
    return {
        "query":   query,
        "answer":  f"[DEV STUB] No real search results. Set TAVILY_API_KEY in .env.",
        "results": [
            {
                "title":          f"Stub Result {i} for '{query}'",
                "url":            f"https://example.com/stub-{i}",
                "snippet":        f"Configure TAVILY_API_KEY in .env to get real results. (stub {i})",
                "score":          1.0 - i * 0.1,
                "published_date": "",
            }
            for i in range(1, min(max_results, 4) + 1)
        ],
        "source": "stub",
    }


# ── Unified entry point ───────────────────────────────────────────────────────

async def web_search(query: str, max_results: int = 5) -> Dict[str, Any]:
    """
    Try Tavily → SerpAPI → stub, in order of preference.
    Never raises — always returns a result dict.
    """
    logger.info(f"[web_search] '{query}' (max={max_results})")

    if settings.TAVILY_API_KEY:
        try:
            return await _tavily_search(query, max_results=max_results)
        except Exception as e:
            logger.warning(f"[web_search] Tavily failed: {e}")

    if settings.SERPAPI_KEY:
        try:
            return await _serpapi_search(query, max_results=max_results)
        except Exception as e:
            logger.warning(f"[web_search] SerpAPI failed: {e}")

    return _stub_search(query, max_results=max_results)


async def multi_query_search(
    queries: List[str],
    max_results_per_query: int = 3,
) -> List[Dict[str, Any]]:
    """Run multiple search queries concurrently and return all results."""
    if not queries:
        return []
    tasks = [web_search(q, max_results=max_results_per_query) for q in queries]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return [r for r in results if isinstance(r, dict)]


# ── Register with global tool registry ───────────────────────────────────────

registry.register(ToolDefinition(
    name="web_search",
    description=(
        "Search the web for real-time information. Use this to find current facts, "
        "news, prices, or anything that may have changed recently. "
        "Returns titles, URLs, and text snippets from top results."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query. Be specific and descriptive.",
            },
            "max_results": {
                "type": "integer",
                "description": "Number of results to return (1-10). Default 5.",
                "default": 5,
            },
        },
        "required": ["query"],
    },
    executor=web_search,
    tags=["search", "web", "realtime"],
))
