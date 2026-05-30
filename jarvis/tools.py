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
CL_TZ = ZoneInfo("America/Santiago")


def get_estado_sistema() -> dict:
    """Retorna hora actual, precios y PnL del crypto bot, y clima de Santiago."""
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

    return {"hora": hora_str, "clima_santiago": clima, "btc": btc, "eth": eth}


def get_wms_kpi() -> dict:
    """Retorna el último resumen de KPIs operativos de Egakat."""
    kpi_path = CRYPTO_BTC.parent.parent / "WMS_Automatizacion" / "kpi_ops_resumen.json"
    if not kpi_path.exists():
        return {"estado": "Sin datos KPI disponibles. El archivo no existe aún."}
    try:
        return json.loads(kpi_path.read_text(encoding="utf-8"))
    except Exception as e:
        return {"estado": f"Error leyendo KPI: {e}"}


def get_apuestas() -> dict:
    """Retorna el reporte del día del agente de apuestas."""
    from datetime import date
    import re
    hoy = date.today().strftime("%Y-%m-%d")
    reporte = APUESTAS_OUT / f"reporte_{hoy}.html"
    if not reporte.exists():
        return {"estado": f"Sin reporte de apuestas para hoy ({hoy})."}
    try:
        html = reporte.read_text(encoding="utf-8")
        texto = re.sub(r"<[^>]+>", " ", html)
        texto = re.sub(r"\s+", " ", texto).strip()
        idx = texto.find("Agente Apuestas")
        resumen = texto[idx:idx + 1500] if idx >= 0 else texto[:1500]
        return {"reporte": resumen}
    except Exception as e:
        return {"estado": f"Error leyendo reporte: {e}"}


def abrir_aplicacion(nombre: str) -> str:
    """Abre una aplicación en Windows por nombre."""
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
        return f"Intentando abrir {nombre}, Señor Sócrates."
    except Exception as e:
        return f"Error al abrir {nombre}: {e}"


def set_timer(minutos: int, mensaje: str = "Tiempo cumplido") -> str:
    """Activa un temporizador con notificación Windows al vencer."""
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
    return f"Temporizador de {minutos} minuto{'s' if minutos != 1 else ''} activado."


def tomar_nota(texto: str) -> str:
    """Guarda una nota en el archivo de notas."""
    now = datetime.now(CL_TZ).strftime("%Y-%m-%d %H:%M")
    linea = f"[{now}] {texto}\n"
    NOTAS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(NOTAS_PATH, "a", encoding="utf-8") as f:
        f.write(linea)
    return f"Nota guardada: \"{texto}\""


def invoke_claude(pregunta: str) -> str:
    """Escala a Claude Sonnet para análisis complejos sobre los proyectos de Señor Sócrates."""
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        msg = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=1024,
            system=(
                "Eres un asistente técnico experto en el stack de Sócrates Cabral "
                "(Python, Playwright, Streamlit, crypto bot grid trading, WMS Egakat). "
                "Responde de forma concisa en español."
            ),
            messages=[{"role": "user", "content": pregunta}],
        )
        return msg.content[0].text
    except Exception as e:
        return f"Error escalando a Claude: {e}"
