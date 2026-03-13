"""
Memory — scratchpad, identity, chat history.
"""

import json
from pathlib import Path
from typing import Any, Dict, List

from ouroboros.utils import read_text, write_text, append_jsonl, short


class Memory:
    """Scratchpad, identity, chat history."""

    def __init__(self, data_root: Path):
        self.data_root = data_root
        self.memory_dir = data_root / "memory"
        self.logs_dir = data_root / "logs"
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)

    def scratchpad_path(self) -> Path:
        return self.memory_dir / "scratchpad.md"

    def identity_path(self) -> Path:
        return self.memory_dir / "identity.md"

    @property
    def scratchpad(self) -> str:
        return self.load_scratchpad()

    @property
    def identity(self) -> str:
        return self.load_identity()

    def chat_count(self) -> int:
        chat_path = self.logs_dir / "chat.jsonl"
        if not chat_path.exists():
            return 0
        return len([l for l in read_text(chat_path).strip().split("\n") if l.strip()])

    def load_scratchpad(self) -> str:
        p = self.scratchpad_path()
        if p.exists():
            return read_text(p)
        default = "# Scratchpad\n\n(empty)\n"
        write_text(p, default)
        return default

    def load_identity(self) -> str:
        p = self.identity_path()
        if p.exists():
            return read_text(p)
        default = (
            "# Who I Am\n\n"
            "I am a self-creating agent. This file is my persistent self-identification.\n"
        )
        write_text(p, default)
        return default

    def save_scratchpad(self, content: str) -> None:
        write_text(self.scratchpad_path(), content)

    def save_identity(self, content: str) -> None:
        write_text(self.identity_path(), content)

    def chat_history(self, count: int = 50, offset: int = 0) -> str:
        chat_path = self.logs_dir / "chat.jsonl"
        if not chat_path.exists():
            return "(chat history is empty)"

        try:
            lines = read_text(chat_path).strip().split("\n")
            entries = []
            for line in lines:
                if not line.strip():
                    continue
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

            if offset > 0:
                entries = entries[:-offset] if offset < len(entries) else []
            entries = entries[-count:] if count < len(entries) else entries

            if not entries:
                return "(no messages)"

            result = []
            for e in entries:
                direction = "→" if str(e.get("direction", "")).lower() in ("out", "outgoing") else "←"
                ts = str(e.get("ts", ""))[:16]
                text = str(e.get("text", ""))
                if direction == "→":
                    text = short(text, 800)
                result.append(f"{direction} [{ts}] {text}")

            return f"Last {len(entries)} messages:\n\n" + "\n".join(result)
        except Exception as e:
            return f"(error: {e})"
