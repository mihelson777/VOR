"""Control tools: update_scratchpad, update_identity, chat_history, send_message."""

from ouroboros.tools.registry import ToolContext, ToolEntry
from ouroboros.utils import utc_now_iso


def _update_scratchpad(ctx: ToolContext, content: str) -> str:
    from ouroboros.memory import Memory
    mem = Memory(ctx.data_root)
    mem.save_scratchpad(content)
    return f"OK: scratchpad updated ({len(content)} chars)"


def _update_identity(ctx: ToolContext, content: str) -> str:
    path = ctx.data_root / "memory" / "identity.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return f"OK: identity updated ({len(content)} chars)"


def _chat_history(ctx: ToolContext, count: int = 50, offset: int = 0) -> str:
    from ouroboros.memory import Memory
    mem = Memory(ctx.data_root)
    return mem.chat_history(count=count, offset=offset)


def _send_message(ctx: ToolContext, text: str) -> str:
    ctx.pending_events.append({
        "type": "send_message",
        "text": text,
        "ts": utc_now_iso(),
    })
    return "OK: message queued"


def get_tools() -> list:
    return [
        ToolEntry("update_scratchpad", {
            "name": "update_scratchpad",
            "description": "Update working memory. Persists across sessions.",
            "parameters": {"type": "object", "properties": {"content": {"type": "string"}}, "required": ["content"]},
        }, _update_scratchpad),
        ToolEntry("update_identity", {
            "name": "update_identity",
            "description": "Update identity manifest (who you are).",
            "parameters": {"type": "object", "properties": {"content": {"type": "string"}}, "required": ["content"]},
        }, _update_identity),
        ToolEntry("chat_history", {
            "name": "chat_history",
            "description": "Get recent chat messages from memory. Use when you need to recall past conversation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "count": {"type": "integer", "description": "Number of messages to return (default 50, max 100)"},
                    "offset": {"type": "integer", "description": "Skip first N messages (default 0)"},
                },
                "required": [],
            },
        }, _chat_history),
        ToolEntry("send_message", {
            "name": "send_message",
            "description": "Send a proactive message to the user. In Telegram: delivers to the chat. In Web: delivers to owner's Telegram if TELEGRAM_OWNER_CHAT_ID is configured. Use when user asks to notify them in Telegram or send something there.",
            "parameters": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]},
        }, _send_message),
    ]
