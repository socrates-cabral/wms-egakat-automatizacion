import sys
sys.stdout.reconfigure(encoding="utf-8")

import os
import time
import logging
from pathlib import Path
from datetime import date, timedelta, datetime

import pandas as pd
from dotenv import load_dotenv

_BASE = Path(__file__).resolve().parent.parent
load_dotenv(_BASE / ".env")
load_dotenv(_BASE.parent / ".env")

sys.path.insert(0, str(Path(__file__).parent))
from sp_reader import leer_todos_meses_abiertos_consolidado
from db_manager import init_db, alerta_ya_enviada, registrar_alerta_enviada
from telegram_utils import enviar_grupo_interno, formato_monto

# ── Logging ────────────────────────────────────────────────────────────
_LOGS_DIR = Path("C:/ClaudeWork/logs")
_LOGS_DIR.mkdir(exist_ok=True)
_ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(_LOGS_DIR / f"alertas_telegram_{_ts}.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)

# ── Parámetros desde .env con defaults ────────────────────────────────
UMBRAL_ALTO_MONTO = float(os.getenv("UMBRAL_ALTO_MONTO", 10_000_000))
DIAS_PREVENCIMIENTO = int(os.getenv("DIAS_ALERTA_PREVENCIMIENTO", 5))
DIAS_VENCIDA = int(os.getenv("DIAS_ALERTA_VENCIDA", 1))

# Plazos de crédito reconocidos en campo "Forma de Pago"
_PLAZOS = [90, 60, 45, 30, 15]


def _detectar_plazo(forma_pago: str) -> int | None:
    """Detecta el plazo contractual desde el campo Forma de Pago."""
    texto = str(forma_pago).upper()
    for dias in _PLAZOS:
        if str(dias) in texto:
            return dias
    return None


def run_alertas_diarias() -> dict:
    """
    Punto de entrada principal. Llamado desde Task Scheduler / n8n a las 16:15 L-V.
    Retorna resumen de alertas enviadas.
    """
    init_db()
    log.info("Iniciando evaluación de alertas Telegram")

    df = leer_todos_meses_abiertos_consolidado()
    if df.empty:
        log.warning("Sin datos disponibles en SharePoint")
        return {"total": 0}

    log.info(f"Datos cargados: {len(df)} documentos de {df['_mes_label'].nunique()} mes(es)")

    resumen = {
        "prevencimiento": _alertas_prevencimiento(df),
        "vencidas": _alertas_vencidas(df),
        "pagos_alto_monto": _alertas_pagos_alto_monto(df),
    }
    total = sum(resumen.values())

    if total > 0:
        _enviar_resumen(resumen, total)

    log.info(f"[OK] Alertas enviadas: {total} — {resumen}")
    return resumen


def _alertas_prevencimiento(df: pd.DataFrame) -> int:
    """Facturas que vencen en los próximos DIAS_PREVENCIMIENTO días."""
    hoy = date.today()
    enviadas = 0
    no_pagadas = df[df["Estado"] == "NO Pagado"].copy()

    for _, row in no_pagadas.iterrows():
        if pd.isna(row["Fecha"]):
            continue
        plazo = _detectar_plazo(row.get("Forma de Pago", ""))
        if plazo is None:
            continue

        fecha_emision = row["Fecha"].date()
        fecha_vencimiento = fecha_emision + timedelta(days=plazo)
        dias_para_vencer = (fecha_vencimiento - hoy).days

        if not (0 < dias_para_vencer <= DIAS_PREVENCIMIENTO):
            continue

        doc_id = row["doc_id"]
        if alerta_ya_enviada("PREVENCIMIENTO", doc_id):
            continue

        cliente = row.get("Razon Social") or row.get("Razón Social") or "—"
        texto = (
            f"⚠️ <b>VENCIMIENTO EN {dias_para_vencer} DÍAS</b>\n\n"
            f"Cliente: {cliente}\n"
            f"Factura: {doc_id} | Mes: {row['_mes_label']}\n"
            f"Monto: {formato_monto(row['Total'])}\n"
            f"Plazo: {plazo} días | Vence: {fecha_vencimiento.strftime('%d/%m/%Y')}"
        )
        if enviar_grupo_interno(texto):
            registrar_alerta_enviada("PREVENCIMIENTO", doc_id)
            enviadas += 1
            log.info(f"PREVENCIMIENTO enviada: {doc_id} — {cliente}")
            time.sleep(1.2)

    return enviadas


def _alertas_vencidas(df: pd.DataFrame) -> int:
    """Facturas ya vencidas sin pago."""
    hoy = date.today()
    enviadas = 0
    no_pagadas = df[df["Estado"] == "NO Pagado"].copy()

    for _, row in no_pagadas.iterrows():
        if pd.isna(row["Fecha"]):
            continue
        plazo = _detectar_plazo(row.get("Forma de Pago", ""))
        if plazo is None:
            continue

        fecha_emision = row["Fecha"].date()
        fecha_vencimiento = fecha_emision + timedelta(days=plazo)
        dias_vencida = (hoy - fecha_vencimiento).days

        if dias_vencida < DIAS_VENCIDA:
            continue

        doc_id = row["doc_id"]
        if alerta_ya_enviada("VENCIDA", doc_id):
            continue

        cliente = row.get("Razon Social") or row.get("Razón Social") or "—"
        texto = (
            f"🔴 <b>FACTURA VENCIDA — Acción requerida</b>\n\n"
            f"Cliente: {cliente}\n"
            f"Factura: {doc_id} | Mes: {row['_mes_label']}\n"
            f"Monto: {formato_monto(row['Total'])}\n"
            f"Venció: {fecha_vencimiento.strftime('%d/%m/%Y')} "
            f"({dias_vencida} días atrás)"
        )
        if enviar_grupo_interno(texto):
            registrar_alerta_enviada("VENCIDA", doc_id)
            enviadas += 1
            log.info(f"VENCIDA enviada: {doc_id} — {cliente}")
            time.sleep(1.2)

    return enviadas


def _alertas_pagos_alto_monto(df: pd.DataFrame) -> int:
    """Pagos registrados hoy por encima del umbral configurado."""
    hoy = date.today()
    enviadas = 0

    pagadas = df[df["Estado"] == "Pagado"].copy()
    pagadas_hoy = pagadas[pagadas["Fecha Ultimo pago"].dt.date == hoy]

    for _, row in pagadas_hoy.iterrows():
        if row["Total"] < UMBRAL_ALTO_MONTO:
            continue

        doc_id = row["doc_id"]
        if alerta_ya_enviada("PAGO_ALTO_MONTO", doc_id):
            continue

        dias_cobro = row.get("dias_cobro")
        dias_txt = f"{int(dias_cobro)} días" if pd.notna(dias_cobro) else "—"
        cliente = row.get("Razon Social") or row.get("Razón Social") or "—"

        texto = (
            f"✅ <b>PAGO RECIBIDO</b>\n\n"
            f"Cliente: {cliente}\n"
            f"Factura: {doc_id} | Mes: {row['_mes_label']}\n"
            f"Monto cobrado: {formato_monto(row['Total'])}\n"
            f"Días de cobro: {dias_txt}"
        )
        if enviar_grupo_interno(texto):
            registrar_alerta_enviada("PAGO_ALTO_MONTO", doc_id)
            enviadas += 1
            log.info(f"PAGO_ALTO_MONTO enviada: {doc_id} — {cliente} {formato_monto(row['Total'])}")
            time.sleep(1.2)

    return enviadas


def _enviar_resumen(resumen: dict, total: int):
    """Mensaje de cierre con conteo total al final de la ejecución."""
    partes = []
    if resumen["prevencimiento"]:
        partes.append(f"⚠️ {resumen['prevencimiento']} por vencer")
    if resumen["vencidas"]:
        partes.append(f"🔴 {resumen['vencidas']} vencidas")
    if resumen["pagos_alto_monto"]:
        partes.append(f"✅ {resumen['pagos_alto_monto']} pagos alto monto")

    hoy_str = date.today().strftime("%d/%m/%Y")
    texto = f"📊 <b>Resumen alertas {hoy_str}</b>\n" + "\n".join(partes) + f"\nTotal: {total} alertas"
    enviar_grupo_interno(texto)


if __name__ == "__main__":
    run_alertas_diarias()
