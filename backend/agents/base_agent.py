"""
agents/base_agent.py — Base ReACT (Reason + Act) agent.

FIX: Removed unused abstractmethod import; BaseAgent is now a concrete
     class (not ABC) since no method is truly abstract — all sub-classes
     override system_prompt as a @property, not an @abstractmethod.
FIX: API key is fetched via settings.get_anthropic_key() so missing keys
     surface with a clear error message rather than a cryptic AuthError.

Implements the core agentic loop:
  1. Think  — Claude reasons about the goal & decides next action
  2. Act    — Call a tool (web_search, extract_webpage_content, …)
  3. Observe — Feed tool output back into the conversation
  4. Repeat  until final answer ready (or max_iterations reached)
"""
from __future__ import annotations

import json
from typing import Any, AsyncGenerator, Dict, List, Optional

import anthropic

from config import get_settings
from tools.tool_registry import registry
from memory.short_term import short_term_memory
from utils.logger import logger

settings = get_settings()


def _get_claude_client() -> anthropic.AsyncAnthropic:
    """Lazily create the Anthropic client so a missing key surfaces clearly."""
    return anthropic.AsyncAnthropic(api_key=settings.get_anthropic_key())


# ── System prompt template ────────────────────────────────────────────────────

BASE_SYSTEM_PROMPT = """\
You are an intelligent research assistant that finds accurate, \
up-to-date information from the web.

## Capabilities
- Search the web in real-time using the `web_search` tool
- Read full webpage content using `extract_webpage_content`
- Synthesize information from multiple sources
- Cite every factual claim with its source URL

## Instructions
1. **Think before acting**: Analyse the query and plan your search strategy
2. **Search multiple angles**: Use 2-3 targeted searches for complex queries
3. **Be specific**: Prefer precise queries over vague ones
4. **Cite sources**: Every factual statement MUST include [Source: URL]
5. **Acknowledge uncertainty**: If information is conflicting or unclear, say so

## Output format
Provide a structured response with:
- A direct answer to the query
- Supporting evidence with citations
- A **Sources** section at the end listing all referenced URLs

Today's date: {date}
"""


# ── Base agent ────────────────────────────────────────────────────────────────

class BaseAgent:
    """
    Concrete base class for all agents.
    Sub-classes override `system_prompt` (property) to customise behaviour.
    """

    def __init__(self, name: str, extra_tools: Optional[List[str]] = None):
        self.name = name
        self.extra_tools = extra_tools or []
        self.max_iterations = settings.MAX_AGENT_ITERATIONS

    @property
    def system_prompt(self) -> str:
        from datetime import date
        return BASE_SYSTEM_PROMPT.format(date=date.today().isoformat())

    def _get_tools(self) -> List[Dict[str, Any]]:
        """Return Anthropic-formatted tool definitions for this agent."""
        return registry.all_definitions()

    # ── Full (non-streaming) run ──────────────────────────────────────────────

    async def run(
        self,
        query: str,
        session_id: str = "default",
        context: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Full ReACT loop. Returns the final structured result dict.
        """
        claude = _get_claude_client()
        logger.info(f"[{self.name}] Starting run: '{query[:80]}'")

        user_content = query
        if context:
            user_content = f"Context from previous research:\n{context}\n\n---\n\nQuery: {query}"

        # Load conversation history for multi-turn support
        history = await short_term_memory.get_messages_for_claude(session_id)
        messages = history + [{"role": "user", "content": user_content}]

        thoughts: List[str] = []
        tool_calls_made: List[Dict[str, Any]] = []
        sources: List[Dict[str, str]] = []
        final_answer = ""
        iteration = 0

        for iteration in range(self.max_iterations):
            logger.info(f"[{self.name}] Iteration {iteration + 1}/{self.max_iterations}")

            try:
                response = await claude.messages.create(
                    model=settings.CLAUDE_MODEL,
                    max_tokens=settings.CLAUDE_MAX_TOKENS,
                    system=self.system_prompt,
                    tools=self._get_tools(),
                    messages=messages,
                )
            except anthropic.APIError as e:
                logger.error(f"[{self.name}] Claude API error: {e}")
                raise

            tool_calls_this_round: List[Dict[str, Any]] = []
            text_output = ""

            for block in response.content:
                if block.type == "text":
                    text_output += block.text
                elif block.type == "tool_use":
                    tool_calls_this_round.append(
                        {"name": block.name, "input": block.input, "id": block.id}
                    )

            if text_output:
                thoughts.append(text_output)

            # No tool calls → answer is ready
            if response.stop_reason == "end_turn" or not tool_calls_this_round:
                final_answer = text_output
                break

            # Execute all tool calls (in parallel)
            tool_results = await registry.execute_parallel(tool_calls_this_round)
            tool_calls_made.extend(tool_calls_this_round)

            # Harvest sources from web_search results
            for call, result in zip(tool_calls_this_round, tool_results):
                if call["name"] == "web_search":
                    try:
                        data = json.loads(result["content"])
                        for r in data.get("results", []):
                            if r.get("url"):
                                sources.append({"title": r.get("title", ""), "url": r["url"]})
                    except Exception:
                        pass

            # Feed results back into conversation
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})

        # Optional self-reflection pass
        if settings.REFLECTION_ENABLED and final_answer:
            final_answer = await self._reflect(
                query=query,
                initial_answer=final_answer,
                messages=messages,
                claude=claude,
            )

        # Persist to short-term memory
        await short_term_memory.add_turn(session_id, "user", query)
        await short_term_memory.add_turn(session_id, "assistant", final_answer)

        return {
            "answer": final_answer,
            "sources": _deduplicate_sources(sources),
            "thoughts": thoughts,
            "tool_calls": len(tool_calls_made),
            "iterations": iteration + 1,
            "agent": self.name,
        }

    # ── Streaming run ─────────────────────────────────────────────────────────

    async def stream(
        self,
        query: str,
        session_id: str = "default",
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Streaming ReACT loop.
        Yields SSE-compatible dicts with type: thinking | text | source | done.
        """
        claude = _get_claude_client()
        logger.info(f"[{self.name}] Streaming: '{query[:80]}'")

        history = await short_term_memory.get_messages_for_claude(session_id)
        messages = history + [{"role": "user", "content": query}]

        sources: List[Dict[str, str]] = []
        full_answer = ""
        iteration = 0

        for iteration in range(self.max_iterations):
            response = await claude.messages.create(
                model=settings.CLAUDE_MODEL,
                max_tokens=settings.CLAUDE_MAX_TOKENS,
                system=self.system_prompt,
                tools=self._get_tools(),
                messages=messages,
            )

            tool_calls_this_round = []
            text_output = ""

            for block in response.content:
                if block.type == "text":
                    text_output += block.text
                    yield {"type": "text", "content": block.text}
                elif block.type == "tool_use":
                    tool_calls_this_round.append(
                        {"name": block.name, "input": block.input, "id": block.id}
                    )
                    yield {
                        "type": "thinking",
                        "content": f"🔍 Searching: **{block.input.get('query', block.name)}**",
                    }

            if response.stop_reason == "end_turn" or not tool_calls_this_round:
                full_answer = text_output
                break

            tool_results = await registry.execute_parallel(tool_calls_this_round)

            for call, result in zip(tool_calls_this_round, tool_results):
                if call["name"] == "web_search":
                    try:
                        data = json.loads(result["content"])
                        for r in data.get("results", []):
                            if r.get("url"):
                                src = {"title": r.get("title", ""), "url": r["url"]}
                                sources.append(src)
                                yield {"type": "source", "content": src}
                    except Exception:
                        pass

            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})

        await short_term_memory.add_turn(session_id, "user", query)
        await short_term_memory.add_turn(session_id, "assistant", full_answer)

        yield {
            "type": "done",
            "content": {
                "sources": _deduplicate_sources(sources),
                "iterations": iteration + 1,
            },
        }

    # ── Reflection pass ───────────────────────────────────────────────────────

    async def _reflect(
        self,
        query: str,
        initial_answer: str,
        messages: List[Dict[str, Any]],
        claude: anthropic.AsyncAnthropic,
    ) -> str:
        """
        Reflexion — ask Claude to self-critique and optionally improve its answer.
        """
        critique_prompt = (
            f"Review your previous answer to: '{query}'\n\n"
            f"Previous answer:\n{initial_answer}\n\n"
            "Check for gaps, inaccuracies, or missing citations. "
            "If the answer is already complete and accurate, reply with exactly: ANSWER_OK\n"
            "Otherwise provide an improved version."
        )
        try:
            resp = await claude.messages.create(
                model=settings.CLAUDE_MODEL,
                max_tokens=settings.CLAUDE_MAX_TOKENS,
                system=self.system_prompt,
                messages=messages + [{"role": "user", "content": critique_prompt}],
            )
            text = "".join(b.text for b in resp.content if b.type == "text").strip()
            if text == "ANSWER_OK":
                logger.info(f"[{self.name}] Reflection: no changes needed")
                return initial_answer
            logger.info(f"[{self.name}] Reflection: answer improved")
            return text
        except Exception as e:
            logger.warning(f"[{self.name}] Reflection failed: {e}")
            return initial_answer


# ── Helpers ────────────────────────────────────────────────────────────────────

def _deduplicate_sources(sources: List[Dict[str, str]]) -> List[Dict[str, str]]:
    seen: set = set()
    result = []
    for s in sources:
        url = s.get("url", "")
        if url and url not in seen:
            seen.add(url)
            result.append(s)
    return result
