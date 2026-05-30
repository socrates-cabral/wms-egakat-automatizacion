import sys
sys.stdout.reconfigure(encoding="utf-8")

import json
import os
import subprocess
import threading
import logging
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

from jarvis.config import (
    CRYPTO_BTC, CRYPTO_ETH, APUESTAS_OUT,
    NOTAS_PATH, ANTHROPIC_API_KEY, CLAUDE_MODEL
)

logger = logging.getLogger("jarvis.tools")


def _notify_bridge(signal: str, message: str = "") -> None:
    """Emite un signal del bridge si Qt esta disponible. Falla silenciosamente si no."""
    try:
        from jarvis.ui.bridge import get_bridge
        bridge = get_bridge()
        sig = getattr(bridge, signal)
        if message:
            sig.emit(message)
        else:
            sig.emit()
    except Exception:
        pass


CL_TZ = ZoneInfo("America/Santiago")


def get_estado_sistema() -> dict:
    """Retorna hora actual, precios y PnL del crypto bot, y clima de Santiago."""
    _notify_bridge("tool_started", "Consultando sistema...")
    now = datetime.now(CL_TZ)
    hora_str = now.strftime("%H:%M del %d/%m/%Y")

    clima = "sin datos"
    try:
        resp = requests.get("https://wttr.in/Santiago?format=j1", timeout=5)
        cond = resp.json()["current_condition"][0]
        clima = f"{cond['temp_C']}°C, {cond['weatherDesc'][0]['value']}"
    except Exception:
        pass

    btc = {"precio": "sin datos", "pnl": "sin datos"}
    if CRYPTO_BTC.exists():
        try:
            data = json.loads(CRYPTO_BTC.read_text(encoding="utf-8"))
            btc = {
                "precio": f"${data.get('precio_ultimo', 0):,.0f}",
                "pnl": f"{data.get('pnl_realizado_usdt', 0):+.4f} USDT",
            }
        except Exception:
            pass

    eth = {"precio": "sin datos", "pnl": "sin datos"}
    if CRYPTO_ETH.exists():
        try:
            data = json.loads(CRYPTO_ETH.read_text(encoding="utf-8"))
            eth = {
                "precio": f"${data.get('precio_ultimo', 0):,.2f}",
                "pnl": f"{data.get('pnl_realizado_usdt', 0):+.4f} USDT",
            }
        except Exception:
            pass

    _notify_bridge("tool_done", "Sistema")
    return {"hora": hora_str, "clima_santiago": clima, "btc": btc, "eth": eth}


def get_wms_kpi() -> dict:
    """Retorna el último resumen de KPIs operativos de Egakat."""
    _notify_bridge("tool_started", "Leyendo WMS KPI...")
    kpi_path = CRYPTO_BTC.parent.parent / "WMS_Automatizacion" / "kpi_ops_resumen.json"
    if not kpi_path.exists():
        _notify_bridge("tool_done", "WMS KPI")
        return {"estado": "Sin datos KPI disponibles. El archivo no existe aún."}
    try:
        resultado = json.loads(kpi_path.read_text(encoding="utf-8"))
        _notify_bridge("tool_done", "WMS KPI")
        return resultado
    except Exception as e:
        _notify_bridge("tool_done", "WMS KPI")
        return {"estado": f"Error leyendo KPI: {e}"}


def get_apuestas() -> dict:
    """Retorna el reporte del día del agente de apuestas."""
    _notify_bridge("tool_started", "Consultando apuestas...")
    from datetime import date
    import re
    hoy = date.today().strftime("%Y-%m-%d")
    reporte = APUESTAS_OUT / f"reporte_{hoy}.html"
    if not reporte.exists():
        _notify_bridge("tool_done", "Apuestas")
        return {"estado": f"Sin reporte de apuestas para hoy ({hoy})."}
    try:
        html = reporte.read_text(encoding="utf-8")
        texto = re.sub(r"<[^>]+>", " ", html)
        texto = re.sub(r"\s+", " ", texto).strip()
        idx = texto.find("Agente Apuestas")
        resumen = texto[idx:idx + 1500] if idx >= 0 else texto[:1500]
        _notify_bridge("tool_done", "Apuestas")
        return {"reporte": resumen}
    except Exception as e:
        _notify_bridge("tool_done", "Apuestas")
        return {"estado": f"Error leyendo reporte: {e}"}


def abrir_aplicacion(nombre: str) -> str:
    """Abre una aplicación en Windows por nombre."""
    _notify_bridge("tool_started", f"Abriendo {nombre}...")
    apps = {
        "chrome":      "chrome",
        "spotify":     "spotify",
        "vscode":      "code",
        "vs code":     "code",
        "explorer":    "explorer",
        "notepad":     "notepad",
        "calculator":  "calc",
        "terminal":    "wt",
        "powershell":  "powershell",
        "whatsapp":    "WhatsApp",
    }
    cmd = apps.get(nombre.lower().strip(), nombre)
    try:
        subprocess.Popen(cmd, shell=True)
        _notify_bridge("tool_done", "App")
        return f"Intentando abrir {nombre}, Señor Sócrates."
    except Exception as e:
        _notify_bridge("tool_done", "App")
        return f"Error al abrir {nombre}: {e}"


def set_timer(minutos: int, mensaje: str = "Tiempo cumplido") -> str:
    """Activa un temporizador con notificación Windows al vencer."""
    _notify_bridge("tool_started", f"Timer {minutos}min...")
    def _alert():
        subprocess.run(
            ["powershell", "-Command",
             f'Add-Type -AssemblyName System.Windows.Forms; '
             f'[System.Windows.Forms.MessageBox]::Show("{mensaje}", "JARVIS")'],
            capture_output=True
        )
    t = threading.Timer(minutos * 60, _alert)
    t.daemon = True
    t.start()
    _notify_bridge("tool_done", "Timer")
    return f"Temporizador de {minutos} minuto{'s' if minutos != 1 else ''} activado."


def tomar_nota(texto: str) -> str:
    """Guarda una nota en el archivo de notas."""
    _notify_bridge("tool_started", "Guardando nota...")
    now = datetime.now(CL_TZ).strftime("%Y-%m-%d %H:%M")
    linea = f"[{now}] {texto}\n"
    NOTAS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(NOTAS_PATH, "a", encoding="utf-8") as f:
        f.write(linea)
    _notify_bridge("tool_done", "Nota")
    return f"Nota guardada: \"{texto}\""


def invoke_claude(pregunta: str) -> str:
    """Escala a Claude Sonnet para analisis complejos sobre los proyectos de Senor Socrates."""
    _notify_bridge("kai_task_started", pregunta[:40])
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY, timeout=45.0)
        msg = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=1024,
            system=(
                "Eres un asistente tecnico experto en el stack de Socrates Cabral "
                "(Python, Playwright, Streamlit, crypto bot grid trading, WMS Egakat). "
                "Responde de forma concisa en espanol."
            ),
            messages=[{"role": "user", "content": pregunta}],
        )
        resultado = next((b.text for b in msg.content if b.type == "text"), "Sin respuesta de Claude.")
    except Exception as e:
        resultado = f"Error escalando a Claude: {e}"
    _notify_bridge("kai_task_done", resultado[:40])
    return resultado
