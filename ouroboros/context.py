"""Build LLM messages from system prompt, memory, and dialogue."""

import json
from pathlib import Path
from typing import Any, Dict, List

from ouroboros.utils import read_text, clip_text


def _load_chat_history(data_root: Path, max_turns: int = 10) -> List[Dict[str, Any]]:
    """Load last N turns from chat.jsonl. Returns [user, assistant, user, ...]."""
    chat_path = data_root / "logs" / "chat.jsonl"
    if not chat_path.exists():
        return []
    try:
        lines = [l for l in read_text(chat_path).strip().split("\n") if l.strip()]
        entries = []
        for line in lines:
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        if not entries:
            return []
        entries = entries[-(max_turns * 2) :]  # each turn = in + out
        result = []
        for e in entries:
            direction = str(e.get("direction", "")).lower()
            text = str(e.get("text", "")).strip()
            if not text:
                continue
            if direction in ("in", "incoming"):
                result.append({"role": "user", "content": text})
            elif direction in ("out", "outgoing"):
                result.append({"role": "assistant", "content": text})
        return result
    except Exception:
        return []


def build_messages(
    repo_dir: Path,
    data_root: Path,
    user_message: str,
) -> List[Dict[str, Any]]:
    """Build messages for LLM: system + context + chat history + current user."""
    system = _build_system(repo_dir, data_root)
    messages = [{"role": "system", "content": system}]

    history = _load_chat_history(data_root, max_turns=10)
    for msg in history:
        messages.append(msg)

    messages.append({"role": "user", "content": user_message})
    return messages


def _build_system(repo_dir: Path, data_root: Path) -> str:
    parts = []

    # SYSTEM.md
    system_path = repo_dir / "prompts" / "SYSTEM.md"
    if system_path.exists():
        parts.append(read_text(system_path))

    # BIBLE.md (abbreviated)
    bible_path = repo_dir / "BIBLE.md"
    if bible_path.exists():
        parts.append("## BIBLE.md\n\n" + clip_text(read_text(bible_path), 4000))

    # Identity
    identity_path = data_root / "memory" / "identity.md"
    if identity_path.exists():
        parts.append("## Identity\n\n" + clip_text(read_text(identity_path), 3000))

    # Scratchpad
    scratchpad_path = data_root / "memory" / "scratchpad.md"
    if scratchpad_path.exists():
        parts.append("## Scratchpad\n\n" + clip_text(read_text(scratchpad_path), 4000))

    return "\n\n---\n\n".join(parts)
