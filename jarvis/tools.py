import sys
try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

import json
import os
import subprocess
import threading
import logging
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

from jarvis.config import (
    CRYPTO_BTC, CRYPTO_ETH, APUESTAS_OUT,
    NOTAS_PATH, ANTHROPIC_API_KEY, CLAUDE_MODEL_FAST, CLAUDE_MODEL_DEEP
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


_ALLOWED_APPS = {
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


def abrir_aplicacion(nombre: str) -> str:
    """Abre una aplicación en Windows por nombre (sólo apps de la lista permitida)."""
    _notify_bridge("tool_started", f"Abriendo {nombre}...")
    key = nombre.lower().strip()
    if key not in _ALLOWED_APPS:
        _notify_bridge("tool_done", "App")
        return (f"No reconozco '{nombre}'. Apps disponibles: "
                f"{', '.join(_ALLOWED_APPS)}.")
    cmd = _ALLOWED_APPS[key]
    try:
        subprocess.Popen([cmd], shell=False)
        _notify_bridge("tool_done", "App")
        return f"Abriendo {nombre}, Señor Sócrates."
    except Exception as e:
        _notify_bridge("tool_done", "App")
        return f"Error al abrir {nombre}: {e}"


_TIMERS_PATH = Path(__file__).parent / "timers.json"
_timers_lock = threading.Lock()


def _show_notification(mensaje: str) -> None:
    env = os.environ.copy()
    env["_JARVIS_TIMER_MSG"] = mensaje
    subprocess.run(
        ["powershell", "-Command",
         "Add-Type -AssemblyName System.Windows.Forms; "
         "[System.Windows.Forms.MessageBox]::Show($env:_JARVIS_TIMER_MSG, 'JARVIS')"],
        capture_output=True, env=env
    )


def _save_timer(timer_id: str, target_iso: str, mensaje: str) -> None:
    with _timers_lock:
        data: dict = {}
        if _TIMERS_PATH.exists():
            try:
                data = json.loads(_TIMERS_PATH.read_text(encoding="utf-8"))
            except Exception:
                pass
        data[timer_id] = {"target": target_iso, "mensaje": mensaje}
        _TIMERS_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _remove_timer(timer_id: str) -> None:
    with _timers_lock:
        if not _TIMERS_PATH.exists():
            return
        try:
            data = json.loads(_TIMERS_PATH.read_text(encoding="utf-8"))
            data.pop(timer_id, None)
            _TIMERS_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass


def _schedule_timer(timer_id: str, delay_s: float, mensaje: str) -> None:
    def _fire():
        _show_notification(mensaje)
        _remove_timer(timer_id)
    t = threading.Timer(delay_s, _fire)
    t.daemon = True
    t.start()


def set_timer(minutos: int, mensaje: str = "Tiempo cumplido") -> str:
    """Activa un temporizador persistente con notificación Windows al vencer."""
    _notify_bridge("tool_started", f"Timer {minutos}min...")
    timer_id = f"timer_{datetime.now(CL_TZ).strftime('%Y%m%d_%H%M%S')}"
    delay_s  = minutos * 60
    target   = datetime.now(timezone.utc).timestamp() + delay_s
    target_iso = datetime.fromtimestamp(target, tz=timezone.utc).isoformat()
    _save_timer(timer_id, target_iso, mensaje)
    _schedule_timer(timer_id, delay_s, mensaje)
    _notify_bridge("tool_done", "Timer")
    return f"Temporizador de {minutos} minuto{'s' if minutos != 1 else ''} activado."


def restore_timers() -> list[str]:
    """Llama al arrancar. Restaura timers pendientes; notifica los que vencieron offline."""
    if not _TIMERS_PATH.exists():
        return []
    messages: list[str] = []
    try:
        data = json.loads(_TIMERS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []
    now_ts = datetime.now(timezone.utc).timestamp()
    expired = []
    for tid, entry in data.items():
        try:
            target_ts = datetime.fromisoformat(entry["target"]).timestamp()
            msg = entry.get("mensaje", "Tiempo cumplido")
            remaining = target_ts - now_ts
            if remaining <= 0:
                expired.append(tid)
                messages.append(f"Timer '{msg}' venció mientras JARVIS estaba cerrado.")
            else:
                _schedule_timer(tid, remaining, msg)
                mins = int(remaining // 60)
                messages.append(f"Timer '{msg}' restaurado — vence en {mins} minuto{'s' if mins != 1 else ''}.")
        except Exception:
            expired.append(tid)
    for tid in expired:
        _remove_timer(tid)
    return messages


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


def invoke_claude(pregunta: str, nivel: str = "rapido") -> str:
    """Escala a Claude para analisis sobre los proyectos de Senor Socrates.
    nivel='rapido' usa Sonnet (consultas normales); nivel='profundo' usa Opus (arquitectura, código complejo).
    """
    model = CLAUDE_MODEL_DEEP if nivel == "profundo" else CLAUDE_MODEL_FAST
    _notify_bridge("kai_task_started", pregunta[:40])
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY, timeout=45.0)
        msg = client.messages.create(
            model=model,
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
