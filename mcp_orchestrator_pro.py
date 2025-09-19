#!/usr/bin/env python3
"""
MCPOrchestratorPro - Enhanced orchestrator for Calendar Assistant Pro
Manages Google Calendar and Notion MCP servers with OAuth support.
"""

import json
import asyncio
from contextlib import AsyncExitStack
from typing import Any, Dict, List, Optional, Tuple

from fastmcp import Client as MCPClient
from fastmcp.client.auth import OAuth


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


def tool_result_to_text(result):
    """Convert fastmcp CallToolResult to a plain string for JSON serialization."""
    try:
        sc = getattr(result, "structured_content", None) or getattr(result, "structuredContent", None)
        if sc is not None:
            return sc
        content = getattr(result, "content", None)
        if isinstance(content, (list, tuple)):
            texts = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    texts.append(block.get("text", ""))
                else:  # fastmcp TextContent dataclass
                    t = getattr(block, "text", None)
                    if isinstance(t, str):
                        texts.append(t)
            if texts:
                return "\n".join(texts)
        return str(result)
    except Exception:
        return str(result)


class MCPOrchestratorPro:
    """
    Enhanced orchestrator for Calendar Assistant Pro.
    Manages Google Calendar (local) and Notion (remote with OAuth) MCP servers.
    """

    def __init__(self, 
                 calendar_url: str = "http://localhost:3000/mcp",
                 notion_url: str = "https://mcp.notion.com/mcp"):
        """
        Initialize with hardcoded server URLs.
        - calendar_url: Local Google Calendar MCP server
        - notion_url: Remote Notion MCP server (requires OAuth)
        """
        self.calendar_url = calendar_url
        self.notion_url = notion_url
        self._clients: Dict[str, MCPClient] = {}
        self._stack: Optional[AsyncExitStack] = None

    async def __aenter__(self) -> "MCPOrchestratorPro":
        self._stack = AsyncExitStack()
        
        # Connect to Google Calendar (no auth needed)
        calendar_client = MCPClient(self.calendar_url)
        await self._stack.enter_async_context(calendar_client)
        self._clients["calendar"] = calendar_client
        
        # Connect to Notion (with OAuth)
        notion_client = MCPClient(self.notion_url, auth=OAuth(self.notion_url))
        await self._stack.enter_async_context(notion_client)
        self._clients["notion"] = notion_client
        
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self._stack:
            await self._stack.aclose()
        self._clients.clear()
        self._stack = None

    # ----------------- Discovery -----------------

    async def list_tools(self, server: str) -> List[Any]:
        """Return raw tool objects from a specific server (calendar or notion)."""
        if server not in self._clients:
            raise ValueError(f"Unknown server: {server}. Available: {list(self._clients.keys())}")
        return await self._clients[server].list_tools()

    async def list_all_tools(self) -> Dict[str, List[Any]]:
        """Return mapping server -> list of raw tool objects."""
        out: Dict[str, List[Any]] = {}
        for name, c in self._clients.items():
            out[name] = await c.list_tools()
        return out

    async def get_all_tool_specs(self, namespaced: bool = True) -> List[Dict[str, Any]]:
        """
        Return a normalized, model-agnostic view of all tools with namespacing.
        
        Each item:
        {
          "server": "calendar",
          "name": "calendar__list-events" (if namespaced) or "list-events",
          "bare_name": "list-events",
          "description": "...",
          "inputSchema": {...}  # plain JSON Schema
        }
        """
        specs: List[Dict[str, Any]] = []
        for server, c in self._clients.items():
            tools = await c.list_tools()
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
        if server not in self._clients:
            raise ValueError(f"Unknown server: {server}. Available: {list(self._clients.keys())}")
        return await self._clients[server].call_tool(tool_name, args or {})

    async def call_tool_by_fullname(self, fullname: str, args: Dict[str, Any]) -> Tuple[str, Any]:
        """
        Execute a tool by namespaced name "server__tool". Returns (server, result).
        Raises ValueError if the name is not namespaced.
        """
        if "__" not in fullname:
            raise ValueError("Expected namespaced tool name like 'calendar__list-events'")
        server, bare = fullname.split("__", 1)
        res = await self.call_tool(server, bare, args)
        return server, res

    # ----------------- Convenience Methods -----------------

    async def search_notion_documents(self, query: str, query_type: str = "internal") -> List[Dict[str, Any]]:
        """Search Notion workspace for documents matching the query."""
        try:
            result = await self.call_tool("notion", "search", {
                "query": query,
                "query_type": query_type
            })
            search_data = tool_result_to_text(result)
            
            if isinstance(search_data, dict) and "results" in search_data:
                return search_data["results"]
            return []
        except Exception as e:
            print(f"Error searching Notion: {e}")
            return []

    async def fetch_notion_document(self, document_id: str) -> Optional[str]:
        """Fetch the full content of a Notion document by ID."""
        try:
            result = await self.call_tool("notion", "fetch", {"id": document_id})
            fetch_data = tool_result_to_text(result)
            
            if isinstance(fetch_data, dict):
                content = fetch_data.get("content") or fetch_data.get("markdown") or fetch_data.get("page_content")
                return content
            return None
        except Exception as e:
            print(f"Error fetching Notion document: {e}")
            return None

    async def list_calendar_events(self, time_min: str, time_max: str, calendar_id: str = "primary") -> List[Dict[str, Any]]:
        """List calendar events for a specific time range."""
        try:
            result = await self.call_tool("calendar", "list-events", {
                "calendarId": calendar_id,
                "timeMin": time_min,
                "timeMax": time_max
            })
            return tool_result_to_text(result)
        except Exception as e:
            print(f"Error listing calendar events: {e}")
            return []

    async def create_calendar_event(self, calendar_id: str, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new calendar event."""
        try:
            result = await self.call_tool("calendar", "create-event", {
                "calendarId": calendar_id,
                **event_data
            })
            return tool_result_to_text(result)
        except Exception as e:
            print(f"Error creating calendar event: {e}")
            return {}

    # ----------------- Health Check -----------------

    async def health_check(self) -> Dict[str, bool]:
        """Check if both servers are accessible."""
        health = {}
        
        # Check calendar
        try:
            await self.list_tools("calendar")
            health["calendar"] = True
        except Exception:
            health["calendar"] = False
            
        # Check notion
        try:
            await self.list_tools("notion")
            health["notion"] = True
        except Exception:
            health["notion"] = False
            
        return health
