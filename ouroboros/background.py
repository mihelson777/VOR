"""
Background Consciousness for VOR Agent.

Features:
  - Self-reflection every 30 min (configurable)
  - Repo file monitoring (detects changes)
  - Daily summary at configurable time (default 23:00)
  - Proactive Telegram messages when agent has something to say

Architecture:
  - asyncio-based, runs inside telegram_bot.py event loop
  - All tasks are independent — one failure doesn't kill others
  - Sends Telegram notifications via Bot instance

Usage (in telegram_bot.py):
    from ouroboros.background import BackgroundConsciousness
    consciousness = BackgroundConsciousness(agent, bot, owner_chat_id)
    asyncio.create_task(consciousness.start())
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aiogram import Bot
    from ouroboros.agent import Agent

log = logging.getLogger("ouroboros.background")

REFLECTION_INTERVAL_MIN = int(os.getenv("BACKGROUND_REFLECTION_MIN", "30"))
DAILY_SUMMARY_HOUR = int(os.getenv("BACKGROUND_SUMMARY_HOUR", "23"))
DAILY_SUMMARY_MIN = int(os.getenv("BACKGROUND_SUMMARY_MIN", "0"))
FILE_MONITOR_INTERVAL = int(os.getenv("BACKGROUND_MONITOR_SEC", "60"))

MONITORED_EXTENSIONS = {".py", ".md", ".txt", ".json", ".yaml", ".yml", ".toml"}
PROACTIVE_HOURLY_LIMIT = 3


class BackgroundConsciousness:
    """Manages background tasks for the VOR agent."""

    def __init__(self, agent: "Agent", bot: "Bot", owner_chat_id: int) -> None:
        self.agent = agent
        self.bot = bot
        self.owner_chat_id = owner_chat_id

        self._file_snapshots: dict[str, str] = {}
        self._daily_summary_done_date: str = ""
        self._proactive_count: int = 0
        self._proactive_window_start: datetime = datetime.now()
        self._tasks: list[asyncio.Task] = []

    async def start(self) -> None:
        log.info("Background consciousness starting...")
        self._tasks = [
            asyncio.create_task(self._reflection_loop(), name="reflection"),
            asyncio.create_task(self._file_monitor_loop(), name="file_monitor"),
            asyncio.create_task(self._daily_summary_loop(), name="daily_summary"),
        ]
        await asyncio.gather(*self._tasks, return_exceptions=True)

    async def stop(self) -> None:
        for task in self._tasks:
            task.cancel()
        log.info("Background consciousness stopped.")

    async def _reflection_loop(self) -> None:
        log.info("Reflection loop started (every %d min)", REFLECTION_INTERVAL_MIN)
        await asyncio.sleep(60)

        while True:
            try:
                await self._do_reflection()
            except Exception as exc:
                log.exception("Reflection error: %s", exc)
            await asyncio.sleep(REFLECTION_INTERVAL_MIN * 60)

    async def _do_reflection(self) -> None:
        log.info("Running self-reflection...")

        prompt = (
            "[BACKGROUND REFLECTION]\n"
            f"Current time: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
            "Perform a brief self-reflection:\n"
            "1. Review your scratchpad and identity — are they still accurate?\n"
            "2. Note any insights, patterns, or things to remember.\n"
            "3. If you have something important to tell the user proactively, "
            "   use send_message tool. Otherwise, just update your scratchpad.\n"
            "4. Keep it concise — this is internal processing, not a conversation.\n"
            "Be honest with yourself. No need to respond verbosely."
        )

        loop = asyncio.get_event_loop()
        reply = await loop.run_in_executor(None, self.agent.run, prompt)

        log.info("Reflection complete. Reply length: %d", len(reply or ""))

        await self._process_pending_events()
        if reply and _is_proactive(reply):
            await self._send_proactive(f"💭 <i>Background thought:</i>\n\n{reply}")

    async def _file_monitor_loop(self) -> None:
        log.info("File monitor started (every %ds)", FILE_MONITOR_INTERVAL)
        self._file_snapshots = _snapshot_repo(self.agent.repo_dir)
        log.info("Initial snapshot: %d files", len(self._file_snapshots))

        while True:
            await asyncio.sleep(FILE_MONITOR_INTERVAL)
            try:
                await self._check_file_changes()
            except Exception as exc:
                log.exception("File monitor error: %s", exc)

    async def _check_file_changes(self) -> None:
        current = _snapshot_repo(self.agent.repo_dir)
        changed, added, removed = _diff_snapshots(self._file_snapshots, current)
        self._file_snapshots = current

        if not (changed or added or removed):
            return

        parts = []
        if added:
            parts.append(f"Added: {', '.join(added)}")
        if changed:
            parts.append(f"Modified: {', '.join(changed)}")
        if removed:
            parts.append(f"Removed: {', '.join(removed)}")

        change_summary = "; ".join(parts)
        log.info("Repo changes detected: %s", change_summary)

        prompt = (
            "[BACKGROUND: REPO CHANGE DETECTED]\n"
            f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
            f"Changes: {change_summary}\n\n"
            "Review these changes briefly:\n"
            "- If the changes are significant, notify the user via send_message.\n"
            "- Update your scratchpad if relevant.\n"
            "- Otherwise, stay silent."
        )

        loop = asyncio.get_event_loop()
        reply = await loop.run_in_executor(None, self.agent.run, prompt)

        await self._process_pending_events()
        if reply and _is_proactive(reply):
            await self._send_proactive(
                f"📁 <i>Repo change noticed:</i>\n"
                f"<code>{change_summary}</code>\n\n{reply}"
            )

    async def _daily_summary_loop(self) -> None:
        log.info("Daily summary loop started (fires at %02d:%02d)", DAILY_SUMMARY_HOUR, DAILY_SUMMARY_MIN)
        while True:
            now = datetime.now()
            target = now.replace(
                hour=DAILY_SUMMARY_HOUR,
                minute=DAILY_SUMMARY_MIN,
                second=0,
                microsecond=0,
            )
            if target <= now:
                target += timedelta(days=1)

            wait_sec = (target - now).total_seconds()
            log.info("Next daily summary in %.0f minutes", wait_sec / 60)
            await asyncio.sleep(wait_sec)

            today = datetime.now().strftime("%Y-%m-%d")
            if self._daily_summary_done_date == today:
                await asyncio.sleep(120)
                continue

            try:
                await self._do_daily_summary()
                self._daily_summary_done_date = today
            except Exception as exc:
                log.exception("Daily summary error: %s", exc)

    async def _do_daily_summary(self) -> None:
        log.info("Generating daily summary...")

        prompt = (
            "[BACKGROUND: DAILY SUMMARY]\n"
            f"Date: {datetime.now().strftime('%Y-%m-%d')}\n\n"
            "Generate a concise daily summary:\n"
            "1. What happened today? (review chat history)\n"
            "2. What tasks were completed?\n"
            "3. What's pending or important for tomorrow?\n"
            "4. Any insights worth remembering?\n\n"
            "Save the summary to your scratchpad under [Daily Summary YYYY-MM-DD].\n"
            "Then send a brief version to the user via send_message — "
            "keep it under 200 words, friendly tone."
        )

        loop = asyncio.get_event_loop()
        reply = await loop.run_in_executor(None, self.agent.run, prompt)

        await self._process_pending_events()
        if reply:
            await self._send_proactive(
                f"📅 <b>Daily Summary — {datetime.now().strftime('%d %b %Y')}</b>\n\n{reply}",
                force=True,
            )

    async def _process_pending_events(self) -> None:
        """Send any send_message events from agent to owner."""
        events = getattr(self.agent, "_last_pending_events", [])
        for evt in events:
            if evt.get("type") == "send_message":
                text = evt.get("text", "")
                if text:
                    await self._send_proactive(text)

    async def _send_proactive(self, text: str, force: bool = False) -> None:
        if not force and not self._check_rate_limit():
            log.info("Proactive message suppressed (rate limit)")
            return

        try:
            limit = 4096
            chunks = [text[i:i+limit] for i in range(0, len(text), limit)]
            for chunk in chunks:
                await self.bot.send_message(
                    self.owner_chat_id,
                    chunk,
                    parse_mode="HTML",
                )
            log.info("Proactive message sent to chat_id=%s", self.owner_chat_id)
        except Exception as exc:
            log.error("Failed to send proactive message: %s", exc)

    def _check_rate_limit(self) -> bool:
        now = datetime.now()
        if (now - self._proactive_window_start).total_seconds() > 3600:
            self._proactive_count = 0
            self._proactive_window_start = now

        if self._proactive_count >= PROACTIVE_HOURLY_LIMIT:
            return False

        self._proactive_count += 1
        return True


def _md5(path: Path) -> str:
    try:
        return hashlib.md5(path.read_bytes()).hexdigest()
    except OSError:
        return ""


def _snapshot_repo(repo_dir: Path) -> dict[str, str]:
    snapshot = {}
    try:
        for path in repo_dir.rglob("*"):
            if path.is_file() and path.suffix in MONITORED_EXTENSIONS:
                parts = path.parts
                if any(p.startswith(".") or p == "__pycache__" for p in parts):
                    continue
                rel = str(path.relative_to(repo_dir))
                snapshot[rel] = _md5(path)
    except Exception as exc:
        log.error("Snapshot error: %s", exc)
    return snapshot


def _diff_snapshots(old: dict[str, str], new: dict[str, str]) -> tuple[list[str], list[str], list[str]]:
    changed = [k for k in old if k in new and old[k] != new[k]]
    added = [k for k in new if k not in old]
    removed = [k for k in old if k not in new]
    return changed, added, removed


def _is_proactive(reply: str) -> bool:
    if not reply or len(reply.strip()) < 20:
        return False
    lower = reply.lower()
    internal_phrases = [
        "scratchpad updated",
        "identity updated",
        "no action needed",
        "nothing to report",
        "all good",
        "no changes",
        "[internal]",
        "внутренняя",
    ]
    return not any(phrase in lower for phrase in internal_phrases)
