#!/usr/bin/env python3
"""
Notion MCP Server Smoke Test
Tests basic connectivity and tool execution with Notion MCP server.
"""

import asyncio
import json
from fastmcp import Client as MCPClient
from fastmcp.client.auth import OAuth

NOTION_URL = "https://mcp.notion.com/mcp"          # hosted by Notion



async def main():
    async with MCPClient(NOTION_URL, auth=OAuth(NOTION_URL)) as notion:
        notion_tools = await notion.list_tools()
        print(f"📊 Total tools available: {len(notion_tools)}")
        print("🔍 Notion MCP Server - First 10 Tools")
        print("=" * 60)
        
        for i, tool in enumerate(notion_tools[:10], 1):
            print(f"\n{i}. 🛠️  {tool.name}")
            print("-" * 40)
            
            # Description
            description = getattr(tool, 'description', 'No description available')
            print(f"📝 Description: {description}")
            
            # Input Schema
            input_schema = getattr(tool, 'inputSchema', {})
            if input_schema:
                print(f"📋 Input Schema:")
                try:
                    schema_str = json.dumps(input_schema, indent=2)
                    # Truncate if too long
                    if len(schema_str) > 300:
                        schema_str = schema_str[:300] + "..."
                    print(f"   {schema_str}")
                except Exception as e:
                    print(f"   Error formatting schema: {e}")
            else:
                print(f"📋 Input Schema: No schema available")
            
            # Output Schema
            output_schema = getattr(tool, 'outputSchema', None)
            if output_schema:
                print(f"📤 Output Schema:")
                try:
                    output_str = json.dumps(output_schema, indent=2)
                    if len(output_str) > 200:
                        output_str = output_str[:200] + "..."
                    print(f"   {output_str}")
                except Exception as e:
                    print(f"   Error formatting output schema: {e}")
            else:
                print(f"📤 Output Schema: No output schema")
            
            print()
        
        print("=" * 60)
        print(f"📊 Total tools available: {len(notion_tools)}")
        print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())
