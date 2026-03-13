"""Git tools: repo_edit, repo_commit, repo_push — self-modification core."""

import subprocess
from pathlib import Path

from ouroboros.tools.registry import ToolContext, ToolEntry
from ouroboros.utils import read_text, write_text


def _safe_repo_path(ctx: ToolContext, path: str) -> Path:
    """Resolve path inside repo_dir, block escape."""
    p = ctx.repo_path(path)
    repo = ctx.repo_dir.resolve()
    if not str(p.resolve()).startswith(str(repo)):
        raise ValueError("Path must be inside repo")
    return p


def _repo_edit(ctx: ToolContext, path: str, content: str) -> str:
    """Edit a file in the repo. Overwrites entire file."""
    p = _safe_repo_path(ctx, path)
    write_text(p, content)
    return f"OK: edited {path} ({len(content)} chars)"


def _repo_commit(ctx: ToolContext, message: str) -> str:
    """Stage all changes and commit."""
    try:
        subprocess.run(
            ["git", "add", "-A"],
            cwd=str(ctx.repo_dir),
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
        result = subprocess.run(
            ["git", "commit", "-m", message],
            cwd=str(ctx.repo_dir),
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            return f"OK: committed — {message}"
        if "nothing to commit" in (result.stderr or "").lower():
            return "Nothing to commit (working tree clean)"
        return f"Commit failed: {result.stderr or result.stdout or 'unknown'}"
    except subprocess.TimeoutExpired:
        return "Error: git command timed out"
    except FileNotFoundError:
        return "Error: git not found"


def _repo_push(ctx: ToolContext) -> str:
    """Push commits to remote."""
    try:
        result = subprocess.run(
            ["git", "push"],
            cwd=str(ctx.repo_dir),
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0:
            return "OK: pushed to remote"
        return f"Push failed: {result.stderr or result.stdout or 'unknown'}"
    except subprocess.TimeoutExpired:
        return "Error: git push timed out"
    except FileNotFoundError:
        return "Error: git not found"


def _repo_status(ctx: ToolContext) -> str:
    """Show git status (short)."""
    try:
        result = subprocess.run(
            ["git", "status", "--short"],
            cwd=str(ctx.repo_dir),
            capture_output=True,
            text=True,
            timeout=10,
        )
        out = (result.stdout or "").strip() or "(clean)"
        return out
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return "Error: could not get status"


def get_tools() -> list:
    return [
        ToolEntry("repo_edit", {
            "name": "repo_edit",
            "description": "Edit a file in the repo. Overwrites entire file. Use for self-modification.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path relative to repo root"},
                    "content": {"type": "string", "description": "New file content"},
                },
                "required": ["path", "content"],
            },
        }, _repo_edit),
        ToolEntry("repo_commit", {
            "name": "repo_commit",
            "description": "Stage all changes and commit.",
            "parameters": {
                "type": "object",
                "properties": {"message": {"type": "string"}},
                "required": ["message"],
            },
        }, _repo_commit),
        ToolEntry("repo_push", {
            "name": "repo_push",
            "description": "Push commits to remote.",
            "parameters": {"type": "object", "properties": {}},
        }, _repo_push),
        ToolEntry("repo_status", {
            "name": "repo_status",
            "description": "Show git status (short).",
            "parameters": {"type": "object", "properties": {}},
        }, _repo_status),
    ]
