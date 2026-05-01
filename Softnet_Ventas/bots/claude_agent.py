import sys
sys.stdout.reconfigure(encoding="utf-8")

import os
import threading
from pathlib import Path
from dotenv import load_dotenv

_BASE = Path(__file__).resolve().parent.parent
load_dotenv(_BASE / ".env")
load_dotenv(_BASE.parent / ".env")

_claude_client = None
_openai_client = None
_init_lock = threading.Lock()  # Thread-safe lazy init


def _get_claude():
    global _claude_client
    if _claude_client is None:
        with _init_lock:  # Double-checked locking
            if _claude_client is None:
                import anthropic
                _claude_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    return _claude_client


def _get_openai():
    global _openai_client
    if _openai_client is None:
        with _init_lock:  # Double-checked locking
            if _openai_client is None:
                from openai import OpenAI
                _openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    return _openai_client


def llamar_claude(sistema: str, historial: list[dict], max_tokens: int = 1000) -> str:
    try:
        client = _get_claude()
        modelo = os.getenv("CLAUDE_MODEL_ANALISIS", "claude-sonnet-4-6")
        response = client.messages.create(
            model=modelo,
            max_tokens=max_tokens,
            system=sistema,
            messages=historial,
        )
        return response.content[0].text
    except Exception as e:
        print(f"[WARN] Claude falló: {e}. Intentando fallback Gemini...")
        return _llamar_gemini_fallback(sistema, historial)


def llamar_openai(sistema: str, historial: list[dict], max_tokens: int = 500) -> str:
    try:
        client = _get_openai()
        modelo = os.getenv("OPENAI_MODEL_RAPIDO", "gpt-4o-mini")
        mensajes = [{"role": "system", "content": sistema}] + historial
        response = client.chat.completions.create(
            model=modelo,
            messages=mensajes,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"[WARN] OpenAI falló: {e}. Intentando fallback Gemini...")
        return _llamar_gemini_fallback(sistema, historial)


def _llamar_gemini_fallback(sistema: str, historial: list[dict]) -> str:
    try:
        import google.generativeai as genai
        genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
        modelo = os.getenv("GEMINI_MODEL_FALLBACK", "gemini-2.0-flash")
        model = genai.GenerativeModel(modelo, system_instruction=sistema)
        ultimo = historial[-1]["content"] if historial else "Hola"
        response = model.generate_content(ultimo)
        return response.text
    except Exception as e:
        return f"⚠️ Sistema temporalmente no disponible. Intenta en unos minutos. ({e})"


def llamar_agente(tipo: str, sistema: str, historial: list[dict], max_tokens: int = 1000) -> str:
    """Router principal. tipo = 'claude' | 'openai' | 'gemini'"""
    if tipo == "claude":
        return llamar_claude(sistema, historial, max_tokens)
    elif tipo == "openai":
        return llamar_openai(sistema, historial, max_tokens)
    else:
        return _llamar_gemini_fallback(sistema, historial)
