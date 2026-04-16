"""
mcp/mcp_client.py — Model Context Protocol (MCP) client.

MCP standardises how AI models communicate with external tool servers.
Architecture:
  MCP Host (Claude Desktop / our app)
    └── MCP Client (this file)
          ├── MCP Server A (web search)
          ├── MCP Server B (database)
          └── MCP Server C (GitHub API)

Each MCP server exposes:
  • tools/list      — discover available tools
  • tools/call      — execute a tool
  • resources/list  — list data resources (files, DB tables, etc.)
  • prompts/list    — server-defined prompt templates

This client implements a simplified JSON-RPC over HTTP/SSE transport,
compatible with the MCP specification (https://modelcontextprotocol.io).
"""
from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any, Dict, List, Optional

import httpx

from utils.logger import logger


class MCPError(Exception):
    """Raised when an MCP server returns an error response."""
    pass


class MCPClient:
    """
    Lightweight async MCP client.

    Usage:
        client = MCPClient("http://localhost:3001")
        tools  = await client.list_tools()
        result = await client.call_tool("web_search", {"query": "AI news"})
    """

    def __init__(
        self,
        server_url: str,
        server_name: str = "unnamed",
        timeout: float = 30.0,
    ):
        self.server_url  = server_url.rstrip("/")
        self.server_name = server_name
        self.timeout     = timeout
        self._session_id = str(uuid.uuid4())
        self._http       = httpx.AsyncClient(timeout=self.timeout)
        self._tools_cache: Optional[List[Dict[str, Any]]] = None

    async def initialize(self) -> Dict[str, Any]:
        """
        Send MCP initialize request to negotiate protocol version
        and discover server capabilities.
        """
        response = await self._request(
            method="initialize",
            params={
                "protocolVersion": "2024-11-05",
                "capabilities": {"roots": {}, "sampling": {}},
                "clientInfo": {
                    "name": "ask-the-web-agent",
                    "version": "1.0.0",
                },
            },
        )
        logger.info(
            f"[MCP:{self.server_name}] Initialized. "
            f"Server: {response.get('serverInfo', {})}"
        )
        return response

    async def list_tools(self, use_cache: bool = True) -> List[Dict[str, Any]]:
        """Return list of tools exposed by this MCP server."""
        if use_cache and self._tools_cache is not None:
            return self._tools_cache

        response = await self._request(method="tools/list")
        tools = response.get("tools", [])
        self._tools_cache = tools
        logger.info(f"[MCP:{self.server_name}] {len(tools)} tools available")
        return tools

    async def call_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
    ) -> Any:
        """Execute a tool on the MCP server and return its result."""
        logger.info(f"[MCP:{self.server_name}] Calling tool: {tool_name}")
        response = await self._request(
            method="tools/call",
            params={"name": tool_name, "arguments": arguments},
        )
        return response.get("content", response)

    async def list_resources(self) -> List[Dict[str, Any]]:
        """Discover data resources (files, DB tables, etc.) on the server."""
        response = await self._request(method="resources/list")
        return response.get("resources", [])

    async def read_resource(self, uri: str) -> Any:
        """Read a specific resource by URI."""
        response = await self._request(
            method="resources/read",
            params={"uri": uri},
        )
        return response.get("contents", [])

    async def close(self) -> None:
        await self._http.aclose()

    # ── JSON-RPC transport ──────────────────────────────────────────────

    async def _request(
        self,
        method: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Send a JSON-RPC 2.0 request to the MCP server."""
        payload = {
            "jsonrpc": "2.0",
            "id":     str(uuid.uuid4()),
            "method": method,
        }
        if params:
            payload["params"] = params

        try:
            resp = await self._http.post(
                f"{self.server_url}/mcp",
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPError as e:
            raise MCPError(f"[MCP:{self.server_name}] HTTP error: {e}") from e

        if "error" in data:
            err = data["error"]
            raise MCPError(
                f"[MCP:{self.server_name}] Error {err.get('code')}: {err.get('message')}"
            )

        return data.get("result", {})


# ── MCP Server registry ───────────────────────────────────────────────────

class MCPServerRegistry:
    """Manages a pool of connected MCP servers."""

    def __init__(self):
        self._servers: Dict[str, MCPClient] = {}

    def register(self, name: str, client: MCPClient) -> None:
        self._servers[name] = client
        logger.info(f"[MCPRegistry] Registered server: {name} @ {client.server_url}")

    def get(self, name: str) -> Optional[MCPClient]:
        return self._servers.get(name)

    async def initialize_all(self) -> None:
        """Initialize all registered servers (discover capabilities)."""
        tasks = [
            client.initialize() for client in self._servers.values()
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for name, result in zip(self._servers.keys(), results):
            if isinstance(result, Exception):
                logger.warning(f"[MCPRegistry] Failed to init '{name}': {result}")

    async def all_tools(self) -> Dict[str, List[Dict[str, Any]]]:
        """Aggregate tool lists from all servers."""
        result = {}
        for name, client in self._servers.items():
            try:
                result[name] = await client.list_tools()
            except Exception as e:
                logger.warning(f"[MCPRegistry] list_tools failed for '{name}': {e}")
        return result

    async def close_all(self) -> None:
        for client in self._servers.values():
            await client.close()


# ── Global MCP registry ───────────────────────────────────────────────────

mcp_registry = MCPServerRegistry()

# Example: wire up servers at startup (add real URLs in .env)
# from config import get_settings
# settings = get_settings()
# mcp_registry.register(
#     "search",
#     MCPClient(settings.MCP_SEARCH_URL or "http://localhost:3001", "search")
# )
