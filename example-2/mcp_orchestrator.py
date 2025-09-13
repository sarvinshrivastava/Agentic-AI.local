# pip install fastmcp
import json
import asyncio
from contextlib import AsyncExitStack
from typing import Any, Dict, List, Optional, Tuple

from fastmcp import Client as MCPClient


def to_plain_json_schema(schema_obj: Any) -> Dict[str, Any]:
    """Best-effort conversion to a plain JSON Schema dict (model-agnostic)."""
    if isinstance(schema_obj, dict):
        return schema_obj
    if hasattr(schema_obj, "model_dump"):
        return schema_obj.model_dump()
    if hasattr(schema_obj, "dict"):
        return schema_obj.dict()
    # Final fallback: attempt a JSON round-trip to strip unknown types
    return json.loads(json.dumps(schema_obj, default=lambda o: getattr(o, "__dict__", {})))


class MCPOrchestrator:
    """
    Model-agnostic orchestrator: manages connections to multiple MCP servers,
    exposes tool discovery and tool execution. No LLM bindings here.
    """

    def __init__(self, servers: Dict[str, str]):
        """
        servers: mapping like {"weather": "http://127.0.0.1:6280/mcp/", ...}
        """
        self._servers = servers
        self._clients: Dict[str, MCPClient] = {}
        self._stack: Optional[AsyncExitStack] = None

    async def __aenter__(self) -> "MCPOrchestrator":
        self._stack = AsyncExitStack()
        # Open all connections
        for name, url in self._servers.items():
            c = MCPClient(url)
            await self._stack.enter_async_context(c)
            self._clients[name] = c
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self._stack:
            await self._stack.aclose()
        self._clients.clear()
        self._stack = None

    # ----------------- Discovery -----------------

    async def list_tools(self, server: str) -> List[Any]:
        """Return raw tool objects from a single server."""
        return await self._clients[server].list_tools()

    async def list_all_tools(self) -> Dict[str, List[Any]]:
        """Return mapping server -> list of raw tool objects."""
        out: Dict[str, List[Any]] = {}
        for name, c in self._clients.items():
            out[name] = await c.list_tools()
        return out

    async def get_all_tool_specs(self, namespaced: bool = True) -> List[Dict[str, Any]]:
        """
        Return a normalized, model-agnostic view of all tools with optional namespacing.

        Each item:
        {
          "server": "weather",
          "name": "weather__get_weather" (if namespaced) or "get_weather",
          "bare_name": "get_weather",
          "description": "...",
          "inputSchema": {...}  # plain JSON Schema
        }
        """
        specs: List[Dict[str, Any]] = []
        for server, c in self._clients.items():
            tools = await c.list_tools()
            #resources = await c.list_resources()
            #print(resources)
            for t in tools:
                desc = getattr(t, "description", "") or getattr(t, "title", "")
                inputSchema = to_plain_json_schema(getattr(t, "inputSchema", {}) or {})
                bare_name = t.name
                full_name = f"{server}__{bare_name}" if namespaced else bare_name
                specs.append({
                    "server": server,
                    "name": full_name,
                    "bare_name": bare_name,
                    "description": desc,
                    "inputSchema": inputSchema,
                })
        return specs

    # ----------------- Execution -----------------

    async def call_tool(self, server: str, tool_name: str, args: Dict[str, Any]) -> Any:
        """Execute a tool on a specific server."""
        return await self._clients[server].call_tool(tool_name, args or {})

    async def call_tool_by_fullname(self, fullname: str, args: Dict[str, Any]) -> Tuple[str, Any]:
        """
        Execute a tool by namespaced name "server__tool". Returns (server, result).
        Raises ValueError if the name is not namespaced.
        """
        if "__" not in fullname:
            raise ValueError("Expected namespaced tool name like 'weather__get_weather'")
        server, bare = fullname.split("__", 1)
        res = await self.call_tool(server, bare, args)
        return server, res
