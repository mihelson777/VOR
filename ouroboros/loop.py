"""
LLM tool loop — send messages, execute tools, repeat until final response.
"""

import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from ouroboros.llm import LLMClient
from ouroboros.tools.registry import ToolRegistry
from ouroboros.utils import utc_now_iso, append_jsonl


def run_loop(
    messages: List[Dict[str, Any]],
    tools: ToolRegistry,
    logs_dir: Path,
    max_rounds: int = 50,
    emit_progress: Optional[Callable[[str], None]] = None,
) -> tuple[str, List[Dict[str, Any]]]:
    """
    Run LLM loop until final text response or max_rounds.
    Returns (final_text, full_messages).
    """
    llm = LLMClient()
    tool_schemas = tools.schemas()

    for round_idx in range(max_rounds):
        # LLM call
        msg, usage = llm.chat(
            messages=messages,
            tools=tool_schemas,
            max_tokens=8192,
        )

        content = msg.get("content") or ""
        tool_calls = msg.get("tool_calls") or []

        if content and not tool_calls:
            # Final response
            return content.strip(), messages

        if tool_calls:
            messages.append(msg)
            for tc in tool_calls:
                fn_name = tc.get("function", {}).get("name", "")
                try:
                    args = json.loads(tc.get("function", {}).get("arguments", "{}"))
                except json.JSONDecodeError:
                    args = {}
                result = tools.execute(fn_name, args)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.get("id", ""),
                    "content": str(result)[:15000],
                })
                append_jsonl(logs_dir / "tools.jsonl", {
                    "ts": utc_now_iso(), "tool": fn_name, "result_preview": str(result)[:500],
                })
                if emit_progress:
                    try:
                        emit_progress(fn_name, str(result)[:200])
                    except TypeError:
                        emit_progress(f"Tool: {fn_name}")
        else:
            return content.strip() or "(no response)", messages

    return "(max rounds reached)", messages
