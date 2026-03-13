"""Build LLM messages from system prompt, memory, and dialogue."""

from pathlib import Path
from typing import Any, Dict, List


from ouroboros.utils import read_text, clip_text


def build_messages(
    repo_dir: Path,
    data_root: Path,
    user_message: str,
) -> List[Dict[str, Any]]:
    """Build messages for LLM: system + context + user."""
    system = _build_system(repo_dir, data_root)
    messages = [{"role": "system", "content": system}]

    # Recent chat (simplified — in full version would load from chat.jsonl)
    # For now we just have the current user message
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
