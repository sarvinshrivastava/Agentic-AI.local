# Run after the server is up
# Connects to the HTTP MCP server and invokes the tool.

import asyncio
from fastmcp import Client

async def main():
    client = Client("http://127.0.0.1:6280/mcp")
    async with client:
        # List available tools
        tools = await client.list_tools()
        print(tools)
        #for t in tools:
            # t has .name, .title, .description, .input_schema, .output_schema
            #print(f"- {t.name}: {getattr(t, 'description', '') or getattr(t, 'title', '')}")

        # Call the tool exposed by the server
        result = await client.call_tool(
            "get_weather",
            {"city": "Bengaluru", "units": "metric", "lang": "en"},
        )
        print(result)
        print("--------------------------------")
        #result = await client.call_tool(
        #    "get_sum",
        #    {"a": 1, "b": 2},
        #)
        #print(result)

if __name__ == "__main__":
    asyncio.run(main())
