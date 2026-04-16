"""
evaluation/evaluator.py — Response quality metrics.

FIX: Corrected broken regex in _citation_score (double-escaped in raw string).
FIX: Uses settings.get_anthropic_key() for safe key access.
FIX: json import moved to top level.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List
from urllib.parse import urlparse

import anthropic

from config import get_settings
from utils.logger import logger

settings = get_settings()


class Evaluator:
    """Scores a (query, answer, sources) triple on multiple quality axes."""

    async def evaluate(
        self,
        query: str,
        answer: str,
        sources: List[Dict[str, str]],
        latency_ms: float = 0.0,
    ) -> Dict[str, Any]:
        """Return a dict of quality scores."""
        scores: Dict[str, Any] = {
            "source_count":      len(sources),
            "source_diversity":  _domain_diversity(sources),
            "citation_score":    _citation_score(answer),
            "word_count":        len(answer.split()),
            "latency_ms":        latency_ms,
        }

        try:
            llm_scores = await self._llm_evaluate(query, answer)
            scores.update(llm_scores)
        except Exception as e:
            logger.warning(f"[Evaluator] LLM evaluation failed: {e}")
            scores.update({
                "relevance":         0.5,
                "completeness":      0.5,
                "hallucination_risk": "unknown",
                "reasoning":         "Evaluation unavailable",
            })

        scores["overall"] = round(
            scores.get("relevance", 0)    * 0.35
            + scores.get("completeness", 0) * 0.25
            + min(scores["source_count"] / 3, 1.0) * 0.20
            + scores["citation_score"]     * 0.20,
            3,
        )

        return scores

    async def _llm_evaluate(self, query: str, answer: str) -> Dict[str, Any]:
        """Use Claude to judge relevance, completeness, and hallucination risk."""
        claude = anthropic.AsyncAnthropic(api_key=settings.get_anthropic_key())

        prompt = (
            f"Evaluate this answer to the query.\n\n"
            f"Query: {query}\n\n"
            f"Answer (first 1500 chars):\n{answer[:1500]}\n\n"
            "Rate on a 0.0-1.0 scale. Output ONLY valid JSON (no markdown):\n"
            '{"relevance": 0.0, "completeness": 0.0, '
            '"hallucination_risk": "low", "reasoning": "..."}'
        )

        response = await claude.messages.create(
            model=settings.CLAUDE_MODEL,
            max_tokens=256,
            system="You are a strict evaluator. Output only valid JSON, no markdown fences.",
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(b.text for b in response.content if b.type == "text").strip()

        # Strip any accidental markdown fences
        if "```" in text:
            parts = text.split("```")
            text = parts[1] if len(parts) > 1 else parts[0]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()

        try:
            return json.loads(text)
        except Exception:
            return {
                "relevance": 0.5,
                "completeness": 0.5,
                "hallucination_risk": "unknown",
                "reasoning": "Parse error",
            }


# ── Helpers ────────────────────────────────────────────────────────────────────

def _citation_score(answer: str) -> float:
    """
    Fraction of paragraphs that contain a URL or citation marker.

    FIX: Original regex used r"\\[\\d+\\]" which matched literal backslashes.
    Correct pattern: r"\[\d+\]" — matches [1], [2], etc.
    """
    paragraphs = [p.strip() for p in answer.split("\n\n") if p.strip()]
    if not paragraphs:
        return 0.0

    # FIX: Correct regex — no double-escaping in raw strings
    citation_pattern = re.compile(
        r"https?://"       # bare URL
        r"|Source:"        # [Source: ...]
        r"|\[\d+\]"        # footnote marker like [1]
        r"|\.com"          # domain hint
        r"|\.org"          # domain hint
        r"|\.gov"          # domain hint
    )

    cited = sum(1 for p in paragraphs if citation_pattern.search(p))
    return round(cited / len(paragraphs), 2)


def _domain_diversity(sources: List[Dict[str, str]]) -> int:
    """Count unique root domains (e.g. bbc.com, cnn.com) across all sources."""
    domains: set = set()
    for s in sources:
        try:
            netloc = urlparse(s.get("url", "")).netloc
            domain = netloc.lstrip("www.")
            if domain:
                domains.add(domain)
        except Exception:
            pass
    return len(domains)
