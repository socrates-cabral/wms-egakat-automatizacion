"""Entrypoint: py C:\\ClaudeWork\\Softnet_Ventas\\src\\run_ventas.py [--force]"""
import sys
sys.stdout.reconfigure(encoding="utf-8")

import os
import json
import argparse
import traceback
from pathlib import Path
from datetime import datetime, date
from dotenv import load_dotenv

BASE = Path(__file__).resolve().parent.parent   # C:\ClaudeWork\Softnet_Ventas
load_dotenv(BASE / ".env")            # vars Softnet (local, tiene prioridad)
load_dotenv(BASE.parent / ".env")     # vars Azure/SMTP (root, fallback)

from utils import (
    meses_en_ventana, nombre_archivo_sp,
    adquirir_lock, liberar_lock, limpiar_downloads,
    snapshot_existe, guardar_snapshot_cierre,
    cargar_checkpoint, guardar_checkpoint,
)
from softnet_scraper import descargar_libro_ventas
from sp_graph import get_site_id, get_drive_id, descargar_archivo, subir_archivo, asegurar_carpeta
from comparador import parse_libro_ventas, detectar_cambios, hay_cambios, analizar_estado_mes
from event_logger import append_eventos
from notificador import enviar_resumen_diario

DOWNLOADS    = BASE / "downloads"
LOGS_DIR     = BASE / "logs"
SNAPSHOTS_DIR = BASE / "snapshots_cierre"
CONFIG_PATH  = BASE / "config" / "parametros.json"
LOCKFILE     = LOGS_DIR / "softnet_ventas.lock"
LOG_CAMBIOS  = LOGS_DIR / "log_cambios_pagos.xlsx"
LOG_TECNICO  = Path(r"C:\ClaudeWork\logs") / f"softnet_ventas_{datetime.now():%Y-%m-%d_%H%M%S}.log"


def log(msg: str):
    line = f"[{datetime.now():%H:%M:%S}] {msg}"
    print(line)
    LOG_TECNICO.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_TECNICO, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true",
                        help="Ignora el checkpoint y fuerza reproceso de todos los meses")
    args = parser.parse_args()

    DOWNLOADS.mkdir(exist_ok=True)
    LOGS_DIR.mkdir(exist_ok=True)
    SNAPSHOTS_DIR.mkdir(exist_ok=True)

    with open(CONFIG_PATH, encoding="utf-8") as f:
        cfg = json.load(f)

    if not adquirir_lock(LOCKFILE):
        return 0

    modo_test = os.getenv("MODO_TEST", "true").strip().lower() == "true"
    if modo_test:
        destinatarios = [e.strip() for e in os.getenv("EMAIL_TEST", "").split(";") if e.strip()]
        cc = []
    else:
        destinatarios = [e.strip() for e in os.getenv("EMAIL_DESTINO", "").split(";") if e.strip()]
        cc            = [e.strip() for e in os.getenv("EMAIL_CC", "").split(";") if e.strip()]
    if not destinatarios:
        destinatarios = cfg["notificacion"].get("destinatarios", [])

    resumen = {
        "meses_procesados": [],
        "total_eventos": 0,
        "eventos_por_tipo": {},
        "eventos_detalle": [],
        "facturas_vencidas": [],
        "alertas_alto_monto": [],
        "cxc_por_mes": {},
        "snapshots_generados": [],
        "errores": [],
        "log_path": str(LOG_TECNICO),
    }

    try:
        site_id  = get_site_id(cfg["sharepoint"]["hostname"], cfg["sharepoint"]["site_path"])
        drive_id = get_drive_id(site_id, cfg["sharepoint"]["drive_name"])
        log(f"Graph API OK — drive_id: {drive_id[:20]}...")

        hoy = date.today()
        meses_abiertos = meses_en_ventana(hoy, cfg["ventana_dias"], cfg.get("año_inicio"))
        log(f"Meses en ventana de {cfg['ventana_dias']} dias: {meses_abiertos}")

        completados_hoy = set() if args.force else cargar_checkpoint(LOGS_DIR)
        if completados_hoy:
            log(f"[CHECKPOINT] Meses ya completados hoy: {', '.join(sorted(completados_hoy))}")

        _generar_snapshots_pendientes(drive_id, cfg, meses_abiertos, resumen, log)

        for año, mes in meses_abiertos:
            mes_label = f"{año}-{mes:02d}"
            if mes_label in completados_hoy:
                log(f"[SKIP] {mes_label} — ya procesado hoy (checkpoint)")
                resumen["meses_procesados"].append((año, mes, "SKIP"))
                continue
            _procesar_mes(año, mes, drive_id, cfg, resumen, log)

        if cfg["notificacion"]["enviar_siempre"] or resumen["errores"]:
            enviar_resumen_diario(resumen, destinatarios, cc=cc)
        log("[OK] Ejecucion completada")
        return 0

    except Exception as e:
        log(f"[FALLO] Error fatal: {e}")
        log(traceback.format_exc())
        resumen["errores"].append(str(e))
        try:
            enviar_resumen_diario(resumen, destinatarios, cc=cc)
        except Exception:
            pass
        return 1
    finally:
        liberar_lock(LOCKFILE)
        limpiar_downloads(DOWNLOADS)


def _procesar_mes(año, mes, drive_id, cfg, resumen, log_fn):
    nombre_sp  = nombre_archivo_sp(año, mes)
    ruta_sp    = f"{cfg['sharepoint']['ruta_base']}/{año}/{nombre_sp}"
    mes_label  = f"{año}-{mes:02d}"

    try:
        log_fn(f"--- Procesando {mes_label} ---")
        target = DOWNLOADS / f"libro_ventas_{año}_{mes:02d}.xlsx"
        _descargar_con_retry(año, mes, target, cfg, log_fn)

        log_fn("Descargando versión anterior de SharePoint...")
        contenido_anterior = descargar_archivo(drive_id, ruta_sp)
        df_nuevo = parse_libro_ventas(target)

        analisis = analizar_estado_mes(
            df_nuevo, año, mes,
            umbral_alto_monto=cfg.get("umbral_alto_monto", 5_000_000),
            dias_vencimiento=cfg.get("dias_vencimiento", 60),
        )
        resumen["facturas_vencidas"].extend(analisis["vencidas"])
        resumen["alertas_alto_monto"].extend(analisis["alto_monto"])
        resumen["cxc_por_mes"][mes_label] = analisis["cxc"]
        if analisis["vencidas"]:
            log_fn(f"Vencidas: {len(analisis['vencidas'])} facturas")
        if analisis["alto_monto"]:
            log_fn(f"Alto monto: {len(analisis['alto_monto'])} facturas > ${cfg.get('umbral_alto_monto',5_000_000):,.0f}")

        if contenido_anterior is None:
            log_fn("No existe versión anterior en SP → primera carga")
            eventos = []
            debe_subir = True
        else:
            path_anterior = DOWNLOADS / f"anterior_{año}_{mes:02d}.xlsx"
            path_anterior.write_bytes(contenido_anterior)
            df_anterior = parse_libro_ventas(path_anterior)
            eventos = detectar_cambios(df_nuevo, df_anterior, mes_label)
            debe_subir = hay_cambios(eventos) or _hay_filas_nuevas(df_nuevo, df_anterior)

        if eventos:
            append_eventos(LOG_CAMBIOS, eventos)
            log_fn(f"Registrados {len(eventos)} eventos en log de cambios")
            for ev in eventos:
                t = ev["tipo_cambio"]
                resumen["eventos_por_tipo"][t] = resumen["eventos_por_tipo"].get(t, 0) + 1
            resumen["total_eventos"] += len(eventos)
            resumen["eventos_detalle"].extend(eventos)

        if debe_subir:
            asegurar_carpeta(drive_id, f"{cfg['sharepoint']['ruta_base']}/{año}")
            subir_archivo(drive_id, ruta_sp, target.read_bytes())
            log_fn(f"[OK] Subido a SP: {ruta_sp}")
            resumen["meses_procesados"].append((año, mes, "OK"))
        else:
            log_fn("Sin cambios — no se sube a SP")
            resumen["meses_procesados"].append((año, mes, "SIN_CAMBIOS"))
        guardar_checkpoint(LOGS_DIR, mes_label)

    except Exception as e:
        log_fn(f"[FALLO] {mes_label}: {e}")
        resumen["errores"].append(f"{mes_label}: {e}")
        resumen["meses_procesados"].append((año, mes, "FALLO"))


def _descargar_con_retry(año, mes, target, cfg, log_fn):
    import time
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

    backoffs = cfg["softnet"]["retry_backoff_seconds"]
    ultimo_error = None
    for intento in range(cfg["softnet"]["retry_attempts"]):
        try:
            descargar_libro_ventas(año, mes, target, log_fn)
            return
        except (PlaywrightTimeoutError, Exception) as e:
            ultimo_error = e
            if intento < len(backoffs):
                log_fn(f"Intento {intento+1} falló: {e}. Esperando {backoffs[intento]}s...")
                time.sleep(backoffs[intento])
    raise RuntimeError(f"[FALLO] Falló después de {cfg['softnet']['retry_attempts']} intentos: {ultimo_error}")


def _hay_filas_nuevas(df_nuevo, df_anterior) -> bool:
    if df_anterior.empty:
        return not df_nuevo.empty
    return len(set(df_nuevo["doc_id"]) - set(df_anterior["doc_id"])) > 0


def _generar_snapshots_pendientes(drive_id, cfg, meses_abiertos, resumen, log_fn):
    """Para meses cerrados sin snapshot local → descargar de SP y guardar."""
    hoy = date.today()
    año, mes = hoy.year, hoy.month
    for _ in range(24):
        mes -= 1
        if mes == 0:
            mes = 12
            año -= 1
        if (año, mes) in meses_abiertos:
            continue
        if snapshot_existe(SNAPSHOTS_DIR, año, mes):
            continue
        nombre_sp = nombre_archivo_sp(año, mes)
        ruta_sp   = f"{cfg['sharepoint']['ruta_base']}/{año}/{nombre_sp}"
        try:
            contenido = descargar_archivo(drive_id, ruta_sp)
            if contenido:
                guardar_snapshot_cierre(SNAPSHOTS_DIR, año, mes, contenido)
                log_fn(f"Snapshot _cierre generado: {año}-{mes:02d}")
                resumen["snapshots_generados"].append((año, mes))
        except Exception as e:
            log_fn(f"No se pudo generar snapshot {año}-{mes:02d}: {e}")


if __name__ == "__main__":
    sys.exit(main())
