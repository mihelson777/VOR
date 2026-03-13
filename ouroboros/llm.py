"""
LLM client — Groq / OpenRouter / OpenAI.

Contract: chat(), default_model().
Приоритет: GROQ (бесплатно) → OpenRouter → OpenAI.
"""

import os
import time
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
# Модель без Groq (когда openrouter/free даёт 429)
# stepfun — быстрая; qwen — лучше с tools (send_message и т.д.)
OPENROUTER_NO_GROQ_MODEL = "qwen/qwen3-next-80b-a3b-instruct"


def _force_openrouter() -> bool:
    """Skip Groq when PREFER_OPENROUTER=1 (e.g. Groq rate limit 429)."""
    return (os.environ.get("PREFER_OPENROUTER") or "").strip() in ("1", "true", "yes")


def _get_api_key() -> str:
    if _force_openrouter():
        return (os.environ.get("OPENROUTER_API_KEY") or "").strip()
    return (
        (os.environ.get("GROQ_API_KEY") or "").strip()
        or (os.environ.get("OPENROUTER_API_KEY") or "").strip()
        or (os.environ.get("OPENAI_API_KEY") or "").strip()
        or ""
    )


def _get_base_url() -> str:
    if _force_openrouter():
        return "https://openrouter.ai/api/v1"
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
        if _force_openrouter():
            return "openrouter"
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

        last_err = None
        for attempt in range(3):
            try:
                resp = client.chat.completions.create(**kwargs)
                resp_dict = resp.model_dump()
                usage = resp_dict.get("usage") or {}
                choices = resp_dict.get("choices") or [{}]
                msg = (choices[0] if choices else {}).get("message") or {}
                return msg, usage
            except Exception as e:
                err_str = str(e)
                err_body = getattr(e, "body", None) or getattr(e, "response", None)
                if isinstance(err_body, str):
                    try:
                        import json
                        err_body = json.loads(err_body)
                    except Exception:
                        err_body = {}
                err = (err_body or {}).get("error", {}) if isinstance(err_body, dict) else {}
                code = err.get("code", "")

                # tool_use_failed: retry same provider
                if code == "tool_use_failed" or "tool_use_failed" in err_str:
                    last_err = e
                    if attempt < 2:
                        time.sleep(0.5 * (attempt + 1))
                        continue
                    raise

                # rate_limit_exceeded (429): fallback to OpenRouter
                is_rate_limit = code == "rate_limit_exceeded" or "rate_limit" in err_str.lower() or "429" in err_str
                if is_rate_limit:
                    or_key = (os.environ.get("OPENROUTER_API_KEY") or "").strip()
                    if or_key:
                        from openai import OpenAI
                        fallback = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=or_key)
                        use_model = (os.environ.get("OUROBOROS_MODEL") or "").strip() or OPENROUTER_FREE_MODEL
                        try:
                            resp = fallback.chat.completions.create(**{**kwargs, "model": use_model})
                            resp_dict = resp.model_dump()
                            return (resp_dict.get("choices") or [{}])[0].get("message") or {}, resp_dict.get("usage") or {}
                        except Exception as fallback_err:
                            pass  # fallback failed, re-raise original
                raise
        if last_err:
            raise last_err

    def default_model(self) -> str:
        explicit = (os.environ.get("OUROBOROS_MODEL") or "").strip()
        if explicit:
            return explicit
        if _force_openrouter():
            return OPENROUTER_NO_GROQ_MODEL  # stepfun — без Groq, чтобы избежать 429
        if (os.environ.get("GROQ_API_KEY") or "").strip():
            return GROQ_FREE_MODEL
        if (os.environ.get("OPENROUTER_API_KEY") or "").strip():
            return OPENROUTER_FREE_MODEL
        return "gpt-4o-mini"  # OpenAI fallback
