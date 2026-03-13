# Отчёт для Claude — VOR Personal AI Secretary

**Дата:** 2026-03-13  
**Проект:** VOR — само-создающийся AI-агент (личный секретарь)

---

## Текущее состояние

### Работает
- ✅ Web UI (http://127.0.0.1:8001) — логин, чат, Memory, Logs, Tools, 🎤 голос
- ✅ Telegram bot (polling + webhook) — голосовые сообщения
- ✅ API ключи: Groq (приоритет 1), OpenRouter (2), OpenAI (3)
- ✅ Multi-agent Swarm: `spawn_agents` → Planner → Researcher/Coder/Critic → синтез
- ✅ Инструменты: repo_*, data_*, web_search, fetch_url, shell_exec, git, spawn_agents, send_message

### Решённые проблемы
- Кнопка AUTHENTICATE — HTML вынесен в `templates/index.html` (Jinja2)
- Error 401 — добавлена загрузка `.env` в llm.py, проверка `check_api_keys.py`
- Error 400 `annotations unsupported` — `_sanitize_messages()` в llm.py убирает неподдерживаемые поля для Groq
- ConnectionResetError WinError 10054 — подавление в `_suppress_connection_reset` (web_server.py)
- Брендинг: Ouroboros → VOR везде (UI, identity, BIBLE, README)

---

## Архитектура

```
VOR Agent
├── ouroboros/
│   ├── agent.py       # Оркестратор, run() → loop
│   ├── loop.py        # LLM + tool calls (ReAct)
│   ├── llm.py         # Groq/OpenRouter/OpenAI, _sanitize_messages
│   ├── context.py     # build_messages (identity, scratchpad)
│   ├── memory.py      # scratchpad, identity, chat_history
│   ├── swarm.py       # Multi-agent: Planner → Researcher/Coder/Critic
│   └── tools/
│       ├── registry.py    # ToolContext, ToolRegistry
│       ├── core.py        # repo_read/list, data_read/list/write
│       ├── control.py    # update_scratchpad, update_identity, send_message
│       ├── git.py        # repo_edit, commit, push, status
│       ├── shell.py      # shell_exec
│       ├── search.py     # web_search
│       ├── browser.py    # fetch_url, extract_links
│       └── agents.py     # spawn_agents
├── web_server.py     # FastAPI, порт 8001
├── telegram_bot.py   # aiogram 3.x
├── config.py         # .env, пути, ключи
└── prompts/
    └── SYSTEM.md     # Системный промпт
```

---

## Ключевые файлы

| Файл | Назначение |
|------|------------|
| `config.py` | Загрузка .env, DATA_ROOT, ключи, WEB_PASSWORD |
| `ouroboros/llm.py` | LLMClient, _sanitize_messages, provider/model |
| `ouroboros/loop.py` | run_loop — chat + tool execution |
| `ouroboros/agent.py` | Agent.run(), ToolContext(agent=self) |
| `ouroboros/swarm.py` | Swarm.run(), SubTask, format_swarm_result |
| `ouroboros/tools/agents.py` | spawn_agents → Swarm |
| `web_server.py` | FastAPI, /api/chat, /api/voice/transcribe, /api/voice/speak, SSE |
| `templates/index.html` | Jinja2, UI VOR |
| `static/app.js` | Клиентский JS, tryLogin, sendMessage |
| `data/memory/identity.md` | Идентичность VOR |
| `BIBLE.md` | Конституция агента |

---

## API ключи

**Приоритет:** GROQ_API_KEY → OPENROUTER_API_KEY → OPENAI_API_KEY

```powershell
# Проверка
python check_api_keys.py
```

**.env:**
```
GROQ_API_KEY=gsk_xxx
OPENROUTER_API_KEY=sk-or-xxx   # опционально
WEB_PASSWORD=vor
```

---

## Инструменты (18 шт)

| Инструмент | Описание |
|------------|----------|
| repo_read, repo_list | Чтение файлов репозитория |
| data_read, data_list, data_write | Файлы в data/ |
| repo_edit, repo_commit, repo_push, repo_status | Git |
| shell_exec | Выполнение команд (timeout 60s) |
| web_search, fetch_url, extract_links | Веб |
| update_scratchpad, update_identity | Память |
| chat_history, send_message | Чат |
| **spawn_agents** | Multi-agent pipeline для сложных задач |

**Voice (Phase 7):** STT Groq Whisper, TTS pyttsx3, `voice_cli.py`, Web 🎤, Telegram voice

---

## Быстрая проверка

```powershell
cd "c:\Users\Admin\Desktop\COURSOR\Личный секретарь (AI)"

# Ключи
python check_api_keys.py

# Web
python web_server.py
# → http://127.0.0.1:8001, пароль: vor

# Telegram
python telegram_bot.py
```

---

## Известные нюансы

1. **Groq** — не поддерживает `annotations` в assistant messages → _sanitize_messages
2. **Windows** — ConnectionResetError при закрытии вкладки SSE → подавление в exception handler
3. **Папка ouroboros/** — имя пакета не меняли (рефакторинг импортов)
4. **Порт 8001** — 8000 часто занят на Windows

---

## Рекомендации для Claude

1. При добавлении новых полей в messages — проверять совместимость с Groq
2. spawn_agents требует ctx.agent — ToolContext создаётся в agent.run()
3. SYSTEM.md — добавить описание новых инструментов в таблицу Tools
4. .env не коммитить — в .gitignore

---

## Окружение

- **OS:** Windows 10
- **Python:** 3.14
- **Браузер:** Chrome
- **Путь:** `c:\Users\Admin\Desktop\COURSOR\Личный секретарь (AI)`
