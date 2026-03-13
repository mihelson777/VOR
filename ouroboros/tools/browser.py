"""Browser tools: fetch_url, extract_links — fetch and parse web pages."""

import json
from typing import Any

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
from bs4 import BeautifulSoup

from ouroboros.tools.registry import ToolContext, ToolEntry

MAX_TEXT_LEN = 8000
DEFAULT_TIMEOUT = 15


def _fetch_url(ctx: ToolContext, url: str, timeout: int = DEFAULT_TIMEOUT) -> str:
    """Fetch URL, return title + text (up to 8000 chars)."""
    try:
        resp = requests.get(url, timeout=timeout, verify=False)
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding or "utf-8"
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style"]):
            tag.decompose()
        title = soup.title.string if soup.title else ""
        text = soup.get_text(separator="\n", strip=True)
        if len(text) > MAX_TEXT_LEN:
            text = text[:MAX_TEXT_LEN] + "\n...(truncated)"
        return json.dumps({"title": title, "text": text, "url": url}, ensure_ascii=False, indent=2)
    except requests.RequestException as e:
        return json.dumps({"error": str(e)})
    except Exception as e:
        return json.dumps({"error": str(e)})


def _extract_links(ctx: ToolContext, url: str, timeout: int = DEFAULT_TIMEOUT) -> str:
    """Extract all links from page. Returns [{text, href}, ...]."""
    try:
        resp = requests.get(url, timeout=timeout, verify=False)
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding or "utf-8"
        soup = BeautifulSoup(resp.text, "html.parser")
        links = []
        for a in soup.find_all("a", href=True):
            href = a.get("href", "").strip()
            if href and href.startswith(("http://", "https://")):
                text = a.get_text(strip=True)[:200]
                links.append({"text": text, "href": href})
        return json.dumps(links[:100], ensure_ascii=False, indent=2)
    except requests.RequestException as e:
        return json.dumps({"error": str(e)})
    except Exception as e:
        return json.dumps({"error": str(e)})


def get_tools() -> list:
    return [
        ToolEntry("fetch_url", {
            "name": "fetch_url",
            "description": "Fetch a web page. Returns title and text (up to 8000 chars).",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL to fetch"},
                    "timeout": {"type": "integer", "description": "Timeout in seconds", "default": 15},
                },
                "required": ["url"],
            },
        }, _fetch_url),
        ToolEntry("extract_links", {
            "name": "extract_links",
            "description": "Extract all links from a web page. Returns [{text, href}, ...].",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL to fetch"},
                    "timeout": {"type": "integer", "description": "Timeout in seconds", "default": 15},
                },
                "required": ["url"],
            },
        }, _extract_links),
    ]
