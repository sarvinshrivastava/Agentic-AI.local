"""
Test different MCP method calls to understand the Gmail server's protocol.
"""

import asyncio
import json
import aiohttp


async def test_mcp_methods():
    """Test various MCP methods on Gmail server"""
    
    base_url = "http://localhost:3001/mcp"
    
    async with aiohttp.ClientSession() as session:
        
        # Test 1: Standard MCP initialization
        print("🔧 Test 1: MCP Initialization")
        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "roots": {
                        "listChanged": True
                    },
                    "sampling": {}
                },
                "clientInfo": {
                    "name": "test-client",
                    "version": "1.0.0"
                }
            }
        }
        
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream, */*"
        }
        
        try:
            async with session.post(base_url, json=init_request, headers=headers) as response:
                print(f"   Status: {response.status}")
                content_type = response.headers.get('content-type', '')
                print(f"   Content-Type: {content_type}")
                
                if 'application/json' in content_type:
                    data = await response.json()
                    print(f"   Response: {json.dumps(data, indent=2)}")
                else:
                    text = await response.text()
                    print(f"   Raw response: {text[:200]}...")
                    
        except Exception as e:
            print(f"   Error: {e}")
        
        print("\n" + "="*60 + "\n")
        
        # Test 2: List tools after initialization
        print("🔧 Test 2: List Tools")
        list_request = {
            "jsonrpc": "2.0", 
            "id": 2,
            "method": "tools/list"
        }
        
        try:
            async with session.post(base_url, json=list_request, headers=headers) as response:
                print(f"   Status: {response.status}")
                content_type = response.headers.get('content-type', '')
                print(f"   Content-Type: {content_type}")
                
                if 'application/json' in content_type:
                    data = await response.json()
                    print(f"   Response: {json.dumps(data, indent=2)}")
                else:
                    text = await response.text()
                    print(f"   Raw response: {text[:200]}...")
                    
        except Exception as e:
            print(f"   Error: {e}")
        
        print("\n" + "="*60 + "\n")
        
        # Test 3: Direct SSE connection
        print("🔧 Test 3: SSE Connection Test")
        sse_headers = {
            "Accept": "text/event-stream",
            "Cache-Control": "no-cache"
        }
        
        try:
            async with session.get(base_url, headers=sse_headers) as response:
                print(f"   Status: {response.status}")
                print(f"   Headers: {dict(response.headers)}")
                
                # Read some SSE data
                content = await response.text()
                print(f"   SSE Content: {content[:300]}...")
                
        except Exception as e:
            print(f"   Error: {e}")


if __name__ == "__main__":
    asyncio.run(test_mcp_methods())