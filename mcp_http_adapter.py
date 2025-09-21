"""
MCP HTTP Adapter for fastmcp compatibility.
Bridges the gap between fastmcp's expected transport and MCP server HTTP implementations.
"""

import asyncio
import json
import uuid
from typing import Any, Dict, List, Optional
import aiohttp
from fastmcp.transports.base import BaseClientTransport


class HTTPMCPTransport(BaseClientTransport):
    """
    HTTP transport adapter for MCP servers that use StreamableHTTP or SSE.
    Compatible with fastmcp's Client interface.
    """
    
    def __init__(self, base_url: str, session_id: Optional[str] = None):
        self.base_url = base_url.rstrip('/')
        self.session_id = session_id or str(uuid.uuid4())
        self.session = None
        self._request_id = 0
    
    async def connect(self):
        """Establish HTTP session"""
        if not self.session:
            self.session = aiohttp.ClientSession()
    
    async def disconnect(self):
        """Close HTTP session"""
        if self.session:
            await self.session.close()
            self.session = None
    
    def _next_request_id(self) -> int:
        """Generate next request ID"""
        self._request_id += 1
        return self._request_id
    
    async def send_request(self, method: str, params: Any = None) -> Any:
        """
        Send MCP request over HTTP.
        Adapts fastmcp's request format to work with HTTP MCP servers.
        """
        if not self.session:
            await self.connect()
        
        # Build JSON-RPC 2.0 request
        request = {
            "jsonrpc": "2.0",
            "id": self._next_request_id(),
            "method": method
        }
        
        if params is not None:
            request["params"] = params
        
        # Send POST request to /mcp endpoint
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream, */*",
            "mcp-session-id": self.session_id
        }
        
        try:
            async with self.session.post(
                f"{self.base_url}",
                json=request,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                
                # Handle different response types
                content_type = response.headers.get('content-type', '')
                
                if 'application/json' in content_type:
                    # Standard JSON-RPC response
                    data = await response.json()
                    if 'error' in data:
                        raise Exception(f"MCP Error: {data['error']}")
                    return data.get('result')
                
                elif 'text/event-stream' in content_type:
                    # Server-Sent Events - read the stream
                    text = await response.text()
                    # Parse SSE format
                    lines = text.strip().split('\n')
                    for line in lines:
                        if line.startswith('data: '):
                            try:
                                data = json.loads(line[6:])  # Remove 'data: ' prefix
                                if 'error' in data:
                                    raise Exception(f"MCP Error: {data['error']}")
                                return data.get('result')
                            except json.JSONDecodeError:
                                continue
                    
                    # If no valid JSON found, return text
                    return text
                
                else:
                    # Plain text or other format
                    return await response.text()
                    
        except aiohttp.ClientError as e:
            raise Exception(f"HTTP transport error: {e}")
    
    async def list_tools(self) -> List[Dict[str, Any]]:
        """List available tools from MCP server"""
        result = await self.send_request("tools/list")
        return result.get("tools", []) if result else []
    
    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Any:
        """Call a tool on the MCP server"""
        params = {
            "name": name,
            "arguments": arguments
        }
        return await self.send_request("tools/call", params)


async def test_http_transport():
    """Test the HTTP transport adapter"""
    
    # Test Calendar MCP
    print("🔧 Testing Calendar MCP HTTP Transport...")
    calendar_transport = HTTPMCPTransport("http://localhost:3000/mcp")
    
    try:
        await calendar_transport.connect()
        tools = await calendar_transport.list_tools()
        print(f"✅ Calendar MCP: Found {len(tools)} tools")
        
        # Test a simple tool call
        if tools:
            tool_names = [tool.get('name', 'unknown') for tool in tools[:3]]
            print(f"   Sample tools: {', '.join(tool_names)}")
        
    except Exception as e:
        print(f"❌ Calendar MCP failed: {e}")
    finally:
        await calendar_transport.disconnect()
    
    print()
    
    # Test Gmail MCP  
    print("🔧 Testing Gmail MCP HTTP Transport...")
    gmail_transport = HTTPMCPTransport("http://localhost:3001/mcp")
    
    try:
        await gmail_transport.connect()
        tools = await gmail_transport.list_tools()
        print(f"✅ Gmail MCP: Found {len(tools)} tools")
        
        # Test a simple tool call
        if tools:
            tool_names = [tool.get('name', 'unknown') for tool in tools[:3]]
            print(f"   Sample tools: {', '.join(tool_names)}")
        
    except Exception as e:
        print(f"❌ Gmail MCP failed: {e}")
    finally:
        await gmail_transport.disconnect()


if __name__ == "__main__":
    asyncio.run(test_http_transport())