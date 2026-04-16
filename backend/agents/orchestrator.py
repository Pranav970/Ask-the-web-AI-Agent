"""
agents/orchestrator.py — Orchestrator-Worker pattern.

Pipeline:
  1. Router   → classifies query complexity: simple | deep | factual
  2. Workers  → ResearchAgent (parallel) + SummarizerAgent + FactCheckerAgent
  3. Evaluator → quality-scores the final answer

FIX: Uses settings.get_anthropic_key(); all sub-agents create their own clients.
"""
from __future__ import annotations

import json
from typing import Any, AsyncGenerator, Dict, Optional

import anthropic

from agents.base_agent import BaseAgent
from agents.research_agent import ResearchAgent
from agents.summarizer_agent import SummarizerAgent
from agents.fact_checker_agent import FactCheckerAgent
from evaluation.evaluator import Evaluator
from config import get_settings
from utils.logger import logger

settings = get_settings()

ROUTE_SIMPLE  = "simple"
ROUTE_DEEP    = "deep"
ROUTE_FACTUAL = "factual"
VALID_ROUTES  = {ROUTE_SIMPLE, ROUTE_DEEP, ROUTE_FACTUAL}


class OrchestratorAgent(BaseAgent):
    """Top-level coordinator — routes, delegates, evaluates."""

    def __init__(self):
        super().__init__(name="OrchestratorAgent")
        self._research     = ResearchAgent()
        self._summarizer   = SummarizerAgent()
        self._fact_checker = FactCheckerAgent()
        self._evaluator    = Evaluator()

    @property
    def system_prompt(self) -> str:
        from datetime import date
        return (
            "You are a helpful AI assistant. "
            "Answer accurately using web-sourced, cited information. "
            f"Today: {date.today().isoformat()}"
        )

    # ── Routing ───────────────────────────────────────────────────────────────

    async def _decide_route(self, query: str) -> str:
        """Classify query complexity via a cheap single Claude call."""
        claude = anthropic.AsyncAnthropic(api_key=settings.get_anthropic_key())
        try:
            response = await claude.messages.create(
                model=settings.CLAUDE_MODEL,
                max_tokens=16,
                system=(
                    "Classify this query. Reply with ONE word only: simple, deep, or factual.\n"
                    "- simple:  conversational, opinion, or very straightforward fact\n"
                    "- deep:    multi-faceted research requiring several sources\n"
                    "- factual: specific fact-check or verification task"
                ),
                messages=[{"role": "user", "content": query}],
            )
            route = "".join(b.text for b in response.content if b.type == "text").strip().lower()
        except Exception as e:
            logger.warning(f"[Orchestrator] Routing failed ({e}), defaulting to simple")
            route = ROUTE_SIMPLE

        if route not in VALID_ROUTES:
            logger.warning(f"[Orchestrator] Unexpected route '{route}', defaulting to simple")
            route = ROUTE_SIMPLE

        logger.info(f"[Orchestrator] Route → {route}")
        return route

    # ── Main process ──────────────────────────────────────────────────────────

    async def process(
        self,
        query: str,
        session_id: str = "default",
        force_route: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Orchestrate the full pipeline and return a rich result dict.
        """
        route = force_route if force_route in VALID_ROUTES else await self._decide_route(query)

        if route == ROUTE_SIMPLE:
            result = await self.run(query, session_id=session_id)

        elif route == ROUTE_DEEP:
            research_result = await self._research.run_parallel_research(
                query, session_id=session_id
            )
            summary = await self._summarizer.summarize(research_result["answer"], query)
            research_result["answer"] = summary
            result = research_result

        else:  # factual
            research_result = await self._research.run(query, session_id=session_id)
            fact_check = await self._fact_checker.check(research_result["answer"], query)
            research_result["fact_check"] = fact_check
            result = research_result

        eval_scores = await self._evaluator.evaluate(
            query=query,
            answer=result.get("answer", ""),
            sources=result.get("sources", []),
        )
        result["evaluation"] = eval_scores
        result["route"] = route
        return result

    # ── Streaming ─────────────────────────────────────────────────────────────

    async def stream(
        self,
        query: str,
        session_id: str = "default",
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Streaming orchestration via Server-Sent Events.
        Always uses the base ReACT stream for low latency,
        appending evaluation scores at the end.
        """
        route = await self._decide_route(query)
        yield {"type": "thinking", "content": f"📋 Strategy: **{route}** research"}

        collected_sources = []
        full_answer_parts = []

        async for chunk in super().stream(query, session_id=session_id):
            yield chunk

            if chunk["type"] == "text":
                full_answer_parts.append(chunk["content"])
            elif chunk["type"] == "source":
                collected_sources.append(chunk["content"])
            elif chunk["type"] == "done":
                # Merge sources from done payload
                done_sources = chunk["content"].get("sources", [])
                all_sources = collected_sources + [
                    s for s in done_sources
                    if s not in collected_sources
                ]
                full_answer = "".join(full_answer_parts)

                eval_scores = await self._evaluator.evaluate(
                    query=query,
                    answer=full_answer or "(streamed answer)",
                    sources=all_sources,
                )
                yield {"type": "evaluation", "content": eval_scores}
