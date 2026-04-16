"""
tools/content_extractor.py — Fetch and clean text from a given URL.
FIX: Handles more edge cases; URL scheme validation; better error returns.
"""
from __future__ import annotations

import re
from typing import Dict, Any
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from tools.tool_registry import ToolDefinition, registry
from utils.logger import logger

MAX_CONTENT_CHARS = 4000

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; AskWebAgent/1.0; "
        "+https://github.com/yourusername/ask-the-web-agent)"
    )
}

STRIP_TAGS = ["script", "style", "nav", "footer", "header", "aside",
              "advertisement", "iframe", "noscript", "button", "form"]


async def extract_content(url: str, max_chars: int = MAX_CONTENT_CHARS) -> Dict[str, Any]:
    """Fetch a URL and return cleaned text content + metadata."""
    logger.info(f"[extract_content] Fetching: {url}")

    # Validate URL
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return {"error": f"Invalid URL scheme '{parsed.scheme}'. Must be http or https.", "url": url}
        if not parsed.netloc:
            return {"error": "Invalid URL: no domain found.", "url": url}
    except Exception as e:
        return {"error": f"URL parse error: {e}", "url": url}

    try:
        async with httpx.AsyncClient(
            timeout=15,
            headers=HEADERS,
            follow_redirects=True,
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            html = resp.text
    except httpx.TimeoutException:
        return {"error": "Request timed out (15s)", "url": url}
    except httpx.HTTPStatusError as e:
        return {"error": f"HTTP {e.response.status_code}: {e.response.reason_phrase}", "url": url}
    except Exception as e:
        return {"error": f"Fetch error: {type(e).__name__}: {e}", "url": url}

    # Parse HTML
    try:
        soup = BeautifulSoup(html, "lxml")
    except Exception:
        soup = BeautifulSoup(html, "html.parser")

    for tag in soup(STRIP_TAGS):
        tag.decompose()

    body = (
        soup.find("article")
        or soup.find("main")
        or soup.find(attrs={"role": "main"})
        or soup.find("body")
    )
    if not body:
        return {"error": "No parseable body found", "url": url}

    raw_text = body.get_text(separator="\n")
    lines = [ln.strip() for ln in raw_text.splitlines() if ln.strip()]
    cleaned = re.sub(r"\n{3,}", "\n\n", "\n".join(lines))

    content = cleaned[:max_chars]
    if len(cleaned) > max_chars:
        content += "\n\n[Content truncated — use a shorter max_chars or read specific sections]"

    title_tag = soup.find("title")
    title = title_tag.get_text().strip() if title_tag else ""

    return {
        "url":        url,
        "title":      title,
        "content":    content,
        "char_count": len(content),
    }


registry.register(ToolDefinition(
    name="extract_webpage_content",
    description=(
        "Fetch and read the full text content of a specific webpage URL. "
        "Use this when a search snippet is too brief and you need the complete article. "
        "Returns cleaned plain text with the page title."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "Full URL (must start with http:// or https://).",
            },
            "max_chars": {
                "type": "integer",
                "description": "Max characters to return. Default 4000.",
                "default": 4000,
            },
        },
        "required": ["url"],
    },
    executor=extract_content,
    tags=["web", "content", "reading"],
))
