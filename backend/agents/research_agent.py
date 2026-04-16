"""
agents/research_agent.py — Deep research agent using parallel multi-angle search.
FIX: Uses settings.get_anthropic_key() for safe key access.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List

import anthropic

from agents.base_agent import BaseAgent
from config import get_settings
from tools.web_search import multi_query_search
from utils.logger import logger

settings = get_settings()


class ResearchAgent(BaseAgent):
    """
    Research Agent — thorough, multi-angle investigator.
    Decomposes complex queries, runs parallel searches, synthesises answers.
    """

    def __init__(self):
        super().__init__(name="ResearchAgent")

    @property
    def system_prompt(self) -> str:
        from datetime import date
        return f"""\
You are an expert research agent. Your goal is thorough, accurate research.

Strategy:
1. Decompose complex queries into 2-3 specific sub-questions
2. Search for each angle separately (use web_search multiple times)
3. Read key source pages with extract_webpage_content when needed
4. Synthesise findings with clear citations

Always cite every factual claim. Today: {date.today().isoformat()}"""

    async def run_parallel_research(
        self,
        query: str,
        session_id: str = "default",
    ) -> Dict[str, Any]:
        """
        ReWOO-style: plan sub-queries upfront, execute in parallel, synthesise.
        """
        claude = anthropic.AsyncAnthropic(api_key=settings.get_anthropic_key())
        logger.info(f"[ResearchAgent] Planning parallel research for: '{query[:60]}'")

        # Step 1: Generate sub-queries
        plan_response = await claude.messages.create(
            model=settings.CLAUDE_MODEL,
            max_tokens=512,
            system=(
                "You are a research planner. "
                "Output ONLY a valid JSON array of 2-3 search query strings. "
                "No explanation, no markdown fences — just the JSON array."
            ),
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Generate 2-3 targeted web search queries to answer:\n'{query}'\n\n"
                        'Output format: ["query1", "query2", "query3"]'
                    ),
                }
            ],
        )

        plan_text = "".join(
            b.text for b in plan_response.content if b.type == "text"
        ).strip()

        # Robustly parse JSON (strip markdown fences if Claude adds them)
        try:
            cleaned = plan_text
            if "```" in cleaned:
                parts = cleaned.split("```")
                # take the part after the first fence
                cleaned = parts[1] if len(parts) > 1 else parts[0]
                if cleaned.startswith("json"):
                    cleaned = cleaned[4:]
            sub_queries: List[str] = json.loads(cleaned.strip())
            if not isinstance(sub_queries, list):
                raise ValueError("Not a list")
        except Exception as e:
            logger.warning(f"[ResearchAgent] Sub-query parse failed ({e}), using original query")
            sub_queries = [query]

        logger.info(f"[ResearchAgent] Sub-queries planned: {sub_queries}")

        # Step 2: Execute all searches in parallel
        all_results = await multi_query_search(
            sub_queries,
            max_results_per_query=settings.MAX_SEARCH_RESULTS,
        )

        # Step 3: Build context and synthesise
        combined_context = "\n\n".join(
            f"## Results for: {r['query']}\n"
            + "\n".join(
                f"- [{item['title']}]({item['url']}): {item['snippet']}"
                for item in r.get("results", [])
            )
            for r in all_results
            if isinstance(r, dict)
        )

        if not combined_context.strip():
            combined_context = "No search results were retrieved. Please provide a best-effort answer."

        synthesis_response = await claude.messages.create(
            model=settings.CLAUDE_MODEL,
            max_tokens=settings.CLAUDE_MAX_TOKENS,
            system=self.system_prompt,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Using the research results below, answer: '{query}'\n\n"
                        f"{combined_context}\n\n"
                        "Provide a comprehensive, well-cited answer."
                    ),
                }
            ],
        )

        final_answer = "".join(
            b.text for b in synthesis_response.content if b.type == "text"
        )

        sources = []
        for r in all_results:
            if isinstance(r, dict):
                for item in r.get("results", []):
                    if item.get("url"):
                        sources.append({"title": item.get("title", ""), "url": item["url"]})

        return {
            "answer": final_answer,
            "sources": sources,
            "sub_queries": sub_queries,
            "agent": self.name,
        }
