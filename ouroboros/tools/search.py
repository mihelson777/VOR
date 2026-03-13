"""Web search via DuckDuckGo (no API key required)."""

import json
from typing import Any

from ouroboros.tools.registry import ToolContext, ToolEntry


def _web_search(ctx: ToolContext, query: str, max_results: int = 5) -> str:
    """Search DuckDuckGo and return structured results as JSON string."""
    max_results = min(int(max_results), 20)
    try:
        try:
            from ddgs import DDGS
        except ImportError:
            from duckduckgo_search import DDGS

        with DDGS() as ddgs:
            raw = list(ddgs.text(query, max_results=max_results))

        results = [
            {
                "title": r.get("title", ""),
                "url": r.get("href", ""),
                "snippet": r.get("body", ""),
            }
            for r in raw
        ]
        if not results:
            return json.dumps([{"error": "No results found"}], ensure_ascii=False, indent=2)
        return json.dumps(results, ensure_ascii=False, indent=2)
    except ImportError:
        return json.dumps([{"error": "duckduckgo-search not installed. pip install duckduckgo-search"}])
    except Exception as exc:
        return json.dumps([{"error": f"web_search failed: {exc}"}])


def get_tools() -> list:
    return [
        ToolEntry("web_search", {
            "name": "web_search",
            "description": (
                "Search the web using DuckDuckGo. Returns title, URL and snippet for each result. "
                "Use for current info, news, documentation. No API key required."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "max_results": {"type": "integer", "description": "Max results (default 5, max 20)", "default": 5},
                },
                "required": ["query"],
            },
        }, _web_search),
    ]
