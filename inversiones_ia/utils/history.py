"""
history.py — Historial persistente de análisis guardados en data/historial.json
"""

import json
import os
import uuid
from datetime import datetime

_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HISTORY_FILE = os.path.join(_BASE, "data", "historial.json")


def _ensure_file():
    os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
    if not os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump([], f)


def save_analysis(module_name: str, ticker_or_title: str, analysis_text: str) -> str:
    """Guarda un análisis. Retorna el id asignado."""
    _ensure_file()
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = []

    entry = {
        "id": str(uuid.uuid4())[:8],
        "fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "modulo": module_name,
        "titulo": ticker_or_title,
        "resumen": analysis_text[:200].replace("\n", " "),
        "texto_completo": analysis_text,
    }
    data.insert(0, entry)

    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return entry["id"]
    except Exception:
        return ""


def load_history() -> list:
    """Retorna lista de entradas ordenadas por fecha desc."""
    _ensure_file()
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def delete_entry(entry_id: str) -> bool:
    """Elimina una entrada por id."""
    _ensure_file()
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        data = [e for e in data if e.get("id") != entry_id]
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False
