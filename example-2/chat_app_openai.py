# chat_app_openai.py
# pip install openai python-dotenv fastmcp
# Run the FastMCP server first, then:
#   python chat_app_openai.py
import os
import json
import asyncio
from typing import Any, Dict, List

from dotenv import load_dotenv
from openai import OpenAI

from mcp_orchestrator import MCPOrchestrator, to_plain_json_schema

load_dotenv()

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
SERVERS = {
    # IMPORTANT: include /mcp/ for FastMCP HTTP transport
    "math": os.getenv("MATH_MCP_URL", "http://127.0.0.1:6281/mcp/"),
    "text": os.getenv("TEXT_MCP_URL", "http://127.0.0.1:6282/mcp/"),
    # add more servers here later...
}


def specs_to_openai_tools(specs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Convert generic MCP tool specs (model-agnostic) into OpenAI Chat Completions
    tools format. Keeps namespacing in tool.name to disambiguate duplicates.
    """
    tools: List[Dict[str, Any]] = []
    for s in specs:
        tools.append({
            "type": "function",
            "function": {
                "name": s["name"],  # e.g., "weather__get_weather"
                "description": s.get("description", ""),
                "parameters": s.get("inputSchema") or {"type": "object", "properties": {}},
            },
        })
    return tools


def _tool_result_to_text(result: Any) -> str:
    """Best-effort conversion of an MCP tool result to plain string for OpenAI messages."""
    try:
        sc = getattr(result, "structured_content", None) or getattr(result, "structuredContent", None)
        if sc is not None:
            return json.dumps(sc)

        content = getattr(result, "content", None)
        if isinstance(content, (list, tuple)):
            texts: List[str] = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    texts.append(block.get("text", ""))
                else:
                    t = getattr(block, "text", None)
                    if isinstance(t, str):
                        texts.append(t)
            if texts:
                return "\n".join(texts)

        return str(result)
    except Exception:
        return str(result)

async def run_chat(question: str) -> None:
    """
    One chat turn: discover tools dynamically (no hard-coded schemas),
    let the OpenAI model decide tool calls, execute via MCP orchestrator,
    and return a final natural-language answer.
    """
    oa = OpenAI()  # uses OPENAI_API_KEY
    # aenter_ is called when the with block is entered
    # aexit_ is called when the with block is exited
    async with MCPOrchestrator(SERVERS) as mcp:
        # 1) Discover tools at runtime (MCP)
        tool_specs = await mcp.get_all_tool_specs(namespaced=True)
        openai_tools = specs_to_openai_tools(tool_specs)
        # 2) System instruction guiding when to call which tool
        sys = (
            "You can call tools via function calling. "
            "For weather questions, use the weather tools. "
            "If multiple cities are requested, call the weather tool for each city. "
            "Prefer metric (Celsius). After using tools, summarize succinctly."
        )

        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": sys},
            {"role": "user", "content": question},
        ]

        # 3) Tool-call loop (multi-hop if needed)
        for _ in range(6):
            resp = oa.chat.completions.create(
                model=OPENAI_MODEL,
                messages=messages,
                tools=openai_tools,
                tool_choice="auto",
                temperature=0,
            )
            msg = resp.choices[0].message

            # The model may decide to call tools
            if getattr(msg, "tool_calls", None):
                # Add assistant's tool_calls message to chat history
                messages.append({"role": "assistant", "content": msg.content or "", "tool_calls": msg.tool_calls})

                # Execute each tool call
                tool_results: List[Dict[str, Any]] = []
                for tc in msg.tool_calls:
                    tool_fullname = tc.function.name  # e.g., "weather__get_weather"
                    try:
                        args = json.loads(tc.function.arguments or "{}")
                    except Exception:
                        args = {}

                    # If you ever accept non-namespaced names, resolve to a server here
                    if "__" not in tool_fullname:
                        # (not expected; we told specs_to_openai_tools to namespace)
                        # You could attempt to match by bare_name from tool_specs.
                        raise ValueError(f"Tool name not namespaced: {tool_fullname}")

                    # Execute via orchestrator
                    _, res = await mcp.call_tool_by_fullname(tool_fullname, args)
                    print("called tool", tool_fullname, "with args", args, "and got result", res)
                    # Feed the tool result back to the model (converted to text)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "name": tool_fullname,
                        "content": _tool_result_to_text(res),
                    })
                    tool_results.append({"tool": tool_fullname, "args": args, "result": res})
                # Loop again so the model can incorporate tool outputs
                continue

            # No tool calls -> final answer
            print("\nAssistant:\n" + (msg.content or "").strip())
            break
        else:
            print("\nAssistant:\n(Sorry, hit tool-call loop limit.)")


if __name__ == "__main__":
    # Example: should trigger two tool calls automatically
    question = "Tell me the stats of 1, 2, 3, 4, 5"
    asyncio.run(run_chat(question))
