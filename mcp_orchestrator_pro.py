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
                 notion_url: str = "https://mcp.notion.com/mcp",
                 gmail_url: str = "http://localhost:3001/mcp"):
        """
        Initialize with hardcoded server URLs.
        - calendar_url: Local Google Calendar MCP server
        - notion_url: Remote Notion MCP server (requires OAuth)
        - gmail_url: Local Gmail MCP server
        """
        self.calendar_url = calendar_url
        self.notion_url = notion_url
        self.gmail_url = gmail_url
        self._clients: Dict[str, MCPClient] = {}
        self._gmail_http_client = None
        self._stack: Optional[AsyncExitStack] = None

    async def __aenter__(self) -> "MCPOrchestratorPro":
        self._stack = AsyncExitStack()
        
        # Connect to Google Calendar (with error handling)
        try:
            calendar_client = MCPClient(self.calendar_url)
            await self._stack.enter_async_context(calendar_client)
            self._clients["calendar"] = calendar_client
            print(f"✅ Connected to Google Calendar MCP server at {self.calendar_url}")
        except Exception as e:
            print(f"⚠️  Failed to connect to Google Calendar MCP server: {e}")
        
        # Connect to Notion (with OAuth and error handling)
        try:
            notion_client = MCPClient(self.notion_url, auth=OAuth(self.notion_url))
            await self._stack.enter_async_context(notion_client)
            self._clients["notion"] = notion_client
            print(f"✅ Connected to Notion MCP server at {self.notion_url}")
        except Exception as e:
            print(f"⚠️  Failed to connect to Notion MCP server: {e}")
        
        # Connect to Gmail using custom HTTP client
        try:
            from gmail_mcp_client import GmailMCPClient
            
            self.gmail_client = GmailMCPClient()
            await self.gmail_client.connect()
            
            # Store as a special client type
            self._gmail_http_client = self.gmail_client
            print(f"✅ Connected to Gmail MCP server via HTTP client")
        except Exception as e:
            print(f"⚠️  Failed to connect to Gmail MCP server: {e}")
            self._gmail_http_client = None
        
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self._stack:
            await self._stack.aclose()
        
        # Clean up Gmail HTTP client if it exists
        if self._gmail_http_client:
            try:
                await self._gmail_http_client.disconnect()
            except Exception:
                pass
        
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
        
        # Add Gmail tools if available
        if self._gmail_http_client:
            gmail_tools = [
                {
                    "name": "send_email",
                    "description": "Send an email via Gmail",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "to": {"type": "array", "items": {"type": "string"}, "description": "List of recipient email addresses"},
                            "subject": {"type": "string", "description": "Email subject"},
                            "body": {"type": "string", "description": "Email body content"},
                            "cc": {"type": "array", "items": {"type": "string"}, "description": "List of CC recipients"},
                            "bcc": {"type": "array", "items": {"type": "string"}, "description": "List of BCC recipients"}
                        },
                        "required": ["to", "subject", "body"]
                    }
                },
                {
                    "name": "search_emails",
                    "description": "Search Gmail messages using Gmail search syntax",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Gmail search query (e.g., 'from:example@gmail.com', 'is:unread newer_than:7d')"},
                            "maxResults": {"type": "integer", "description": "Maximum number of results to return", "default": 10}
                        },
                        "required": ["query"]
                    }
                },
                {
                    "name": "read_email",
                    "description": "Read the content of a specific Gmail message",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "messageId": {"type": "string", "description": "ID of the email message to retrieve"}
                        },
                        "required": ["messageId"]
                    }
                }
            ]
            
            for tool in gmail_tools:
                full_name = f"gmail__{tool['name']}" if namespaced else tool['name']
                specs.append({
                    "server": "gmail",
                    "name": full_name,
                    "bare_name": tool['name'],
                    "description": tool['description'],
                    "inputSchema": tool['inputSchema'],
                })
        
        return specs

    # ----------------- Execution -----------------

    async def call_tool(self, server: str, tool_name: str, args: Dict[str, Any]) -> Any:
        """Execute a tool on a specific server."""
        if server == "gmail" and self._gmail_http_client:
            # Handle Gmail tools directly
            if tool_name == "send_email":
                return await self._gmail_http_client.send_gmail(
                    args.get("to", []),
                    args.get("subject", ""),
                    args.get("body", ""),
                    cc=args.get("cc"),
                    bcc=args.get("bcc")
                )
            elif tool_name == "search_emails":
                try:
                    return await self._gmail_http_client.search_gmail(
                        args.get("query", ""),
                        args.get("maxResults", 10)
                    )
                except Exception as e:
                    if "timeout" in str(e).lower() or "cancelled" in str(e).lower():
                        return "Gmail authentication required. Please run OAuth authentication first."
                    raise e
            elif tool_name == "read_email":
                return await self._gmail_http_client.read_gmail(args.get("messageId", ""))
            else:
                raise ValueError(f"Unknown Gmail tool: {tool_name}")
        elif server in self._clients:
            return await self._clients[server].call_tool(tool_name, args or {})
        else:
            available_servers = list(self._clients.keys())
            if self._gmail_http_client:
                available_servers.append("gmail")
            raise ValueError(f"Unknown server: {server}. Available: {available_servers}")

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

    # ----------------- Gmail Operations -----------------

    async def send_gmail(self, to: List[str], subject: str, body: str, **kwargs) -> Dict[str, Any]:
        """Send an email via Gmail."""
        try:
            if self._gmail_http_client:
                result = await self._gmail_http_client.send_gmail(to, subject, body, **kwargs)
                return {"content": result, "success": True}
            else:
                return {"error": "Gmail client not available", "success": False}
        except Exception as e:
            print(f"Error sending email: {e}")
            return {"error": str(e), "success": False}

    async def search_gmail(self, query: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """Search Gmail messages."""
        try:
            if self._gmail_http_client:
                result = await self._gmail_http_client.search_gmail(query, max_results)
                return result
            else:
                return {"error": "Gmail client not available"}
        except Exception as e:
            print(f"Error searching emails: {e}")
            return {"error": str(e)}

    async def read_gmail(self, message_id: str) -> str:
        """Read a specific Gmail message."""
        try:
            if self._gmail_http_client:
                result = await self._gmail_http_client.read_gmail(message_id)
                return result
            else:
                return "Gmail client not available"
        except Exception as e:
            print(f"Error reading email: {e}")
            return f"Error: {str(e)}"

    async def list_gmail_labels(self) -> Dict[str, Any]:
        """List all Gmail labels."""
        try:
            if self._gmail_http_client:
                # Add list_labels method to Gmail client if needed
                tools = await self._gmail_http_client.list_tools()
                return {"labels": tools}
            else:
                return {"error": "Gmail client not available"}
        except Exception as e:
            print(f"Error listing Gmail labels: {e}")
            return {"error": str(e)}

    # ----------------- Health Check -----------------

    async def health_check(self) -> Dict[str, bool]:
        """Check if all servers are accessible."""
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
            
        # Check gmail
        health["gmail"] = self._gmail_http_client is not None
            
        return health
