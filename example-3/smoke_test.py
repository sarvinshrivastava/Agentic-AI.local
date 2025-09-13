# pip install fastmcp
import asyncio
import json
import re
from datetime import datetime, timedelta
from fastmcp import Client

async def main():
    async with Client("http://localhost:3000/mcp") as mcp:
        tools = await mcp.list_tools()
        # Pretty-print each tool's name, description, input/output schemas
        print("Available tools (schema):")
        for t in tools:
            try:
                inp = json.dumps(getattr(t, "inputSchema", {}) or {}, indent=2)
            except Exception:
                inp = str(getattr(t, "inputSchema=", {}))
            try:
                outp = json.dumps(getattr(t, "outputSchema", None), indent=2)
            except Exception:
                outp = str(getattr(t, "outputSchema", None))
            print(f"- {t.name}\n  desc: {getattr(t, 'description', '')}\n  input: {inp}\n  output: {outp}\n")


        # Build time range: now to 3 days ahead in 'YYYY-MM-DDTHH:MM:SS'
        now = datetime.utcnow()
        time_min = now.strftime("%Y-%m-%dT%H:%M:%S")
        time_max = (now + timedelta(days=3)).strftime("%Y-%m-%dT%H:%M:%S")

        # Call list-events on the chosen calendar
        evt_res = await mcp.call_tool(
            "list-events",
            {"calendarId": "vivek176iitv@gmail.com", "timeMin": time_min, "timeMax": time_max, "maxResults": 10},
        )
        print(evt_res)
        print("--------------------------------")
        

asyncio.run(main())
