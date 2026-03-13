"""
FastAPI web interface for VOR Agent.

Features:
  - Password authentication (session-based)
  - Chat UI with streaming-like responses
  - Memory panel (scratchpad + identity)
  - Real-time logs via SSE
  - Tool activity panel
  - REST API + SSE

Setup:
  pip install fastapi uvicorn python-multipart

Add to .env:
  WEB_PASSWORD=your_password
  WEB_PORT=8000
  WEB_SECRET_KEY=change_me_to_random_string

Run:
  python web_server.py
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
import logging
import os
import secrets
import sys
from collections import deque
from datetime import datetime
from typing import AsyncGenerator

PROJECT_ROOT = Path(__file__).parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import (
    DATA_ROOT,
    PROJECT_ROOT as REPO_DIR,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_OWNER_CHAT_ID,
    WEB_PASSWORD,
    WEB_PORT,
)
from ouroboros.agent import Agent
from ouroboros.voice import transcribe, synthesize

from fastapi import Cookie, Depends, FastAPI, File, HTTPException, Request, Response, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

log = logging.getLogger("ouroboros.web")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def _suppress_connection_reset(loop, context):
    """Suppress ConnectionResetError when client closes SSE/tab (WinError 10054)."""
    exc = context.get("exception")
    if isinstance(exc, ConnectionResetError):
        return  # ignore
    default = getattr(loop, "default_exception_handler", None)
    if default:
        default(context)

WEB_SECRET_KEY = os.getenv("WEB_SECRET_KEY") or secrets.token_hex(32)

_agent: Agent | None = None
_sessions: set[str] = set()
_log_buffer: deque = deque(maxlen=200)
_tool_events: deque = deque(maxlen=50)
_sse_queues: list[asyncio.Queue] = []
_loop: asyncio.AbstractEventLoop | None = None


def get_agent() -> Agent:
    global _agent
    if _agent is None:
        _agent = Agent(repo_dir=REPO_DIR, data_root=DATA_ROOT)
    return _agent


def push_log(level: str, message: str) -> None:
    entry = {"ts": datetime.now().strftime("%H:%M:%S"), "level": level, "msg": message}
    _log_buffer.append(entry)
    _broadcast({"type": "log", "data": entry})


def push_tool(tool: str, status: str, result: str = "") -> None:
    entry = {"ts": datetime.now().strftime("%H:%M:%S"), "tool": tool, "status": status, "result": result[:200]}
    _tool_events.append(entry)
    _broadcast({"type": "tool", "data": entry})


def _get_last_telegram_content(data_root: Path) -> str | None:
    """Из последнего сообщения юзера с 'в телеграм:' извлечь контент."""
    chat_path = data_root / "logs" / "chat.jsonl"
    if not chat_path.exists():
        return None
    try:
        lines = [l for l in chat_path.read_text(encoding="utf-8").strip().split("\n") if l.strip()]
        for line in reversed(lines):
            try:
                e = json.loads(line)
                if str(e.get("direction", "")).lower() != "in":
                    continue
                txt = str(e.get("text", ""))
                for prefix in ("отправь в телеграм:", "в телеграм:", "напиши в телеграм:"):
                    if prefix in txt.lower():
                        idx = txt.lower().find(prefix) + len(prefix)
                        return txt[idx:].strip()
            except json.JSONDecodeError:
                continue
    except Exception:
        pass
    return None


async def _send_to_telegram(text: str) -> None:
    """Отправить сообщение в Telegram владельцу (из Web UI)."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_OWNER_CHAT_ID:
        return
    try:
        import aiohttp
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        async with aiohttp.ClientSession() as session:
            await session.post(url, json={
                "chat_id": TELEGRAM_OWNER_CHAT_ID.strip(),
                "text": text[:4096],
                "parse_mode": "HTML",
            })
    except Exception as e:
        log.warning("Failed to send to Telegram: %s", e)


def _broadcast(event: dict) -> None:
    if _loop is None:
        return
    for q in list(_sse_queues):
        try:
            _loop.call_soon_threadsafe(q.put_nowait, event)
        except Exception:
            pass


def check_auth(session: str | None = Cookie(default=None)) -> str:
    if not session or session not in _sessions:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return session


app = FastAPI(title="VOR", docs_url=None, redoc_url=None)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.on_event("startup")
def _on_startup():
    loop = asyncio.get_event_loop()
    loop.set_exception_handler(_suppress_connection_reset)

STATIC_DIR = PROJECT_ROOT / "static"
TEMPLATES_DIR = PROJECT_ROOT / "templates"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


class LoginRequest(BaseModel):
    password: str


@app.post("/api/login")
async def login(req: LoginRequest, response: Response):
    pwd = (req.password or "").strip()
    expected = str(WEB_PASSWORD or "").strip()
    if not pwd or pwd != expected:
        raise HTTPException(status_code=401, detail="Wrong password")
    token = secrets.token_hex(32)
    _sessions.add(token)
    response.set_cookie("session", token, httponly=True, samesite="lax", max_age=86400 * 7)
    push_log("INFO", "User logged in")
    return {"ok": True}


@app.post("/api/logout")
async def logout(response: Response, session: str = Depends(check_auth)):
    _sessions.discard(session)
    response.delete_cookie("session")
    return {"ok": True}


@app.get("/api/me")
async def me(session: str = Depends(check_auth)):
    return {"ok": True}


class ChatRequest(BaseModel):
    message: str


@app.post("/api/chat")
async def chat(req: ChatRequest, session: str = Depends(check_auth)):
    global _loop
    _loop = asyncio.get_event_loop()
    push_log("INFO", f"User: {req.message[:80]}")
    agent = get_agent()

    def on_progress(tool_name: str, result_preview: str = "") -> None:
        push_tool(tool_name, "ok", result_preview)

    loop = asyncio.get_event_loop()
    try:
        reply = await loop.run_in_executor(
            None,
            lambda: agent.run(req.message, emit_progress=on_progress),
        )
        push_log("INFO", f"Agent replied ({len(reply or '')} chars)")

        # Отправить send_message в Telegram, если настроено
        events = getattr(agent, "_last_pending_events", [])
        to_telegram = None
        for evt in events:
            if evt.get("type") == "send_message":
                to_telegram = evt.get("text", "")
                break
        # Fallback: модель не вызвала send_message
        if not to_telegram:
            msg = (req.message or "").lower()
            for prefix in ("отправь в телеграм:", "в телеграм:", "напиши в телеграм:"):
                if prefix in msg:
                    idx = req.message.lower().find(prefix) + len(prefix)
                    to_telegram = req.message[idx:].strip()
                    break
            if not to_telegram and any(p in msg for p in ("отправь", "send", "прямо сейчас")):
                to_telegram = _get_last_telegram_content(DATA_ROOT)
        if to_telegram and TELEGRAM_BOT_TOKEN and TELEGRAM_OWNER_CHAT_ID:
            asyncio.create_task(_send_to_telegram(to_telegram))
        return {"reply": reply or ""}
    except Exception as exc:
        push_log("ERROR", f"Agent error: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/memory")
async def get_memory(session: str = Depends(check_auth)):
    agent = get_agent()
    return {
        "scratchpad": agent.memory.scratchpad or "",
        "identity": agent.memory.identity or "",
    }


@app.post("/api/memory/scratchpad")
async def update_scratchpad(req: Request, session: str = Depends(check_auth)):
    body = await req.json()
    agent = get_agent()
    agent.memory.save_scratchpad(body.get("content", ""))
    push_log("INFO", "Scratchpad updated via web")
    return {"ok": True}


@app.post("/api/memory/identity")
async def update_identity(req: Request, session: str = Depends(check_auth)):
    body = await req.json()
    agent = get_agent()
    agent.memory.save_identity(body.get("content", ""))
    push_log("INFO", "Identity updated via web")
    return {"ok": True}


@app.get("/api/logs")
async def get_logs(session: str = Depends(check_auth)):
    return {"logs": list(_log_buffer)}


@app.get("/api/tools/history")
async def get_tool_history(session: str = Depends(check_auth)):
    return {"events": list(_tool_events)}


@app.get("/api/events")
async def sse_events(session: str | None = Cookie(default=None)):
    if not session or session not in _sessions:
        raise HTTPException(status_code=401)

    queue: asyncio.Queue = asyncio.Queue(maxsize=100)
    _sse_queues.append(queue)

    async def generate() -> AsyncGenerator[str, None]:
        try:
            yield "data: {\"type\":\"connected\"}\n\n"
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30)
                    yield f"data: {json.dumps(event)}\n\n"
                except asyncio.TimeoutError:
                    yield "data: {\"type\":\"ping\"}\n\n"
        finally:
            if queue in _sse_queues:
                _sse_queues.remove(queue)

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.post("/api/voice/transcribe")
async def voice_transcribe(session: str = Depends(check_auth), audio: UploadFile = File(...)):
    import tempfile
    ext = ".webm" if "webm" in (audio.content_type or "") else ".ogg"
    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as f:
        path = f.name
    try:
        content = await audio.read()
        Path(path).write_bytes(content)
        text = transcribe(path)
        return {"text": text}
    finally:
        try:
            os.unlink(path)
        except Exception:
            pass


@app.post("/api/voice/speak")
async def voice_speak(req: Request, session: str = Depends(check_auth)):
    body = await req.json()
    text = (body.get("text") or "").strip()[:500]
    if not text:
        raise HTTPException(status_code=400, detail="text required")
    wav = synthesize(text)
    if not wav:
        raise HTTPException(status_code=500, detail="TTS failed")
    return Response(content=wav, media_type="audio/wav")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


if __name__ == "__main__":
    import uvicorn
    push_log("INFO", "VOR Web Server starting...")
    uvicorn.run(app, host="0.0.0.0", port=WEB_PORT, log_level="warning")
