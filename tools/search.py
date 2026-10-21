"""Tavily web search.

One plain HTTP call instead of another SDK. If the key is missing the tool
returns an error object; the agent is told to say what it could not check.
"""

from __future__ import annotations

from typing import Any

import httpx
from langchain_core.tools import tool

from config import SETTINGS

TAVILY_URL = "https://api.tavily.com/search"
TIMEOUT = 25.0


def tavily_search(
    query: str,
    *,
    max_results: int = 5,
    include_answer: bool = False,
) -> dict[str, Any]:
    """Run one Tavily query and return a small, model-friendly payload."""
    if not SETTINGS.tavily_api_key:
        return {
            "error": "TAVILY_API_KEY is missing, so live web search is unavailable.",
            "query": query,
            "results": [],
        }

    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            response = client.post(
                TAVILY_URL,
                json={
                    "api_key": SETTINGS.tavily_api_key,
                    "query": query,
                    "search_depth": "basic",
                    "max_results": max(1, min(10, int(max_results))),
                    "include_answer": include_answer,
                    "include_raw_content": False,
                },
            )
            response.raise_for_status()
            payload = response.json()
    except Exception as exc:  # noqa: BLE001
        return {
            "error": f"web search failed: {type(exc).__name__}: {exc}",
            "query": query,
            "results": [],
        }

    results = []
    for row in payload.get("results") or []:
        results.append(
            {
                "title": row.get("title", ""),
                "url": row.get("url", ""),
                "content": (row.get("content") or "")[:400],
            }
        )

    return {
        "query": query,
        "answer": payload.get("answer"),
        "results": results,
    }


@tool
def web_search(query: str, max_results: int = 5) -> dict:
    """Search the live web for places, events, opening hours or local details.

    Args:
        query: A specific search query, e.g. "things to do in Mangalore on a Sunday".
        max_results: Number of results to return, from 1 to 10.
    """
    return tavily_search(query, max_results=max_results)
