#!/usr/bin/env python3
"""
Test script to verify MCP server connections work properly with error handling
"""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from mcp_orchestrator_pro import MCPOrchestratorPro

async def test_connections():
    """Test MCP server connections with enhanced error handling"""
    print("🔧 Testing MCP Server Connections...")
    print("=" * 50)
    
    async with MCPOrchestratorPro() as orchestrator:
        # Health check
        print("\n📊 Running Health Check...")
        health = await orchestrator.health_check()
        
        print(f"Calendar MCP: {'✅ Connected' if health['calendar'] else '❌ Failed'}")
        print(f"Notion MCP:   {'✅ Connected' if health['notion'] else '❌ Failed'}")  
        print(f"Gmail MCP:    {'✅ Connected' if health['gmail'] else '❌ Failed'}")
        
        # Test available tools
        print(f"\n🛠️  Available Tools:")
        try:
            tools = await orchestrator.get_all_tool_specs()
            for tool in tools[:5]:  # Show first 5 tools
                print(f"  • {tool['name']} ({tool['server']})")
            if len(tools) > 5:
                print(f"  ... and {len(tools) - 5} more tools")
        except Exception as e:
            print(f"Error getting tools: {e}")
        
        print(f"\n🎯 Connection Summary:")
        connected_servers = [name for name, status in health.items() if status]
        failed_servers = [name for name, status in health.items() if not status]
        
        print(f"✅ Connected: {', '.join(connected_servers) if connected_servers else 'None'}")
        print(f"❌ Failed: {', '.join(failed_servers) if failed_servers else 'None'}")
        
        if connected_servers:
            print(f"\n✨ System ready with {len(connected_servers)}/3 services available!")
            return True
        else:
            print(f"\n⚠️  No services available - check server configurations")
            return False

if __name__ == "__main__":
    try:
        result = asyncio.run(test_connections())
        sys.exit(0 if result else 1)
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)