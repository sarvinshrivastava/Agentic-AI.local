# Run: python weather_server_fastmcp.py
# The MCP endpoint will be http://127.0.0.1:6280/mcp/

from typing import Literal, Dict, Any
from fastmcp import FastMCP
import httpx

mcp = FastMCP("weather-server")

@mcp.tool
async def get_sum(a: int, b: int) -> int:
    """
    Get the sum of two numbers.
    """
    return a + b

@mcp.tool
async def get_vivek_info() -> Dict[str, Any]:
    """
    Return simple personal information about Vivek.

    This tool takes no input and returns a dictionary with
    name, address, and nationality.
    """
    # Returns personal info of Vivek
    return {
        "name": "Vivek",
        "address": "sector 62, Noida",
        "nationality": "Indian",
    }

@mcp.tool
async def get_weather(
    city: str,
    units: Literal["metric", "imperial"] = "metric",
    lang: str = "en",
) -> Dict[str, Any]:
    """
    Fetch current weather from wttr.in.
    Returns temperature, humidity, wind, description, and feels-like.
    """
    # wttr.in JSON; 'm' flag => metric units, imperial is default
    flags = "m" if units == "metric" else ""
    url = f"https://wttr.in/{city}?format=j1&{flags}&lang={lang}"

    try:
        async with httpx.AsyncClient(timeout=6.0) as client:
            r = await client.get(url)
            r.raise_for_status()
            data = r.json()

        cur = (data.get("current_condition") or [{}])[0]
        # description field varies by language key; fall back to english
        desc = ""
        if cur.get(f"lang_{lang}"):
            desc = cur[f"lang_{lang}"][0].get("value", "")
        elif cur.get("weatherDesc"):
            desc = cur["weatherDesc"][0].get("value", "")

        return {
            "ok": True,
            "weather": {
                "city": city,
                "desc": desc,
                "temp_c": cur.get("temp_C"),
                "temp_f": cur.get("temp_F"),
                "feels_like_c": cur.get("FeelsLikeC"),
                "feels_like_f": cur.get("FeelsLikeF"),
                "humidity_pct": cur.get("humidity"),
                "wind_kmph": cur.get("windspeedKmph"),
                "wind_mph": cur.get("windspeedMiles"),
                "observation_time_utc": cur.get("observation_time"),
                "units": units,
            },
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}



if __name__ == "__main__":
    # Serve via Streamable HTTP so any MCP client can connect
    mcp.run(transport="http", host="127.0.0.1", port=6280)
