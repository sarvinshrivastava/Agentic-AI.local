"""
One-shot OpenAI chat that dynamically fetches tools from the MCP server and executes them.

Run the server first in another terminal:
  uvicorn weather_server:app --port 6280 --host 127.0.0.1

Usage:
  python open_ai_chat.py "What's the weather in Paris?"
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from typing import Any

from dotenv import load_dotenv
from fastmcp import Client
from openai import OpenAI


def _build_openai_tools_schema(tools: list[Any]) -> list[dict[str, Any]]:
    schemas: list[dict[str, Any]] = []
    for t in tools:
        name = getattr(t, "name", None) or "tool"
        description = getattr(t, "description", None) or getattr(t, "title", "") or ""
        params = getattr(t, "inputSchema", None) or {"type": "object", "properties": {}}
        schemas.append(
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": description,
                    "parameters": params,
                },
            }
        )
    return schemas


def _tool_result_to_text(result: Any) -> str:
    """Convert fastmcp CallToolResult to a plain string for OpenAI tool message."""
    try:
        # Prefer structured content if available
        sc = getattr(result, "structured_content", None) or getattr(result, "structuredContent", None)
        if sc is not None:
            return json.dumps(sc)

        # Otherwise, join any text blocks in content
        content = getattr(result, "content", None)
        if isinstance(content, (list, tuple)):
            texts: list[str] = []
            for block in content:
                if isinstance(block, dict):
                    if block.get("type") == "text":
                        texts.append(block.get("text", ""))
                else:
                    # fastmcp TextContent dataclass
                    t = getattr(block, "text", None)
                    if isinstance(t, str):
                        texts.append(t)
            if texts:
                return "\n".join(texts)

        # Fallback to string repr
        return str(result)
    except Exception:
        return str(result)

async def main() -> None:
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY missing in environment/.env")

    # MCP server URL (streamable-http app mounted at /mcp on port 6280)
    server_url = os.getenv("MCP_SERVER_URL", "http://127.0.0.1:6280/mcp")

    # User prompt
    user_text = "what is sum of 9 and 6"
    if len(sys.argv) > 1:
        user_text = " ".join(sys.argv[1:])

    # Connect to MCP server and fetch tools
    async with Client(server_url) as mcp_client:
        tools = await mcp_client.list_tools()
        openai_tools = _build_openai_tools_schema(tools)
        print(openai_tools)
        # Prepare OpenAI request
        client = OpenAI(api_key=api_key)
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": user_text},
        ]

        # Single OpenAI call that may produce tool calls
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            tools=openai_tools,
            tool_choice="auto",
            temperature=0.2,
        )

        choice = response.choices[0]
        msg = choice.message
        if msg.content:
            print("Assistant:", msg.content)

        # Execute any tool calls returned (no second OpenAI call here by design)
        if getattr(msg, "tool_calls", None):
            messages.append({
                        "role": "assistant",
                        "content": msg.content or "",
                        "tool_calls": msg.tool_calls
                    })
            for tc in msg.tool_calls:
                if tc.type == "function":
                    name = tc.function.name
                    arguments = tc.function.arguments or "{}"
                    try:
                        args = json.loads(arguments)
                    except Exception:
                        args = {}
                    print(f"\n[Executing tool] {name}({args})")
                    result = await mcp_client.call_tool(name, args)
                    print("Tool result:", result)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": _tool_result_to_text(result),
                    })

            # Final OpenAI call after all tool responses are appended
            final = client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                temperature=0.2,
            )
            print("\nFinal:", final.choices[0].message.content)


if __name__ == "__main__":
    asyncio.run(main())


