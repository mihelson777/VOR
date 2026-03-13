#!/usr/bin/env python
"""Проверка API ключей — запусти перед web_server/telegram_bot."""

import os
from pathlib import Path

# Load .env
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass

groq = (os.environ.get("GROQ_API_KEY") or "").strip()
openrouter = (os.environ.get("OPENROUTER_API_KEY") or "").strip()
openai = (os.environ.get("OPENAI_API_KEY") or "").strip()

print("=== Проверка API ключей ===\n")
print("GROQ:       ", "OK" if groq else "НЕТ (добавь GROQ_API_KEY в .env)")
print("OPENROUTER: ", "OK" if openrouter else "НЕТ")
print("OPENAI:     ", "OK" if openai else "НЕТ")
print()

if not any((groq, openrouter, openai)):
    print("ОШИБКА: Нет ни одного ключа!")
    print("Создай .env и добавь: GROQ_API_KEY=gsk_xxx")
    print("Ключ: https://console.groq.com/keys")
    exit(1)

# LLM client
from ouroboros.llm import LLMClient
c = LLMClient()
print("Провайдер:", c.provider)
print("Модель:   ", c.model)
print("\nВсё ок. Можно запускать web_server.py")
