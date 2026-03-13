"""
Telegram interface for VOR Agent.

Features:
  - Polling mode (local dev, no webhook needed)
  - Webhook mode (production)
  - Groups + private messages
  - File send/receive
  - Inline buttons: /help, /status, /memory, /restart

Setup:
  1. pip install aiogram aiohttp
  2. Add to .env: TELEGRAM_BOT_TOKEN=your_token
  3. Optional: TELEGRAM_ALLOWED_USERS=123456789,987654321
  4. Polling (local): python telegram_bot.py
  5. Webhook (prod): TELEGRAM_WEBHOOK_URL=https://... TELEGRAM_WEBHOOK_PORT=8443
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import (
    DATA_ROOT,
    PROJECT_ROOT as REPO_DIR,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_OWNER_CHAT_ID,
)
from ouroboros.agent import Agent
from ouroboros.background import BackgroundConsciousness
from ouroboros.voice import transcribe, synthesize

from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    BotCommand,
    BufferedInputFile,
    CallbackQuery,
    Document,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("ouroboros.telegram")

WEBHOOK_URL = os.getenv("TELEGRAM_WEBHOOK_URL", "").rstrip("/")
WEBHOOK_PORT = int(os.getenv("TELEGRAM_WEBHOOK_PORT", "8443"))
WEBHOOK_PATH = "/webhook"

_raw_allowed = os.getenv("TELEGRAM_ALLOWED_USERS", "")
ALLOWED_USERS: set[int] = (
    {int(u.strip()) for u in _raw_allowed.split(",") if u.strip()}
    if _raw_allowed else set()
)

UPLOADS_DIR = DATA_ROOT / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

FILES_DIR = DATA_ROOT / "files"
FILES_DIR.mkdir(parents=True, exist_ok=True)

# Bot created in main() — not at import (token may be empty)
bot: Bot | None = None

_agents: dict[int, Agent] = {}


def get_agent(chat_id: int) -> Agent:
    if chat_id not in _agents:
        log.info("Creating new Agent for chat_id=%s", chat_id)
        _agents[chat_id] = Agent(repo_dir=REPO_DIR, data_root=DATA_ROOT)
    return _agents[chat_id]


def is_allowed(user_id: int) -> bool:
    return not ALLOWED_USERS or user_id in ALLOWED_USERS


def main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📋 /status", callback_data="cmd_status"),
            InlineKeyboardButton(text="🧠 /memory", callback_data="cmd_memory"),
        ],
        [
            InlineKeyboardButton(text="❓ /help", callback_data="cmd_help"),
            InlineKeyboardButton(text="🔄 Restart", callback_data="cmd_restart"),
        ],
    ])


async def send_long(message: Message, text: str, reply_markup=None) -> None:
    limit = 4096
    chunks = [text[i:i+limit] for i in range(0, len(text), limit)]
    for i, chunk in enumerate(chunks):
        kb = reply_markup if i == len(chunks) - 1 else None
        await message.answer(chunk, reply_markup=kb)


dp = Dispatcher()


@dp.message(CommandStart())
async def cmd_start(message: Message) -> None:
    if not is_allowed(message.from_user.id):
        await message.answer("⛔ Access denied.")
        return

    text = (
        "👋 <b>VOR Agent online.</b>\n\n"
        "I'm your personal AI secretary. Send me any message or task.\n\n"
        "Commands:\n"
        "/help — what I can do\n"
        "/status — current state\n"
        "/memory — show scratchpad\n\n"
        "You can also send me files and I'll read them."
    )
    await message.answer(text, reply_markup=main_keyboard())


@dp.message(Command("help"))
async def cmd_help(message: Message) -> None:
    if not is_allowed(message.from_user.id):
        return

    text = (
        "<b>🤖 VOR — Personal AI Secretary</b>\n\n"
        "<b>Chat:</b> Just write to me naturally.\n\n"
        "<b>Tools:</b> Web search, page fetch, files, shell, git, memory\n\n"
        "<b>Commands:</b> /start, /help, /status, /memory\n"
    )
    await message.answer(text, reply_markup=main_keyboard())


@dp.message(Command("status"))
async def cmd_status(message: Message) -> None:
    if not is_allowed(message.from_user.id):
        return

    agent = get_agent(message.chat.id)
    mem = agent.memory

    text = (
        "<b>📊 Agent Status</b>\n\n"
        f"🔧 Repo: <code>{REPO_DIR}</code>\n"
        f"📦 Data: <code>{DATA_ROOT}</code>\n"
        f"🧠 Scratchpad: {len(mem.scratchpad or '')} chars\n"
        f"🪪 Identity: {len(mem.identity or '')} chars\n"
        f"💬 Chat entries: {mem.chat_count()}\n"
    )
    await message.answer(text, reply_markup=main_keyboard())


@dp.message(Command("memory"))
async def cmd_memory(message: Message) -> None:
    if not is_allowed(message.from_user.id):
        return

    agent = get_agent(message.chat.id)
    scratch = agent.memory.scratchpad or "(empty)"
    identity = agent.memory.identity or "(empty)"

    text = (
        "<b>🧠 Memory</b>\n\n"
        "<b>Scratchpad:</b>\n"
        f"<pre>{scratch[:1500]}</pre>\n\n"
        "<b>Identity:</b>\n"
        f"<pre>{identity[:1500]}</pre>"
    )
    await send_long(message, text, reply_markup=main_keyboard())


@dp.callback_query(F.data == "cmd_status")
async def cb_status(query: CallbackQuery) -> None:
    await query.answer()
    await cmd_status(query.message)


@dp.callback_query(F.data == "cmd_memory")
async def cb_memory(query: CallbackQuery) -> None:
    await query.answer()
    await cmd_memory(query.message)


@dp.callback_query(F.data == "cmd_help")
async def cb_help(query: CallbackQuery) -> None:
    await query.answer()
    await cmd_help(query.message)


@dp.callback_query(F.data == "cmd_restart")
async def cb_restart(query: CallbackQuery) -> None:
    await query.answer("♻️ Restarting agent...")
    chat_id = query.message.chat.id
    if chat_id in _agents:
        del _agents[chat_id]
    await query.message.answer(
        "♻️ Agent restarted. Fresh session started.",
        reply_markup=main_keyboard()
    )


@dp.message(F.voice)
async def handle_voice(message: Message) -> None:
    if not is_allowed(message.from_user.id):
        return

    voice = message.voice
    file = await message.bot.get_file(voice.file_id)
    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as f:
        path = f.name
    try:
        await message.bot.download_file(file.file_path, destination=path)
        text = transcribe(path)
    finally:
        try:
            os.unlink(path)
        except Exception:
            pass

    if not text or text.startswith("ERROR"):
        await message.answer("Could not transcribe voice. Try again.")
        return

    await message.answer(f"🎤 Heard: {text}")
    await _process_message(message, text)


@dp.message(F.document)
async def handle_document(message: Message) -> None:
    if not is_allowed(message.from_user.id):
        return

    doc: Document = message.document
    file_path = UPLOADS_DIR / doc.file_name

    file = await message.bot.get_file(doc.file_id)
    await message.bot.download_file(file.file_path, destination=file_path)

    log.info("File received: %s (%d bytes)", doc.file_name, doc.file_size)

    caption = message.caption or ""
    user_msg = (
        f"User sent a file: {doc.file_name} "
        f"(saved to data/uploads/{doc.file_name}). "
        f"{caption}"
    ).strip()

    await _process_message(message, user_msg)


@dp.message(F.text)
async def handle_text(message: Message) -> None:
    if not is_allowed(message.from_user.id):
        await message.answer("⛔ Access denied.")
        return

    if message.text and message.text.startswith("/"):
        return

    await _process_message(message, message.text or "")


async def _process_message(message: Message, user_text: str) -> None:
    agent = get_agent(message.chat.id)

    await message.bot.send_chat_action(message.chat.id, "typing")

    try:
        loop = asyncio.get_event_loop()
        reply = await loop.run_in_executor(None, agent.run, user_text)

        events = getattr(agent, "_last_pending_events", [])
        for evt in events:
            if evt.get("type") == "send_file":
                path = FILES_DIR / evt.get("filename", "")
                if path.exists():
                    data = path.read_bytes()
                    tg_file = BufferedInputFile(data, filename=path.name)
                    caption = evt.get("caption", "")
                    await message.bot.send_document(message.chat.id, tg_file, caption=caption)
                    log.info("Sent file: %s", path.name)
                else:
                    await message.answer(f"⚠️ File not found: {path.name}")

        if reply:
            await send_long(message, reply, reply_markup=main_keyboard())

    except Exception as exc:
        log.exception("Agent error: %s", exc)
        await message.answer(
            f"⚠️ Agent error: <code>{exc}</code>",
            reply_markup=main_keyboard()
        )


async def on_startup(app: web.Application, bot_instance: Bot) -> None:
    webhook_url = f"{WEBHOOK_URL}{WEBHOOK_PATH}"
    await bot_instance.set_webhook(webhook_url)
    log.info("Webhook set: %s", webhook_url)

    await bot_instance.set_my_commands([
        BotCommand(command="start", description="Start / greeting"),
        BotCommand(command="help", description="What I can do"),
        BotCommand(command="status", description="Agent status"),
        BotCommand(command="memory", description="Show scratchpad & identity"),
    ])
    log.info("Bot commands registered.")


async def on_shutdown(app: web.Application, bot_instance: Bot) -> None:
    await bot_instance.delete_webhook()
    await bot_instance.session.close()
    log.info("Webhook removed, bot stopped.")


def _start_background_consciousness(bot_instance: Bot) -> None:
    """Start background consciousness if TELEGRAM_OWNER_CHAT_ID is set."""
    try:
        owner_id = TELEGRAM_OWNER_CHAT_ID.strip()
        if not owner_id:
            log.info("TELEGRAM_OWNER_CHAT_ID not set — background consciousness disabled")
            return
        owner_chat_id = int(owner_id)
        agent = get_agent(owner_chat_id)
        consciousness = BackgroundConsciousness(agent, bot_instance, owner_chat_id)
        asyncio.create_task(consciousness.start())
        log.info("Background consciousness started for chat_id=%s", owner_chat_id)
    except (ValueError, Exception) as e:
        log.warning("Could not start background consciousness: %s", e)


async def _run_polling_with_background(bot_instance: Bot) -> None:
    """Start polling and background consciousness."""
    _start_background_consciousness(bot_instance)
    await dp.start_polling(bot_instance)


def main() -> None:
    global bot
    if not TELEGRAM_BOT_TOKEN:
        log.error("TELEGRAM_BOT_TOKEN is not set in .env")
        sys.exit(1)

    bot = Bot(token=TELEGRAM_BOT_TOKEN, parse_mode=ParseMode.HTML)

    if WEBHOOK_URL:
        async def _on_startup(app: web.Application) -> None:
            await on_startup(app, bot)
            _start_background_consciousness(bot)

        async def _on_shutdown(app: web.Application) -> None:
            await on_shutdown(app, bot)

        app = web.Application()
        app.on_startup.append(_on_startup)
        app.on_shutdown.append(_on_shutdown)

        SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)
        setup_application(app, dp, bot=bot)

        log.info("Starting webhook server on port %d", WEBHOOK_PORT)
        web.run_app(app, host="0.0.0.0", port=WEBHOOK_PORT)
    else:
        log.info("Starting polling mode (no WEBHOOK_URL — local dev)")
        asyncio.run(_run_polling_with_background(bot))


if __name__ == "__main__":
    main()
