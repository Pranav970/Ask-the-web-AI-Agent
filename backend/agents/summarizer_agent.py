"""
agents/summarizer_agent.py — Condenses research into a clean summary.
FIX: Uses settings.get_anthropic_key() for safe key access.
"""
from __future__ import annotations

import anthropic

from agents.base_agent import BaseAgent
from config import get_settings

settings = get_settings()


class SummarizerAgent(BaseAgent):
    """
    Takes raw research output and produces a concise, well-structured summary.
    """

    def __init__(self):
        super().__init__(name="SummarizerAgent")

    @property
    def system_prompt(self) -> str:
        return """\
You are an expert summarizer. Your job:
1. Distil long, complex research into clear, concise prose
2. Preserve ALL important facts and citations
3. Structure: Brief summary → Key points → Sources
4. Use plain language — accessible to a general audience
5. Never add information not present in the input"""

    async def summarize(self, research_text: str, query: str) -> str:
        """Summarize research_text in the context of the original query."""
        claude = anthropic.AsyncAnthropic(api_key=settings.get_anthropic_key())
        response = await claude.messages.create(
            model=settings.CLAUDE_MODEL,
            max_tokens=1500,
            system=self.system_prompt,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Original question: {query}\n\n"
                        f"Research to summarize:\n{research_text}"
                    ),
                }
            ],
        )
        return "".join(b.text for b in response.content if b.type == "text")
