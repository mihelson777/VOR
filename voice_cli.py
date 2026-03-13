#!/usr/bin/env python
"""
Voice CLI — говори с VOR голосом.

Press Enter → запись 4 сек → транскрипция → ответ агента → озвучка.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import DATA_ROOT, PROJECT_ROOT
from ouroboros.agent import Agent
from ouroboros.voice import is_available, record_and_transcribe, speak


def main():
    avail = is_available()
    print("Voice components:", avail)
    if not all(avail.values()):
        print("Missing: pip install pyttsx3 sounddevice soundfile numpy")
        if not avail["stt_groq"]:
            print("  + GROQ_API_KEY in .env")
        return

    agent = Agent(repo_dir=PROJECT_ROOT, data_root=DATA_ROOT)
    print("\nVOR Voice CLI. Press Enter to speak (4 sec), Ctrl+C to exit.\n")

    while True:
        try:
            input("Press Enter to speak... ")
        except (EOFError, KeyboardInterrupt):
            break

        print("Recording 4 sec...")
        text = record_and_transcribe(seconds=4)
        print(f"Heard: {text}")

        if not text or text.startswith("ERROR"):
            speak("I didn't catch that. Try again.")
            continue

        print("Thinking...")
        reply = agent.run(text)
        print(f"VOR: {reply[:200]}...")

        speak(reply[:500])


if __name__ == "__main__":
    main()
