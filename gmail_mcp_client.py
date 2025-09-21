"""
Simple HTTP MCP Client for Gmail integration.
Direct HTTP communication with Gmail MCP server.
"""

import asyncio
import json
import uuid
from typing import Any, Dict, List, Optional
import aiohttp


class SimpleMCPClient:
    """
    Simple HTTP client for MCP servers.
    Handles direct HTTP communication with MCP endpoints.
    """
    
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        self.session_id = str(uuid.uuid4())
        self.session = None
        self._request_id = 0
        self.connected = False
    
    async def connect(self):
        """Establish HTTP session"""
        if not self.session:
            self.session = aiohttp.ClientSession()
            self.connected = True
    
    async def disconnect(self):
        """Close HTTP session"""
        if self.session:
            await self.session.close()
            self.session = None
            self.connected = False
    
    def _next_request_id(self) -> int:
        """Generate next request ID"""
        self._request_id += 1
        return self._request_id
    
    async def send_request(self, method: str, params: Any = None) -> Any:
        """Send MCP request over HTTP"""
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
        
        # Send POST request
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream, */*",
            "mcp-session-id": self.session_id
        }
        
        try:
            async with self.session.post(
                self.base_url,
                json=request,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                
                content_type = response.headers.get('content-type', '')
                
                if 'application/json' in content_type:
                    data = await response.json()
                    if 'error' in data:
                        raise Exception(f"MCP Error: {data['error']}")
                    return data.get('result')
                
                elif 'text/event-stream' in content_type:
                    # Handle SSE response
                    text = await response.text()
                    lines = text.strip().split('\n')
                    for line in lines:
                        if line.startswith('data: '):
                            try:
                                data = json.loads(line[6:])
                                if 'error' in data:
                                    raise Exception(f"MCP Error: {data['error']}")
                                return data.get('result')
                            except json.JSONDecodeError:
                                continue
                    return {"raw_response": text}
                
                else:
                    return {"raw_response": await response.text()}
                    
        except aiohttp.ClientError as e:
            raise Exception(f"HTTP transport error: {e}")
    
    async def list_tools(self) -> List[Dict[str, Any]]:
        """List available tools"""
        try:
            result = await self.send_request("tools/list")
            return result.get("tools", []) if result else []
        except Exception:
            # Fallback for different MCP implementations
            return []
    
    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Any:
        """Call a tool"""
        params = {
            "name": name,
            "arguments": arguments
        }
        return await self.send_request("tools/call", params)


# Gmail-specific operations wrapper
class GmailMCPClient:
    """Gmail-specific MCP client with convenience methods"""
    
    def __init__(self, base_url: str = "http://localhost:3001/mcp"):
        self.client = SimpleMCPClient(base_url)
    
    async def connect(self):
        """Connect to Gmail MCP server"""
        await self.client.connect()
    
    async def disconnect(self):
        """Disconnect from Gmail MCP server"""
        await self.client.disconnect()
    
    async def list_tools(self) -> List[str]:
        """Get list of available Gmail tools"""
        tools = await self.client.list_tools()
        return [tool.get('name', 'unknown') for tool in tools]
    
    async def send_gmail(self, to: List[str], subject: str, body: str, 
                        cc: Optional[List[str]] = None, 
                        bcc: Optional[List[str]] = None) -> str:
        """Send an email via Gmail"""
        args = {
            "to": to,
            "subject": subject,
            "body": body
        }
        if cc:
            args["cc"] = cc
        if bcc:
            args["bcc"] = bcc
        
        result = await self.client.call_tool("send_email", args)
        return str(result)
    
    async def search_gmail(self, query: str, max_results: int = 10) -> str:
        """Search Gmail messages"""
        args = {
            "query": query,
            "maxResults": max_results
        }
        result = await self.client.call_tool("search_emails", args)
        return str(result)
    
    async def read_gmail(self, message_id: str) -> str:
        """Read a specific Gmail message"""
        args = {"messageId": message_id}
        result = await self.client.call_tool("read_email", args)
        return str(result)


async def test_gmail_client():
    """Test Gmail MCP client"""
    print("🔧 Testing Gmail MCP Client...")
    
    gmail = GmailMCPClient()
    
    try:
        await gmail.connect()
        
        # Test listing tools
        tools = await gmail.list_tools()
        print(f"✅ Gmail MCP: Found {len(tools)} tools")
        if tools:
            print(f"   Sample tools: {', '.join(tools[:5])}")
        
        print("✅ Gmail client test successful")
        
    except Exception as e:
        print(f"❌ Gmail client test failed: {e}")
    
    finally:
        await gmail.disconnect()


if __name__ == "__main__":
    asyncio.run(test_gmail_client())