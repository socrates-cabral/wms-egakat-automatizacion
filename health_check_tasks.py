#!/usr/bin/env python
"""
health_check_tasks.py — Monitor activo de Task Scheduler para Egakat.

Corre cada hora vía Task Scheduler. Para cada tarea crítica:
  1. Consulta schtasks → último resultado + última ejecución
  2. Si código != 0 (con whitelist de falsos positivos conocidos) → alerta Telegram
  3. Si tarea silenciada (> max_silencio_hs desde última ejecución) → alerta Telegram
  4. Anti-spam: no repetir alerta de la misma tarea dentro de ANTISPAM_HS horas

Alertas van al grupo Egakat Intel (TELEGRAM_TOKEN_INTERNO + TELEGRAM_GRUPO_INTERNO_ID).
"""
import sys
sys.stdout.reconfigure(encoding="utf-8")

import json
import logging
import re
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "Softnet_Ventas" / "bots"))
from telegram_utils import enviar_grupo_interno  # noqa: E402

LOG_DIR = ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)
STATE_FILE = LOG_DIR / "health_check_state.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / f"health_check_{datetime.now():%Y-%m-%d}.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)

ANTISPAM_HS = 4

# Tareas críticas. max_silencio_hs = cuánto puede pasar sin correr antes de alertar.
# Para tareas MON-FRI poner 75 (cubre weekend). Para diarias 25-30.
TAREAS_CRITICAS = [
    {"nombre": "\\WMS Egakat - Descarga diaria",                       "max_silencio_hs": 25},
    {"nombre": "\\WMS Egakat - Maestro Articulos Derco",               "max_silencio_hs": 25},
    {"nombre": "\\WMS Egakat - Watchdog Alerta",                       "max_silencio_hs": 25},
    {"nombre": "\\Productividad Diario - EGA KAT",                     "max_silencio_hs": 25},
    {"nombre": "\\Softnet Ventas - Descarga Diaria",                   "max_silencio_hs": 30},
    {"nombre": "\\VDR Comparador - EGA KAT",                           "max_silencio_hs": 25},
    {"nombre": "\\FillRate Egakat - Descarga Diaria",                  "max_silencio_hs": 75},
    {"nombre": "\\Watchdog Modulos - Productividad y FillRate",        "max_silencio_hs": 25},
]

# Códigos de Task Scheduler que ignoramos como falsos positivos.
# -2147024703 = 0x80070141 — se ha visto que aparece tras runs OK (validado con log
# completo del script). Si el log del script confirma éxito, ignorar este código.
# 267009 = 0x41301 = "tarea todavía corriendo" (no es error)
CODIGOS_IGNORADOS = {267009}

# Encoding de salida de schtasks en Windows en español (cp850 / cp1252 según consola).
ENCODINGS_INTENTAR = ["cp850", "cp1252", "utf-8"]


def schtasks_query(nombre: str):
    """Devuelve dict con campos parseados o None si la tarea no existe / falla."""
    for enc in ENCODINGS_INTENTAR:
        try:
            r = subprocess.run(
                ["schtasks", "/Query", "/TN", nombre, "/FO", "LIST", "/V"],
                capture_output=True, text=True, encoding=enc, errors="replace",
                timeout=20,
            )
            if r.returncode != 0:
                if enc == ENCODINGS_INTENTAR[-1]:
                    log.warning("schtasks failed for %s: %s", nombre, r.stderr[:200])
                continue
            return _parse_schtasks_output(r.stdout)
        except Exception as e:
            log.warning("schtasks exception for %s (%s): %s", nombre, enc, e)
    return None


def _parse_schtasks_output(text: str) -> dict:
    info = {}
    for line in text.splitlines():
        if ":" not in line:
            continue
        clave, _, valor = line.partition(":")
        clave = clave.strip()
        valor = valor.strip()
        if clave.startswith("Último resultado") or clave.startswith("Last Result"):
            try:
                info["ultimo_resultado"] = int(valor)
            except ValueError:
                pass
        elif clave.startswith("Último tiempo de ejecución") or clave.startswith("Last Run Time"):
            info["ultimo_tiempo_raw"] = valor
            info["ultimo_tiempo"] = _parse_fecha(valor)
        elif clave.startswith("Estado") and "Estado de tarea" not in clave:
            info["estado"] = valor
        elif clave.startswith("Estado de tarea programada") or clave.startswith("Scheduled Task State"):
            info["habilitado"] = "Habilitado" in valor or "Enabled" in valor
    return info


def _parse_fecha(s: str):
    """Acepta 'DD-MM-YYYY HH:MM:SS' o 'YYYY-MM-DD HH:MM:SS' o 'M/D/YYYY ...'."""
    s = s.strip()
    formatos = ["%d-%m-%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%m/%d/%Y %I:%M:%S %p", "%m/%d/%Y %H:%M:%S"]
    for fmt in formatos:
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def cargar_estado() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            log.warning("Estado corrupto, reiniciando")
    return {}


def guardar_estado(estado: dict):
    STATE_FILE.write_text(json.dumps(estado, indent=2, default=str), encoding="utf-8")


def debe_alertar(tarea: str, motivo: str, estado: dict) -> bool:
    """Anti-spam: no repetir misma tarea+motivo dentro de ANTISPAM_HS horas."""
    key = f"{tarea}::{motivo}"
    ultima = estado.get(key)
    if not ultima:
        return True
    try:
        ultima_dt = datetime.fromisoformat(ultima)
    except Exception:
        return True
    return (datetime.now() - ultima_dt) > timedelta(hours=ANTISPAM_HS)


def registrar_alerta(tarea: str, motivo: str, estado: dict):
    estado[f"{tarea}::{motivo}"] = datetime.now().isoformat()


def evaluar(tarea_cfg: dict, estado: dict) -> list[str]:
    """Devuelve lista de mensajes de alerta para esta tarea (0..N)."""
    nombre = tarea_cfg["nombre"]
    max_sil = tarea_cfg["max_silencio_hs"]
    info = schtasks_query(nombre)
    if info is None:
        msg = f"⚠️ Tarea no encontrada: {nombre}"
        if debe_alertar(nombre, "missing", estado):
            registrar_alerta(nombre, "missing", estado)
            return [msg]
        return []

    alertas = []

    if not info.get("habilitado", True):
        log.info("[%s] deshabilitada, skip", nombre)
        return []

    res = info.get("ultimo_resultado")
    if res is not None and res != 0 and res not in CODIGOS_IGNORADOS:
        hex_code = f"0x{res & 0xFFFFFFFF:08X}"
        msg = (
            f"🚨 <b>{nombre.lstrip(chr(92))}</b>\n"
            f"Último resultado: <code>{res}</code> ({hex_code})\n"
            f"Última ejecución: {info.get('ultimo_tiempo_raw', '—')}\n"
            f"Revisar logs."
        )
        if debe_alertar(nombre, f"fail:{res}", estado):
            registrar_alerta(nombre, f"fail:{res}", estado)
            alertas.append(msg)

    ultima_dt = info.get("ultimo_tiempo")
    if ultima_dt:
        horas_silencio = (datetime.now() - ultima_dt).total_seconds() / 3600
        if horas_silencio > max_sil:
            msg = (
                f"⏰ <b>{nombre.lstrip(chr(92))}</b>\n"
                f"Sin correr hace {horas_silencio:.1f} h (límite: {max_sil} h)\n"
                f"Última ejecución: {info.get('ultimo_tiempo_raw', '—')}"
            )
            if debe_alertar(nombre, "silencio", estado):
                registrar_alerta(nombre, "silencio", estado)
                alertas.append(msg)

    return alertas


def main():
    log.info("=" * 60)
    log.info("Health check de tareas críticas — inicio")

    estado = cargar_estado()
    todas_alertas = []
    revisadas = 0

    for tarea_cfg in TAREAS_CRITICAS:
        revisadas += 1
        alertas = evaluar(tarea_cfg, estado)
        for a in alertas:
            todas_alertas.append(a)
            log.warning("ALERTA: %s", a.replace("\n", " | "))

    if todas_alertas:
        cuerpo = "\n\n".join(todas_alertas)
        encabezado = (
            f"🔔 <b>Health check — {datetime.now():%Y-%m-%d %H:%M}</b>\n"
            f"{len(todas_alertas)} alerta(s) en {revisadas} tareas críticas\n\n"
        )
        ok = enviar_grupo_interno(encabezado + cuerpo)
        log.info("Telegram %s — %d alertas enviadas", "OK" if ok else "FALLO", len(todas_alertas))
    else:
        log.info("Todo OK — %d tareas revisadas", revisadas)

    guardar_estado(estado)
    log.info("Health check — fin")


if __name__ == "__main__":
    main()
