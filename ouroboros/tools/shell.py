"""Shell tool: shell_exec — run command with timeout."""

import shlex
import subprocess
from pathlib import Path

from ouroboros.tools.registry import ToolContext, ToolEntry


def _shell_exec(ctx: ToolContext, cmd: str, timeout: int = 60) -> str:
    """Run shell command. Cwd = repo_dir. Returns stdout+stderr."""
    if not cmd or not cmd.strip():
        return "Error: empty command"
    # Block obviously dangerous patterns
    lower = cmd.lower().strip()
    for blocked in ("format ", "del /", "rm -rf /", "mkfs", ":(){ :|:& };:"):
        if blocked in lower:
            return f"Error: blocked command pattern"
    try:
        # shlex.split handles quotes correctly (e.g. "echo hello")
        parts = shlex.split(cmd)
        if not parts:
            return "Error: no executable"
        result = subprocess.run(
            parts,
            cwd=str(ctx.repo_dir),
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
        )
        out = (result.stdout or "").strip()
        err = (result.stderr or "").strip()
        combined = f"{out}\n{err}".strip() if err else out
        if result.returncode != 0:
            return f"[exit {result.returncode}]\n{combined}"
        return combined or "(no output)"
    except subprocess.TimeoutExpired:
        return f"Error: command timed out after {timeout}s"
    except FileNotFoundError as e:
        return f"Error: {e}"
    except Exception as e:
        return f"Error: {e}"


def get_tools() -> list:
    return [
        ToolEntry("shell_exec", {
            "name": "shell_exec",
            "description": "Run a shell command. Working dir = repo. Use for scripts, tests, etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "cmd": {"type": "string", "description": "Command (e.g. 'python -c \"print(1)\"')"},
                    "timeout": {"type": "integer", "description": "Timeout in seconds", "default": 60},
                },
                "required": ["cmd"],
            },
        }, _shell_exec),
    ]
