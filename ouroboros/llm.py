"""
LLM client — Groq / OpenRouter / OpenAI.

Contract: chat(), default_model().
Приоритет: GROQ (бесплатно) → OpenRouter → OpenAI.
"""

import os
from typing import Any, Dict, List, Optional, Tuple

# Ensure .env is loaded before reading keys
from pathlib import Path
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

# Бесплатные модели по провайдеру
GROQ_FREE_MODEL = "llama-3.3-70b-versatile"
OPENROUTER_FREE_MODEL = "openrouter/free"


def _get_api_key() -> str:
    return (
        (os.environ.get("GROQ_API_KEY") or "").strip()
        or (os.environ.get("OPENROUTER_API_KEY") or "").strip()
        or (os.environ.get("OPENAI_API_KEY") or "").strip()
        or ""
    )


def _get_base_url() -> str:
    if (os.environ.get("GROQ_API_KEY") or "").strip():
        return "https://api.groq.com/openai/v1"
    if (os.environ.get("OPENROUTER_API_KEY") or "").strip():
        return "https://openrouter.ai/api/v1"
    return "https://api.openai.com/v1"


class LLMClient:
    """OpenRouter or OpenAI API wrapper."""

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        self._api_key = (api_key or _get_api_key()).strip()
        self._base_url = base_url or _get_base_url()
        self._client = None

    @property
    def provider(self) -> str:
        """Current provider for debugging."""
        if (os.environ.get("GROQ_API_KEY") or "").strip():
            return "groq"
        if (os.environ.get("OPENROUTER_API_KEY") or "").strip():
            return "openrouter"
        if (os.environ.get("OPENAI_API_KEY") or "").strip():
            return "openai"
        return "none"

    @property
    def model(self) -> str:
        return self.default_model()

    def _get_client(self):
        if self._client is None:
            if not self._api_key:
                raise ValueError(
                    "No API key. Add to .env: GROQ_API_KEY=gsk_xxx (https://console.groq.com/keys) "
                    "or OPENROUTER_API_KEY or OPENAI_API_KEY"
                )
            from openai import OpenAI
            self._client = OpenAI(
                base_url=self._base_url,
                api_key=self._api_key,
            )
        return self._client

    def _sanitize_messages(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Strip unsupported fields for Groq/OpenRouter. Remove None in tool_calls."""
        out = []
        for m in messages:
            role = m.get("role", "")
            if role == "assistant":
                clean = {"role": "assistant"}
                if m.get("content"):
                    clean["content"] = m["content"]
                else:
                    clean["content"] = None
                if m.get("tool_calls"):
                    tcs = []
                    for tc in m["tool_calls"]:
                        if not isinstance(tc, dict):
                            continue
                        fn = tc.get("function", {})
                        tcs.append({
                            "id": tc.get("id", ""),
                            "type": "function",
                            "function": {
                                "name": fn.get("name", ""),
                                "arguments": fn.get("arguments", "{}"),
                            }
                        })
                    if tcs:
                        clean["tool_calls"] = tcs
            elif role == "tool":
                clean = {
                    "role": "tool",
                    "tool_call_id": m.get("tool_call_id", ""),
                    "content": str(m.get("content", "")),
                }
            elif role in ("user", "system"):
                clean = {
                    "role": role,
                    "content": m.get("content", ""),
                }
            else:
                continue
            out.append(clean)
        return out

    def chat(
        self,
        messages: List[Dict[str, Any]],
        model: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        max_tokens: int = 8192,
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Single LLM call. Returns (response_message, usage_dict)."""
        client = self._get_client()
        model = model or self.default_model()
        messages = self._sanitize_messages(messages)

        kwargs: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        resp = client.chat.completions.create(**kwargs)
        resp_dict = resp.model_dump()
        usage = resp_dict.get("usage") or {}
        choices = resp_dict.get("choices") or [{}]
        msg = (choices[0] if choices else {}).get("message") or {}

        return msg, usage

    def default_model(self) -> str:
        explicit = (os.environ.get("OUROBOROS_MODEL") or "").strip()
        if explicit:
            return explicit
        if (os.environ.get("GROQ_API_KEY") or "").strip():
            return GROQ_FREE_MODEL
        if (os.environ.get("OPENROUTER_API_KEY") or "").strip():
            return OPENROUTER_FREE_MODEL
        return "gpt-4o-mini"  # OpenAI fallback
