"""
Simple Math MCP Server (FastMCP, Streamable HTTP)

Run:
  python math_server.py

MCP endpoint:
  http://127.0.0.1:6281/mcp/
"""

from __future__ import annotations

from typing import Dict, Any, List

from fastmcp import FastMCP


mcp = FastMCP("math-server")


@mcp.tool
async def add(a: float, b: float) -> float:
    """
    Return a + b.
    """
    return a + b


@mcp.tool
async def multiply(a: float, b: float) -> float:
    """
    Return a * b.
    """
    return a * b


@mcp.tool
async def stats(numbers: List[float]) -> Dict[str, Any]:
    """
    Return basic stats for a list of numbers: count, sum, mean.
    """
    n = len(numbers)
    s = sum(numbers)
    mean = (s / n) if n else 0.0
    return {"count": n, "sum": s, "mean": mean}


if __name__ == "__main__":
    # Serve via HTTP
    mcp.run(transport="http", host="127.0.0.1", port=6281)


