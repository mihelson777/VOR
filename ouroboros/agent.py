"""
Agent — thin orchestrator.
Delegates to loop, tools, memory, context.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

from ouroboros.context import build_messages
from ouroboros.loop import run_loop
from ouroboros.memory import Memory
from ouroboros.tools.registry import ToolContext, ToolRegistry
from ouroboros.utils import utc_now_iso, append_jsonl


class Agent:
    """One agent instance. Stateless; state lives in data/."""

    def __init__(self, repo_dir: Path, data_root: Path):
        self.repo_dir = repo_dir
        self.data_root = data_root
        self.logs_dir = data_root / "logs"
        self.logs_dir.mkdir(parents=True, exist_ok=True)

        self.tools = ToolRegistry(repo_dir=repo_dir, data_root=data_root)
        self.memory = Memory(data_root=data_root)

    def run(self, user_message: str, emit_progress: Optional[Any] = None) -> str:
        """Process user message, return response. emit_progress(tool_name, result_preview) for web UI."""
        pending_events: List[Dict[str, Any]] = []

        def _emit(name: str, msg: str = "") -> None:
            if emit_progress:
                try:
                    emit_progress(name, msg)
                except TypeError:
                    emit_progress(name)

        ctx = ToolContext(
            repo_dir=self.repo_dir,
            data_root=self.data_root,
            pending_events=pending_events,
            agent=self,
            emit_progress_fn=_emit,
        )
        self.tools.set_context(ctx)

        messages = build_messages(
            repo_dir=self.repo_dir,
            data_root=self.data_root,
            user_message=user_message,
        )

        # Run loop
        final_text, _ = run_loop(
            messages=messages,
            tools=self.tools,
            logs_dir=self.logs_dir,
            emit_progress=emit_progress,
        )

        # Log chat
        append_jsonl(self.logs_dir / "chat.jsonl", {
            "ts": utc_now_iso(), "direction": "in", "text": user_message[:500],
        })
        append_jsonl(self.logs_dir / "chat.jsonl", {
            "ts": utc_now_iso(), "direction": "out", "text": final_text[:2000],
        })

        # Expose for Telegram (send_message handled there; send_file in control tool)
        self._last_pending_events = pending_events

        # Process pending events (e.g. send_message) — CLI mode
        for evt in pending_events:
            if evt.get("type") == "send_message":
                print("[Agent message]:", evt.get("text", "")[:200])

        return final_text
