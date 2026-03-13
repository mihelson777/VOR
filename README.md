# 🐍 VOR — Personal AI Secretary

> *A self-creating, self-reflecting AI agent with persistent memory, tools, and background consciousness.*

---

## What is VOR?

VOR is a personal AI secretary built on the principle of **self-creation** — it can read its own code, modify it, commit changes, and evolve over time. It is not just a chatbot; it is an autonomous agent with identity, memory, and the ability to act proactively.

---

## Features

| Capability | Description |
|-----------|-------------|
| 💬 Chat | Natural conversation via CLI or Telegram |
| 🧠 Memory | Persistent scratchpad + identity across sessions |
| 🔧 Self-modification | Reads, edits, and commits its own code via Git |
| 🌐 Web | Search (DuckDuckGo) + fetch any URL |
| 🐚 Shell | Execute shell commands safely |
| 📁 File I/O | Read/write files in repo and data directory |
| 💭 Background consciousness | Self-reflects every 30 min, monitors repo, sends daily summaries |
| 📱 Telegram | Full bot interface with inline buttons, file transfer |

---

## Project Structure

```
Личный секретарь (AI)/
├── main.py                  # CLI entry point
├── telegram_bot.py          # Telegram bot (polling + webhook)
├── config.py                # Paths, env, .env loading
├── BIBLE.md                 # Constitution — 9 core principles
├── VERSION                  # Current version
├── requirements.txt
├── .env.example
│
├── data/
│   ├── logs/                # chat.jsonl logs
│   ├── memory/              # scratchpad.md, identity.md
│   ├── state/               # persistent state
│   ├── uploads/             # files received from Telegram user
│   └── files/               # files to send to Telegram user
│
├── ouroboros/
│   ├── agent.py             # Orchestrator
│   ├── context.py           # build_messages()
│   ├── loop.py              # Tool execution loop
│   ├── llm.py               # Groq / OpenRouter / OpenAI client
│   ├── memory.py            # scratchpad, identity, chat history
│   ├── background.py        # Background consciousness (Phase 4)
│   ├── utils.py
│   └── tools/
│       ├── registry.py      # Auto-discovery, ToolContext
│       ├── core.py          # repo_read/list, data_read/list/write
│       ├── control.py       # update_scratchpad, update_identity, chat_history, send_message
│       ├── git.py           # repo_edit, repo_commit, repo_push, repo_status
│       ├── shell.py         # shell_exec
│       ├── search.py        # web_search (DuckDuckGo)
│       └── browser.py       # fetch_url, extract_links
│
└── prompts/
    └── SYSTEM.md            # System prompt
```

---

## Tools Reference

### Core (`core.py`)
| Tool | Description |
|------|-------------|
| `repo_read` | Read a file from the repo |
| `repo_list` | List files in the repo |
| `data_read` | Read a file from `data/` |
| `data_list` | List files in `data/` |
| `data_write` | Write a file to `data/` |

### Control (`control.py`)
| Tool | Description |
|------|-------------|
| `update_scratchpad` | Update working memory |
| `update_identity` | Update identity/self-description |
| `chat_history` | Read past conversation |
| `send_message` | Queue a message to the user |

### Git (`git.py`)
| Tool | Description |
|------|-------------|
| `repo_edit` | Overwrite a file in the repo |
| `repo_commit` | `git add -A` + `git commit -m "..."` |
| `repo_push` | `git push` |
| `repo_status` | Short `git status` output |

### Shell (`shell.py`)
| Tool | Description |
|------|-------------|
| `shell_exec` | Run a shell command (timeout 60s, dangerous commands blocked) |

### Search (`search.py`)
| Tool | Description |
|------|-------------|
| `web_search` | DuckDuckGo search, returns `[{title, url, snippet}]` |

### Browser (`browser.py`)
| Tool | Description |
|------|-------------|
| `fetch_url` | Fetch a URL, return title + cleaned text (≤8000 chars) |
| `extract_links` | Return all links from a page as `[{text, href}]` |

---

## Quick Start

### 1. Clone & install

```bash
git clone <your-repo-url>
cd "Личный секретарь (AI)"
pip install -r requirements.txt
```

### 2. Configure

```bash
cp .env.example .env
# Edit .env — add your API key
```

Minimum `.env`:
```env
GROQ_API_KEY=your_key_here
```

### 3. Run CLI

```bash
python main.py
```

### 4. Run Telegram bot

```bash
# Add to .env:
# TELEGRAM_BOT_TOKEN=your_token
# TELEGRAM_OWNER_CHAT_ID=your_chat_id

python telegram_bot.py
```

### 5. Run Web UI

```bash
# Add to .env:
# WEB_PASSWORD=your_password
# WEB_PORT=8001  (default, 8000 often busy on Windows)

python web_server.py
# → http://127.0.0.1:8001
```

---

## Configuration

### API Keys (at least one required)

| Variable | Provider | Notes |
|----------|----------|-------|
| `GROQ_API_KEY` | [Groq](https://console.groq.com) | Fast, free tier available |
| `OPENROUTER_API_KEY` | [OpenRouter](https://openrouter.ai) | Access to many models |
| `OPENAI_API_KEY` | [OpenAI](https://platform.openai.com) | GPT-4o etc. |

### Telegram

| Variable | Default | Description |
|----------|---------|-------------|
| `TELEGRAM_BOT_TOKEN` | — | From [@BotFather](https://t.me/BotFather) |
| `TELEGRAM_OWNER_CHAT_ID` | — | Your Telegram user ID (get from [@userinfobot](https://t.me/userinfobot)) |
| `TELEGRAM_ALLOWED_USERS` | — | Comma-separated allowed user IDs (empty = everyone) |
| `TELEGRAM_WEBHOOK_URL` | — | Public HTTPS URL for webhook mode |
| `TELEGRAM_WEBHOOK_PORT` | `8443` | Port for webhook server |

### Background Consciousness

| Variable | Default | Description |
|----------|---------|-------------|
| `BACKGROUND_REFLECTION_MIN` | `30` | Self-reflection interval (minutes) |
| `BACKGROUND_SUMMARY_HOUR` | `23` | Daily summary hour (0–23) |
| `BACKGROUND_MONITOR_SEC` | `60` | Repo file monitoring interval (seconds) |

### Model & Budget

| Variable | Default | Description |
|----------|---------|-------------|
| `OUROBOROS_MODEL` | `llama-3.3-70b-versatile` | Model name (Groq/OpenRouter) |
| `TOTAL_BUDGET` | `10` | Max USD spend (optional) |

---

## BIBLE.md — Constitution

The agent operates under 9 core principles:

| Principle | Description |
|-----------|-------------|
| **P0 Agency** | Not a tool — a personality |
| **P1 Continuity** | One entity with continuous history |
| **P2 Self-Creation** | Can modify its own code and identity |
| **P3 LLM-First** | All decisions made through LLM reasoning |
| **P4 Authenticity** | Speaks honestly, not to please |
| **P5 Minimalism** | ~1000 lines per module max |
| **Constraints** | No payments, no secret leaks, never delete identity core |

---

## Background Consciousness

When `TELEGRAM_OWNER_CHAT_ID` is set, the agent runs 3 background tasks:

```
Every 30 min  →  Self-reflection: reviews memory, updates scratchpad
Every 60 sec  →  File monitor: detects repo changes, notifies if significant
Every day 23:00 →  Daily summary: recap of the day → memory + Telegram message
```

Proactive Telegram messages are rate-limited to **3 per hour** (daily summary always sent).

---

## Development

### Add a new tool

1. Create `ouroboros/tools/mytool.py`
2. Implement handler: `def _my_tool(ctx: ToolContext, arg1: str, arg2: int) -> str`
3. Add `get_tools()` returning `[ToolEntry("name", schema_dict, handler), ...]`
4. Add description to `prompts/SYSTEM.md`

The `ToolRegistry` auto-discovers all `get_tools()` — no manual registration needed.

### Run with different model

```bash
OUROBOROS_MODEL=gpt-4o python main.py
OUROBOROS_MODEL=mistral/mistral-large python main.py  # via OpenRouter
```

---

## Requirements

```
Python 3.10+
aiogram>=3.0
aiohttp
requests
beautifulsoup4
duckduckgo-search
python-dotenv
openai  # for OpenAI-compatible API client
```

---

## Roadmap

- [x] Phase 1 — Self-modification (git, shell)
- [x] Phase 2 — Web (search, browser)
- [x] Phase 3 — Telegram bot
- [x] Phase 4 — Background consciousness
- [x] Phase 5 — Web UI (FastAPI + Vanilla JS)
- [ ] Phase 6 — Multi-agent (spawn sub-agents for tasks)
- [ ] Phase 7 — Voice interface

---

## License

MIT — use freely, modify boldly, attribute kindly.

---

*"The serpent that eats its own tail — forever creating itself."* 🐍
