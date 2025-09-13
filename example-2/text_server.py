"""
Simple Text MCP Server (FastMCP, Streamable HTTP)

Run:
  python text_server.py

MCP endpoint:
  http://127.0.0.1:6282/mcp/
"""

from __future__ import annotations

from typing import Dict, Any

from fastmcp import FastMCP


mcp = FastMCP("text-server")


@mcp.tool
async def word_count(text: str) -> Dict[str, Any]:
    """
    Count words and characters.
    """
    words = text.split()
    return {"words": len(words), "chars": len(text)}


@mcp.tool
async def reverse(text: str) -> str:
    """
    Reverse a string.
    """
    return text[::-1]


@mcp.tool
async def to_upper(text: str) -> str:
    """
    Convert to uppercase.
    """
    return text.upper()


if __name__ == "__main__":
    # Serve via HTTP
    mcp.run(transport="http", host="127.0.0.1", port=6282)


