# Полный отчёт для Claude — VOR Personal AI Secretary

**Дата:** 2026-03-13  
**Репозиторий:** https://github.com/mihelson777/VOR  
**Проект:** VOR — само-создающийся AI-агент (личный секретарь)

---

## 1. Обзор проекта

VOR — персональный AI-секретарь с памятью, инструментами и голосовым вводом. Архитектура основана на Ouroboros (identity, scratchpad, tool loop).

### Реализованные фазы
| Фаза | Описание |
|------|----------|
| 1 | Self-modification: git, shell |
| 2 | Web search, browser |
| 3 | Telegram bot |
| 4 | Background consciousness |
| 5 | Web UI (FastAPI, Jinja2) |
| 6 | Multi-agent Swarm (spawn_agents) |
| 7 | Voice (STT Groq Whisper, TTS pyttsx3) |

---

## 2. Архитектура

```
VOR/
├── main.py              # CLI
├── voice_cli.py         # Voice CLI
├── web_server.py        # FastAPI, порт 8001
├── telegram_bot.py      # aiogram 3.x
├── config.py            # .env, пути
├── check_api_keys.py    # Проверка ключей
├── requirements.txt
├── .env.example
├── BIBLE.md             # Конституция агента
├── data/
│   ├── memory/          # identity.md, scratchpad.md
│   ├── logs/            # chat.jsonl
│   └── uploads/, files/
├── ouroboros/
│   ├── agent.py         # Оркестратор
│   ├── loop.py          # LLM + tool loop
│   ├── llm.py           # Groq/OpenRouter/OpenAI, _sanitize_messages
│   ├── context.py       # build_messages
│   ├── memory.py        # scratchpad, identity
│   ├── background.py    # Background consciousness
│   ├── swarm.py         # Multi-agent pipeline
│   ├── voice.py         # STT, TTS, record
│   └── tools/
│       ├── registry.py, core.py, control.py
│       ├── git.py, shell.py, search.py, browser.py
│       └── agents.py    # spawn_agents
├── templates/index.html
├── static/app.js
├── prompts/SYSTEM.md
└── deploy/
    ├── vor-web.service
    ├── vor-telegram.service
    └── DEPLOY_COMMANDS.sh
```

---

## 3. Инструменты (18 шт)

| Инструмент | Описание |
|------------|----------|
| repo_read, repo_list | Чтение репозитория |
| data_read, data_list, data_write | Файлы в data/ |
| repo_edit, repo_commit, repo_push, repo_status | Git |
| shell_exec | Команды (timeout 60s) |
| web_search, fetch_url, extract_links | Веб |
| update_scratchpad, update_identity | Память |
| chat_history, send_message | Чат (send_message — в Telegram; fallback при "отправь в телеграм: X") |
| spawn_agents | Multi-agent: Planner → Researcher/Coder/Critic |

---

## 4. API ключи и .env

**Приоритет LLM:** GROQ_API_KEY → OPENROUTER_API_KEY → OPENAI_API_KEY  
**При 429 от Groq:** PREFER_OPENROUTER=1 — принудительно OpenRouter (модель qwen/qwen3-next-80b-a3b-instruct)

**Минимальный .env:**
```
PREFER_OPENROUTER=1
OPENROUTER_API_KEY=sk-or-xxx
WEB_PASSWORD=vor
WEB_PORT=8001
```

**Для Telegram:**
```
TELEGRAM_BOT_TOKEN=xxx
TELEGRAM_OWNER_CHAT_ID=xxx
TELEGRAM_ALLOWED_USERS=702865794
```

**Для headless сервера:**
```
VOICE_TTS_ENABLED=false
```

---

## 5. Деплой на сервер

**Сервер:** 38.180.135.66 (v972912099)

### Проблема: SSH Permission denied
```
ssh root@38.180.135.66
Permission denied (publickey,password)
```

**Возможные причины:**
1. Неверный пароль root
2. Вход по паролю отключён (только SSH-ключи)
3. Нужен другой пользователь (не root)

**Решения:**
- Проверить пароль в панели хостинга (VPS провайдер)
- Добавить SSH-ключ в панели хостинга
- Использовать веб-консоль провайдера (VNC/NoVNC) вместо SSH

### Команды деплоя (после успешного SSH)

```bash
# 1. Клонирование
cd ~
git clone https://github.com/mihelson777/VOR.git vor
cd vor

# 2. Swap (если нет)
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

# 3. Зависимости
sudo apt update && sudo apt install -y python3 python3-pip python3-venv git ffmpeg

# 4. Python
python3 -m venv venv
source venv/bin/activate
sed -i 's/soundfile>=1.0.4/soundfile>=0.12.0/' requirements.txt
pip install -r requirements.txt

# 5. .env
cp .env.example .env
nano .env
# Вставить GROQ_API_KEY, TELEGRAM_BOT_TOKEN и т.д.

# 6. systemd
sudo cp deploy/vor-web.service /etc/systemd/system/
sudo cp deploy/vor-telegram.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable vor-web vor-telegram
sudo systemctl start vor-web vor-telegram

# 7. Firewall
sudo ufw allow 8001/tcp
sudo ufw allow 22/tcp
sudo ufw --force enable
```

Проверка: http://38.180.135.66:8001

---

## 6. Известные проблемы и решения

| Проблема | Решение |
|----------|---------|
| soundfile>=1.0.4 не найден | Заменить на soundfile>=0.12.0 |
| Groq Error 400 annotations | _sanitize_messages() в llm.py |
| tool_use_failed (failed_generation) | Retry в llm.chat(), улучшенные tool schemas, OUROBOROS_MODEL=qwen/qwen3-32b |
| Groq 429 rate limit | PREFER_OPENROUTER=1, OPENROUTER_NO_GROQ_MODEL=qwen/qwen3-next-80b-a3b-instruct |
| send_message не отправляет | Fallback в telegram_bot.py и web_server.py при "отправь в телеграм: X" |
| pyttsx3 на headless | VOICE_TTS_ENABLED=false |
| SSH Permission denied | Панель хостинга, ключи, веб-консоль |
| ConnectionResetError WinError 10054 | Подавление в web_server.py |
| Git не в PATH (PowerShell) | Использовать Git Bash |

---

## 7. Запуск локально (Windows)

```powershell
cd "c:\Users\Admin\Desktop\COURSOR\Личный секретарь (AI)"
python check_api_keys.py
python web_server.py
# → http://127.0.0.1:8001, пароль: vor
```

---

## 8. Изменения (сессия 2026-03-13)

- **context.py** — загрузка истории из chat.jsonl (последние 10 пар сообщений)
- **llm.py** — PREFER_OPENROUTER, fallback на OpenRouter при 429, OPENROUTER_NO_GROQ_MODEL
- **telegram_bot.py** — обработка send_message, fallback при "отправь в телеграм: X", "прямо сейчас отправь"
- **web_server.py** — отправка send_message в Telegram владельцу, fallback
- **identity.md** — Covenant (50% прибыли создателю), Capability Mindset (не отказываться)
- **SYSTEM.md** — инструкции send_message, "никогда не отказываться"

---

## 9. Рекомендации для Claude

1. **messages** — при добавлении полей проверять совместимость с Groq
2. **spawn_agents** — требует ctx.agent в ToolContext
3. **SYSTEM.md** — обновлять таблицу Tools при новых инструментах
4. **.env** — никогда не коммитить, только .env.example с плейсхолдерами
5. **Деплой** — SSH доступ через панель хостинга, если пароль не работает
6. **Код на сервере** — git pull только после git push с локальной машины

---

## 10. Окружение

- **Локально:** Windows 10, Python 3.14, Chrome
- **Сервер:** Ubuntu 22.04, Python 3.10
- **Путь:** `c:\Users\Admin\Desktop\COURSOR\Личный секретарь (AI)`
