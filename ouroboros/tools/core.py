"""Core tools: repo_read, repo_list, data_read, data_list, data_write."""

import json
from pathlib import Path

from ouroboros.tools.registry import ToolContext, ToolEntry
from ouroboros.utils import read_text


def _safe_path(root: Path, rel: str) -> Path:
    p = (root / rel.lstrip("/")).resolve()
    if not str(p).startswith(str(root.resolve())):
        raise ValueError("Path escape attempt")
    return p


def _repo_read(ctx: ToolContext, path: str) -> str:
    return read_text(ctx.repo_path(path))


def _repo_list(ctx: ToolContext, dir: str = ".") -> str:
    target = ctx.repo_path(dir)
    if not target.exists():
        return "Directory not found"
    if not target.is_dir():
        return "Not a directory"
    items = sorted(p.relative_to(ctx.repo_dir).as_posix() + ("/" if p.is_dir() else "")
                   for p in target.iterdir())[:200]
    return json.dumps(items, ensure_ascii=False, indent=2)


def _data_read(ctx: ToolContext, path: str) -> str:
    return read_text(ctx.data_path(path))


def _data_list(ctx: ToolContext, dir: str = ".") -> str:
    target = ctx.data_path(dir)
    if not target.exists():
        return "Directory not found"
    if not target.is_dir():
        return "Not a directory"
    items = sorted(p.relative_to(ctx.data_root).as_posix() + ("/" if p.is_dir() else "")
                   for p in target.iterdir())[:200]
    return json.dumps(items, ensure_ascii=False, indent=2)


def _data_write(ctx: ToolContext, path: str, content: str, mode: str = "overwrite") -> str:
    from ouroboros.utils import write_text
    p = ctx.data_path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    if mode == "overwrite":
        p.write_text(content, encoding="utf-8")
    else:
        with p.open("a", encoding="utf-8") as f:
            f.write(content)
    return f"OK: wrote {path} ({len(content)} chars)"


def get_tools() -> list:
    return [
        ToolEntry("repo_read", {
            "name": "repo_read",
            "description": "Read a file from the repo.",
            "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
        }, _repo_read),
        ToolEntry("repo_list", {
            "name": "repo_list",
            "description": "List files in a repo directory.",
            "parameters": {"type": "object", "properties": {"dir": {"type": "string", "default": "."}}, "required": []},
        }, _repo_list),
        ToolEntry("data_read", {
            "name": "data_read",
            "description": "Read a file from data storage (memory, logs, state).",
            "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
        }, _data_read),
        ToolEntry("data_list", {
            "name": "data_list",
            "description": "List files in data directory.",
            "parameters": {"type": "object", "properties": {"dir": {"type": "string", "default": "."}}, "required": []},
        }, _data_list),
        ToolEntry("data_write", {
            "name": "data_write",
            "description": "Write a file to data storage.",
            "parameters": {"type": "object", "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
                "mode": {"type": "string", "enum": ["overwrite", "append"], "default": "overwrite"},
            }, "required": ["path", "content"]},
        }, _data_write),
    ]
