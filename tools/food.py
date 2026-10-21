"""Famous local food lookup, backed by Tavily."""

from __future__ import annotations

from langchain_core.tools import tool

from tools.search import tavily_search


@tool
def find_famous_food(location: str, limit: int = 6) -> dict:
    """Find famous local dishes and good places to try them.

    Use this once the location is known. It returns a short summary plus
    sources; do not invent dishes or restaurant names beyond what it gives you.

    Args:
        location: City or area, e.g. "Mangalore" or "Udupi".
        limit: Number of sources to return, from 1 to 10.
    """
    query = (
        f"famous local food dishes to try in {location} "
        "and the best places to eat them"
    )
    result = tavily_search(query, max_results=limit, include_answer=True)
    if result.get("error"):
        return result

    summary = result.get("answer")
    if not summary:
        snippets = [row["content"] for row in result.get("results", []) if row.get("content")]
        summary = " ".join(snippets[:3])

    return {
        "location": location,
        "summary": (summary or "")[:700],
        "sources": result.get("results", [])[:5],
    }
