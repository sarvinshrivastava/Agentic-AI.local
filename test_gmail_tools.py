"""
Test to check Gmail tools are properly registered.
"""
import asyncio
from mcp_orchestrator_pro import MCPOrchestratorPro

async def test_gmail_tools():
    async with MCPOrchestratorPro() as orchestrator:
        tools = await orchestrator.get_all_tool_specs()
        
        gmail_tools = [tool for tool in tools if tool['server'] == 'gmail']
        
        print(f"🔧 Gmail Tools Available ({len(gmail_tools)}):")
        for tool in gmail_tools:
            print(f"  • {tool['name']}: {tool['description']}")

if __name__ == "__main__":
    asyncio.run(test_gmail_tools())