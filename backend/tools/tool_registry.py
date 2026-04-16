"""
tools/tool_registry.py — Central tool registry and async execution engine.

Every tool is a Python async callable wrapped with:
  • A JSON Schema definition (for Claude's tools= parameter)
  • An async executor
  • Comprehensive error handling

Claude picks which tool(s) to call; this module executes them and formats
responses as Anthropic tool_result blocks.
"""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine, Dict, List, Optional

from utils.logger import logger


@dataclass
class ToolDefinition:
    """Mirrors Anthropic's tool schema format exactly."""
    name:         str
    description:  str
    input_schema: Dict[str, Any]
    executor:     Callable[..., Coroutine]
    tags:         List[str] = field(default_factory=list)

    def to_anthropic_format(self) -> Dict[str, Any]:
        """Return the dict Claude expects in the `tools=` parameter."""
        return {
            "name":         self.name,
            "description":  self.description,
            "input_schema": self.input_schema,
        }


class ToolRegistry:
    """Holds all registered tools and executes them by name."""

    def __init__(self):
        self._tools: Dict[str, ToolDefinition] = {}

    def register(self, tool: ToolDefinition) -> None:
        self._tools[tool.name] = tool
        logger.info(f"[ToolRegistry] Registered: {tool.name}")

    def get(self, name: str) -> Optional[ToolDefinition]:
        return self._tools.get(name)

    def all_definitions(self) -> List[Dict[str, Any]]:
        """List passed directly to Anthropic client as tools=."""
        return [t.to_anthropic_format() for t in self._tools.values()]

    def list_names(self) -> List[str]:
        return list(self._tools.keys())

    async def execute(
        self,
        tool_name: str,
        tool_input: Dict[str, Any],
        tool_use_id: str,
    ) -> Dict[str, Any]:
        """
        Execute one tool and return an Anthropic tool_result block.
        Catches ALL exceptions so the agent loop never crashes on tool failure.
        """
        tool = self.get(tool_name)
        if not tool:
            msg = f"Unknown tool: '{tool_name}'. Available: {self.list_names()}"
            logger.warning(f"[ToolRegistry] {msg}")
            return {"type": "tool_result", "tool_use_id": tool_use_id,
                    "is_error": True, "content": msg}

        try:
            logger.info(f"[ToolRegistry] Executing '{tool_name}' | input={json.dumps(tool_input)[:120]}")
            result = await tool.executor(**tool_input)
            content = json.dumps(result) if not isinstance(result, str) else result
            logger.info(f"[ToolRegistry] '{tool_name}' completed ({len(content)} chars)")
            return {"type": "tool_result", "tool_use_id": tool_use_id, "content": content}
        except TypeError as e:
            # Wrong kwargs — likely schema mismatch
            msg = f"Tool '{tool_name}' called with wrong arguments: {e}"
            logger.error(f"[ToolRegistry] {msg}")
            return {"type": "tool_result", "tool_use_id": tool_use_id,
                    "is_error": True, "content": msg}
        except Exception as e:
            msg = f"Tool '{tool_name}' raised {type(e).__name__}: {e}"
            logger.error(f"[ToolRegistry] {msg}")
            return {"type": "tool_result", "tool_use_id": tool_use_id,
                    "is_error": True, "content": msg}

    async def execute_parallel(
        self,
        calls: List[Dict[str, Any]],  # [{name, input, id}, ...]
    ) -> List[Dict[str, Any]]:
        """Execute multiple tool calls concurrently and return all results."""
        if not calls:
            return []
        tasks = [self.execute(c["name"], c["input"], c["id"]) for c in calls]
        return list(await asyncio.gather(*tasks))


# Global singleton — all tool modules import and register against this
registry = ToolRegistry()
