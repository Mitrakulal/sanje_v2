"""Load the four tools once, at startup.

Three are local LangChain tools. The weather tool comes from a tiny stdio MCP
server so the network handling stays in one place.
"""

from __future__ import annotations

import sys

from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient

from config import ROOT
from tools.budget import calculate_budget
from tools.food import find_famous_food
from tools.search import web_search

LOCAL_TOOLS: list[BaseTool] = [web_search, find_famous_food, calculate_budget]


def connections() -> dict:
    return {
        "weather": {
            "transport": "stdio",
            "command": sys.executable,
            "args": ["-m", "weather_mcp"],
            "cwd": str(ROOT),
        }
    }


async def load_tools() -> list[BaseTool]:
    """Return local tools plus whatever the weather MCP server exposes."""
    tools: list[BaseTool] = list(LOCAL_TOOLS)

    try:
        client = MultiServerMCPClient(connections())
        weather_tools = list(await client.get_tools())
        tools.extend(weather_tools)
        names = ", ".join(tool.name for tool in tools)
        print(f"[tools] loaded: {names}")
    except Exception as exc:  # noqa: BLE001
        print(f"[tools] weather MCP unavailable ({type(exc).__name__}: {exc})")
        print("[tools] continuing with local tools only")

    return tools
