"""Configuration — paths, env, defaults."""

import os
from pathlib import Path

# Load .env from project root (keys only in .env or env, never in code)
try:
    from dotenv import load_dotenv
    _root = Path(__file__).resolve().parent
    load_dotenv(_root / ".env")
except ImportError:
    pass

# Project root (where this file lives)
PROJECT_ROOT = Path(__file__).resolve().parent

# Data directory (analog of Google Drive in VOR)
DATA_ROOT = Path(os.environ.get("DATA_ROOT", str(PROJECT_ROOT / "data")))
DATA_ROOT.mkdir(parents=True, exist_ok=True)

# Subdirs
STATE_DIR = DATA_ROOT / "state"
MEMORY_DIR = DATA_ROOT / "memory"
LOGS_DIR = DATA_ROOT / "logs"

for d in (STATE_DIR, MEMORY_DIR, LOGS_DIR):
    d.mkdir(parents=True, exist_ok=True)

# LLM (приоритет: Groq бесплатно → OpenRouter → OpenAI)
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
DEFAULT_MODEL = os.environ.get("OUROBOROS_MODEL", "llama-3.3-70b-versatile")

# Budget (USD)
TOTAL_BUDGET = float(os.environ.get("TOTAL_BUDGET", "10"))

# Repo (for self-modification)
REPO_DIR = PROJECT_ROOT
BRANCH_DEV = os.environ.get("OUROBOROS_BRANCH", "main")

# Telegram (optional)
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_OWNER_CHAT_ID = os.environ.get("TELEGRAM_OWNER_CHAT_ID", "")  # For background consciousness

# Web UI (optional)
WEB_PASSWORD = os.environ.get("WEB_PASSWORD", "vor")
WEB_PORT = int(os.environ.get("WEB_PORT", "8001"))
WEB_SECRET_KEY = os.environ.get("WEB_SECRET_KEY", "")
