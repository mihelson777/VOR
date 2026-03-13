"""
ouroboros/voice.py — Voice I/O for VOR.

STT: Groq Whisper (speech-to-text)
TTS: pyttsx3 (text-to-speech, offline)
Recording: sounddevice + soundfile
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Optional

# Load .env
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

GROQ_KEY = (os.environ.get("GROQ_API_KEY") or "").strip()
VOICE_SPEED = int(os.environ.get("VOICE_SPEED", "180"))
VOICE_VOLUME = float(os.environ.get("VOICE_VOLUME", "1.0"))
VOICE_TTS_ENABLED = os.environ.get("VOICE_TTS_ENABLED", "true").lower() in ("1", "true", "yes")


def is_available() -> dict:
    """Check availability of voice components."""
    result = {"stt_groq": False, "tts_pyttsx3": False, "recording": False}
    if GROQ_KEY:
        result["stt_groq"] = True
    if VOICE_TTS_ENABLED:
        try:
            import pyttsx3
            result["tts_pyttsx3"] = True
        except Exception:
            pass
    try:
        import sounddevice
        import soundfile
        result["recording"] = True
    except Exception:
        pass
    return result


def transcribe(audio_path: str | Path) -> str:
    """Transcribe audio file to text via Groq Whisper."""
    if not GROQ_KEY:
        return "ERROR: GROQ_API_KEY not set"
    try:
        from openai import OpenAI
        client = OpenAI(api_key=GROQ_KEY, base_url="https://api.groq.com/openai/v1")
        with open(audio_path, "rb") as f:
            resp = client.audio.transcriptions.create(
                model="whisper-large-v3-turbo",
                file=f,
            )
        return (resp.text or "").strip()
    except Exception as e:
        return f"Transcription error: {e}"


def speak(text: str, speed: Optional[int] = None, volume: Optional[float] = None) -> None:
    """Speak text via pyttsx3 (blocks until done). No-op if VOICE_TTS_ENABLED=false (headless)."""
    if not VOICE_TTS_ENABLED:
        return
    try:
        import pyttsx3
        engine = pyttsx3.init()
        engine.setProperty("rate", speed or VOICE_SPEED)
        engine.setProperty("volume", volume if volume is not None else VOICE_VOLUME)
        engine.say(text)
        engine.runAndWait()
        engine.stop()
    except Exception as e:
        print(f"TTS error: {e}")


def synthesize(text: str) -> bytes:
    """Synthesize text to WAV bytes (for web/Telegram). Returns empty if TTS disabled."""
    if not VOICE_TTS_ENABLED:
        return b""
    try:
        import pyttsx3
        engine = pyttsx3.init()
        engine.setProperty("rate", VOICE_SPEED)
        engine.setProperty("volume", VOICE_VOLUME)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            path = f.name
        engine.save_to_file(text, path)
        engine.runAndWait()
        engine.stop()
        with open(path, "rb") as f:
            data = f.read()
        try:
            os.unlink(path)
        except Exception:
            pass
        return data
    except Exception as e:
        return b""


def record_and_transcribe(seconds: float = 4.0) -> str:
    """Record audio and transcribe. Returns transcribed text."""
    try:
        import sounddevice as sd
        import soundfile as sf
        import numpy as np

        samplerate = 16000
        channels = 1
        duration = seconds
        recording = sd.rec(
            int(duration * samplerate),
            samplerate=samplerate,
            channels=channels,
            dtype=np.float32,
        )
        sd.wait()
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            path = f.name
        sf.write(path, recording, samplerate)
        try:
            return transcribe(path)
        finally:
            try:
                os.unlink(path)
            except Exception:
                pass
    except Exception as e:
        return f"Recording error: {e}"
