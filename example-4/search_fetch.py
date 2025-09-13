# pip install fastmcp
import os
import re
import json
import asyncio
from fastmcp import Client
from fastmcp.client.auth import OAuth

NOTION_MCP_URL = "https://mcp.notion.com/mcp"  # <-- set this

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

async def main():
    client = Client(NOTION_MCP_URL, auth=OAuth(NOTION_MCP_URL))

    async with client:
        # 1) Search your workspace for the page
        query = "Meeting Plan"
        search_res = await client.call_tool("search", {
            "query": query,
            "query_type": "internal"
        })
        search_data = tool_result_to_text(search_res)
        print("Search (raw):", json.dumps(search_data, indent=2)[:600], "...\n")



if __name__ == "__main__":
    asyncio.run(main())
