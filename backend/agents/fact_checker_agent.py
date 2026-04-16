"""
agents/fact_checker_agent.py — Verifies key claims via cross-referencing web search.
FIX: Uses settings.get_anthropic_key(); robust JSON parsing with multiple fence formats.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List

import anthropic

from agents.base_agent import BaseAgent
from config import get_settings
from tools.web_search import web_search
from utils.logger import logger

settings = get_settings()


def _parse_json_response(text: str) -> Any:
    """Strip markdown fences and parse JSON robustly."""
    cleaned = text.strip()
    if "```" in cleaned:
        parts = cleaned.split("```")
        cleaned = parts[1] if len(parts) > 1 else parts[0]
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
    return json.loads(cleaned.strip())


class FactCheckerAgent(BaseAgent):
    """
    Extracts key factual claims and cross-checks each via web search.
    """

    def __init__(self):
        super().__init__(name="FactCheckerAgent")

    @property
    def system_prompt(self) -> str:
        return """\
You are a rigorous fact-checker. For each claim classify as:
- VERIFIED   — confirmed by multiple independent sources
- UNCERTAIN  — found in one source but not cross-verified
- DISPUTED   — conflicting information found
- NOT_FOUND  — no relevant sources located

Be objective. Output only valid JSON:
{"verified": [], "uncertain": [], "disputed": [], "not_found": []}"""

    async def check(self, answer: str, query: str) -> Dict[str, Any]:
        """Extract claims from answer and verify each one."""
        claude = anthropic.AsyncAnthropic(api_key=settings.get_anthropic_key())

        # Step 1: Extract key claims
        extract_resp = await claude.messages.create(
            model=settings.CLAUDE_MODEL,
            max_tokens=512,
            system=(
                "Extract 3-5 key verifiable factual claims from the text. "
                "Output ONLY a valid JSON array of strings, no markdown."
            ),
            messages=[
                {"role": "user", "content": f"Extract claims from:\n{answer}"}
            ],
        )
        claims_text = "".join(b.text for b in extract_resp.content if b.type == "text")

        try:
            claims: List[str] = _parse_json_response(claims_text)
            if not isinstance(claims, list):
                raise ValueError("Not a list")
        except Exception as e:
            logger.warning(f"[FactChecker] Claim extraction failed: {e}")
            return {"status": "skipped", "reason": "Could not extract claims"}

        # Step 2: Verify each claim
        verification_results = []
        for claim in claims[:5]:
            try:
                result = await web_search(f"fact check: {claim}", max_results=3)
                verification_results.append({
                    "claim": claim,
                    "search_results": [
                        {"title": r.get("title", ""), "snippet": r.get("snippet", ""), "url": r.get("url", "")}
                        for r in result.get("results", [])
                    ],
                })
            except Exception as e:
                verification_results.append({"claim": claim, "error": str(e)})

        # Step 3: Classify claims
        classify_resp = await claude.messages.create(
            model=settings.CLAUDE_MODEL,
            max_tokens=1024,
            system=self.system_prompt,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Classify these claims based on the search results:\n"
                        f"{json.dumps(verification_results, indent=2)}"
                    ),
                }
            ],
        )
        report_text = "".join(b.text for b in classify_resp.content if b.type == "text")

        try:
            report = _parse_json_response(report_text)
        except Exception:
            report = {"raw": report_text}

        return {
            "claims_checked": len(claims),
            "report": report,
            "agent": self.name,
        }
