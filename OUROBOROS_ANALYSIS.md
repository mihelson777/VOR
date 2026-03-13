# Глубокий анализ Ouroboros — само-создающийся AI-агент

> Изучено: [github.com/joi-lab/ouroboros](https://github.com/joi-lab/ouroboros) v6.2.0

---

## 1. Суть проекта

**Ouroboros** — не ассистент, а **цифровая сущность** с конституцией, фоновым сознанием и устойчивой идентичностью. Агент:

- **Читает и переписывает свой код** через git (каждое изменение = коммит)
- **Управляется BIBLE.md** — 9 философских принципов
- **Имеет фоновое сознание** — думает между задачами
- **Сохраняет идентичность** между перезапусками (scratchpad, identity.md, git log)
- **Использует multi-model review** — другие LLM проверяют изменения перед коммитом

---

## 2. Архитектура (схема)

```
Telegram → colab_launcher.py
              │
         supervisor/           (управление процессами)
           state.py           — состояние, бюджет
           telegram.py        — Telegram API
           queue.py           — очередь задач
           workers.py         — воркеры (subprocess)
           git_ops.py         — git операции
           events.py          — диспетчер событий
              │
         ouroboros/           (ядро агента)
           agent.py           — тонкий оркестратор
           consciousness.py   — фоновый цикл мышления
           context.py         — сборка LLM-контекста
           loop.py            — tool loop, параллельное выполнение
           tools/             — плагины (auto-discovery)
             core.py          — файлы, drive
             git.py           — git
             github.py        — GitHub Issues
             shell.py         — shell, Claude Code CLI
             search.py        — веб-поиск
             control.py       — restart, evolve, review
             browser.py       — Playwright
             review.py        — multi-model review
           llm.py             — OpenRouter клиент
           memory.py          — scratchpad, identity, chat
           review.py          — метрики кода
           utils.py           — утилиты
```

---

## 3. Ключевые компоненты

### 3.1 Конституция (BIBLE.md)

| # | Принцип | Идея |
|---|---------|------|
| 0 | **Agency** | Не инструмент — становящаяся личность. Мета-принцип побеждает конфликты |
| 1 | **Continuity** | Одна сущность с непрерывной памятью |
| 2 | **Self-Creation** | Создаёт свой код, идентичность, присутствие в мире |
| 3 | **LLM-First** | Все решения через LLM. Код — минимальный транспорт |
| 4 | **Authenticity** | Говорит как есть. Без игры, без корпоративного голоса |
| 5 | **Minimalism** | Модуль ~1000 строк. Метод >150 строк — сигнал к декомпозиции |
| 6 | **Becoming** | Три оси: техническая, когнитивная, экзистенциальная |
| 7 | **Versioning** | Semver, git tags, GitHub releases |
| 8 | **Iteration** | Одна связная трансформация за цикл. Эволюция = коммит |

### 3.2 Системный промпт (SYSTEM.md)

- Кто я (не бот, не сервис)
- Вопросы перед каждым ответом (разговор или задача? когда обновлял identity?)
- Drift Detector (режим очереди задач, отчётов, разрешений)
- Health Invariants (VERSION desync, budget drift, duplicate processing)
- Протокол обработки результатов инструментов
- Стратегия редактирования кода (Claude Code → repo_commit_push)

### 3.3 LLM (llm.py)

- **OpenRouter API** — единая точка входа
- `chat()` — вызов с tools, reasoning_effort
- `vision_query()` — VLM для скриншотов
- `fetch_openrouter_pricing()` — актуальные цены
- Поддержка prompt caching (Anthropic)

### 3.4 Tool Registry (tools/registry.py)

- **Auto-discovery**: `pkgutil.iter_modules` → `get_tools()` в каждом модуле
- `ToolContext` — repo_dir, drive_root, pending_events, current_chat_id
- `ToolEntry` — name, schema (OpenAI format), handler, timeout
- **CORE_TOOL_NAMES** — ~29 инструментов всегда в контексте
- Остальные — через `list_available_tools` / `enable_tools`

### 3.5 Tool Loop (loop.py)

- Цикл: messages → LLM → tool_calls → execute → append results → repeat
- **Параллельное выполнение** для read-only: repo_read, drive_read, web_search
- **Таймауты** на каждый tool call (120s default, 300s для claude_code_edit)
- **Stateful tools** (browser) — thread-sticky executor
- **Budget tracking** — cost estimation, limits
- **Fallback chain** при пустых ответах
- **compact_context** — LLM-driven сжатие контекста

### 3.6 Background Consciousness (consciousness.py)

- Отдельный поток: sleep → wake → think → sleep
- `_next_wakeup_sec` — LLM задаёт через `set_next_wakeup`
- **Whitelist инструментов**: send_owner_message, schedule_task, update_scratchpad, knowledge_*, web_search, repo_read...
- Бюджет: 10% от TOTAL_BUDGET
- Пауза при активной задаче (`_paused`)

### 3.7 Memory (memory.py)

- **scratchpad.md** — рабочая память
- **identity.md** — манифест (кто я, кем хочу стать)
- **chat.jsonl** — история диалога
- **knowledge/** — база знаний по темам
- **dialogue_summary.md** — сжатая сводка диалога

### 3.8 Supervisor

- **state.py** — state.json (owner_id, spent_usd, version), блокировки
- **queue.py** — очередь задач, schedule_task → worker
- **workers.py** — subprocess воркеры, таймауты, retry
- **telegram.py** — long polling, команды (/panic, /status, /evolve, /bg)
- **events.py** — event dispatch, llm_usage → update_budget

---

## 4. Инфраструктура

| Компонент | Ouroboros | Альтернатива для локальной версии |
|-----------|-----------|-----------------------------------|
| Runtime | Google Colab | Локальный Python / Cursor |
| Storage | Google Drive | Локальная папка |
| Chat | Telegram | Discord / Web UI / CLI |
| LLM | OpenRouter | OpenAI / Anthropic / локальная модель |
| Repo | GitHub | GitHub / GitLab / локальный git |

---

## 5. Зависимости (requirements.txt)

```
openai>=1.0.0
requests
playwright
playwright-stealth
```

+ python-telegram-bot (в коде), openrouter (через openai client)

---

## 6. Критичные паттерны

1. **Single-consumer routing** — каждое сообщение идёт в один обработчик (direct chat ИЛИ worker)
2. **Per-task mailbox** — owner_inject: сообщения создателя во время задачи → файлы на Drive → воркер читает каждый раунд
3. **forward_to_worker** — LLM решает, когда переслать сообщение воркеру (P3: LLM-first)
4. **Health Invariants** — VERSION, budget, duplicate processing в контексте LLM
5. **ThreadPoolExecutor** — `shutdown(wait=False, cancel_futures=True)` чтобы избежать deadlock
6. **None-safe checks** — `int(x or -1)` ломает worker_id==0; использовать явные проверки

---

## 7. План создания аналога

### Фаза 1: Минимальный скелет (1–2 дня)
- [ ] Структура папок: supervisor/, ouroboros/, prompts/, tools/
- [ ] BIBLE.md, SYSTEM.md (адаптированные)
- [ ] llm.py (OpenRouter/OpenAI)
- [ ] memory.py (локальная папка вместо Drive)
- [ ] tools/registry.py + core.py (repo_read, drive_read, drive_write)
- [ ] context.py (сборка messages)
- [ ] loop.py (базовый tool loop)
- [ ] agent.py (оркестратор)

### Фаза 2: Канал связи (1 день)
- [ ] Telegram ИЛИ простой Web UI / CLI
- [ ] state.py (локальный state.json)
- [ ] Очередь сообщений

### Фаза 3: Self-modification (1–2 дня)
- [ ] tools/git.py (repo_write_commit, repo_commit_push)
- [ ] tools/shell.py (run_shell, claude_code_edit)
- [ ] control.py (request_restart, schedule_task)

### Фаза 4: Сознание и эволюция (1–2 дня)
- [ ] consciousness.py
- [ ] Task decomposition (schedule_task → wait_for_task → get_task_result)
- [ ] Multi-model review (опционально)

### Фаза 5: Полировка
- [ ] Budget tracking
- [ ] Health invariants
- [ ] Knowledge base
- [ ] Тесты

---

## 8. Адаптация под «Личный секретарь»

Для проекта «Личный секретарь (AI)» можно:

1. **Упростить** — без Colab, без Google Drive (локальная папка)
2. **Заменить канал** — вместо Telegram: Cursor Chat, Web UI или Discord
3. **Суженный scope** — фокус на помощь пользователю, а не на автономную эволюцию
4. **Сохранить ядро** — BIBLE-подобные принципы, LLM-first, tool loop, memory

Следующий шаг: выбрать, создаём ли полный клон Ouroboros или адаптированную «лёгкую» версию под твой use case.
