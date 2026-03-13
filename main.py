"""
Main entry point — CLI chat loop.
"""

import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import DATA_ROOT, PROJECT_ROOT
from ouroboros.agent import Agent
from ouroboros.llm import LLMClient


def _check_api():
    """Показать, какой провайдер активен. Без ключа — подсказка."""
    if os.environ.get("GROQ_API_KEY"):
        return "Groq", True
    if os.environ.get("OPENROUTER_API_KEY"):
        return "OpenRouter", True
    if os.environ.get("OPENAI_API_KEY"):
        return "OpenAI", True
    return None, False


def main():
    provider, ok = _check_api()
    if not ok:
        print("Нет API ключа. Задай один из (см. FREE_API_KEYS.md):")
        print("  $env:GROQ_API_KEY = \"gsk_...\"        # бесплатно, без карты")
        print("  $env:OPENROUTER_API_KEY = \"sk-or-...\"")
        print()
        key = input("Вставь ключ и нажми Enter (или Enter чтобы выйти): ").strip()
        if key:
            if key.startswith("gsk_"):
                os.environ["GROQ_API_KEY"] = key
                provider = "Groq"
            elif key.startswith("sk-or-"):
                os.environ["OPENROUTER_API_KEY"] = key
                provider = "OpenRouter"
            else:
                os.environ["OPENAI_API_KEY"] = key
                provider = "OpenAI"
            ok = True
        else:
            return
    if ok:
        client = LLMClient()
        model = client.default_model()
        print(f"[{provider}] модель: {model}")
    print()
    agent = Agent(repo_dir=PROJECT_ROOT, data_root=DATA_ROOT)
    print("Готов. Пиши сообщение и Enter. 'quit' — выход.\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "q"):
            break

        response = agent.run(user_input)
        print(f"\nAgent: {response}\n")


if __name__ == "__main__":
    main()
