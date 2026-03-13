"""
Tool registry — SSOT for all tools.
Auto-discovery: each module exports get_tools().
"""

import importlib
import pkgutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


@dataclass
class ToolContext:
    """Context passed to each tool."""

    repo_dir: Path
    data_root: Path
    pending_events: List[Dict[str, Any]]
    current_chat_id: Optional[Any] = None
    emit_progress_fn: Callable[[str], None] = lambda _: None
    agent: Optional[Any] = None  # parent Agent for spawn_agents

    def repo_path(self, rel: str) -> Path:
        return (self.repo_dir / rel.lstrip("/")).resolve()

    def data_path(self, rel: str) -> Path:
        return (self.data_root / rel.lstrip("/")).resolve()


@dataclass
class ToolEntry:
    """Single tool: name, schema, handler."""

    name: str
    schema: Dict[str, Any]
    handler: Callable  # fn(ctx, **args) -> str


class ToolRegistry:
    """Collects tools from modules, provides schemas() and execute()."""

    def __init__(self, repo_dir: Path, data_root: Path):
        self._entries: Dict[str, ToolEntry] = {}
        self._ctx = ToolContext(repo_dir=repo_dir, data_root=data_root, pending_events=[])
        self._load_modules()

    def _load_modules(self) -> None:
        import ouroboros.tools as tools_pkg
        for _importer, modname, _ispkg in pkgutil.iter_modules(tools_pkg.__path__):
            if modname.startswith("_") or modname == "registry":
                continue
            try:
                mod = importlib.import_module(f"ouroboros.tools.{modname}")
                if hasattr(mod, "get_tools"):
                    for entry in mod.get_tools():
                        self._entries[entry.name] = entry
            except Exception:
                import logging
                logging.getLogger(__name__).warning("Failed to load tool module %s", modname, exc_info=True)

    def set_context(self, ctx: ToolContext) -> None:
        self._ctx = ctx

    def schemas(self) -> List[Dict[str, Any]]:
        return [{"type": "function", "function": e.schema} for e in self._entries.values()]

    def execute(self, name: str, args: Dict[str, Any]) -> str:
        entry = self._entries.get(name)
        if entry is None:
            return f"Unknown tool: {name}. Available: {', '.join(sorted(self._entries.keys()))}"
        try:
            return entry.handler(self._ctx, **args)
        except TypeError as e:
            return f"Tool arg error ({name}): {e}"
        except Exception as e:
            return f"Tool error ({name}): {e}"
