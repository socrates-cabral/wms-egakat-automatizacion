"""
generar_resumen_ops.py
Genera resumen_ops_YYYYMMDD.json al final del pipeline WMS.
La API de Operaciones lee este archivo — cero llamadas SharePoint por consulta.

Llamado desde run_todos.py: generar_resumen_ops(resultados, inicio_total, dur_total, logdir)
"""
import sys
sys.stdout.reconfigure(encoding="utf-8")

import json
import os
from datetime import datetime
from pathlib import Path


def _clasificar_modulo(nombre, ok, fallos, reintentos, dur):
    skip = (dur == 0 and ok and reintentos == 0 and not fallos)
    if skip:
        return "SKIP"
    nombre_lower = str(nombre).strip().lower()
    es_validacion = nombre_lower.startswith("modulo 9")
    if es_validacion:
        return "ADVERTENCIA" if (fallos or not ok) else ("OK_REINTENTO" if reintentos > 0 else "OK")
    if not ok:
        return "FALLO"
    if fallos:
        return "PARCIAL"
    if reintentos > 0:
        return "OK_REINTENTO"
    return "OK"


def _leer_validacion_json(logdir: str) -> dict | None:
    val_dir = os.path.join(logdir, "validaciones")
    if not os.path.isdir(val_dir):
        return None
    candidatos = [
        os.path.join(val_dir, f)
        for f in os.listdir(val_dir)
        if f.startswith("validacion_total_") and f.lower().endswith(".json")
    ]
    if not candidatos:
        return None
    candidatos.sort(key=os.path.getmtime, reverse=True)
    try:
        with open(candidatos[0], "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _resumir_validacion(payload: dict) -> dict:
    if not payload or not isinstance(payload, dict):
        return {"disponible": False}

    resumen = payload.get("resumen", {}) or {}
    detalles = payload.get("detalles", []) or []

    hallazgos = []
    for item in detalles:
        estado = str(item.get("estado_final") or "OK").upper()
        if estado in ("WARNING", "ERROR", "PARCIAL"):
            schema = item.get("schema") or item.get("tipo_archivo") or "archivo"
            for h in (item.get("hallazgos") or []):
                detalle = str(h.get("detalle") or "").strip()
                if detalle and h.get("regla") != "ARCHIVO_SIN_REGISTROS":
                    hallazgos.append(f"{schema}: {detalle[:120]}")
            if not item.get("hallazgos") and estado in ("ERROR", "PARCIAL"):
                hallazgos.append(f"{schema}: {estado}")

    ok_n  = int(resumen.get("OK", 0))
    warn  = int(resumen.get("WARNING", 0))
    parc  = int(resumen.get("PARCIAL", 0))
    err   = int(resumen.get("ERROR", 0))

    if err > 0 or parc > 0:
        estado_global = "CON_FALLOS"
    elif warn > 0:
        estado_global = "CON_ADVERTENCIAS"
    else:
        estado_global = "OK"

    return {
        "disponible": True,
        "estado_global": estado_global,
        "total_archivos": ok_n + warn + parc + err,
        "ok": ok_n,
        "warning": warn,
        "parcial": parc,
        "error": err,
        "hallazgos_relevantes": hallazgos[:6],
    }


def generar_resumen_ops(resultados: list, inicio_total: datetime,
                        dur_total: int, logdir: str) -> str | None:
    """
    Genera resumen_ops_YYYYMMDD.json en logdir.
    Retorna la ruta del archivo generado, o None si falla.
    """
    try:
        modulos = []
        hay_fallos = False
        hay_advertencias = False

        for nombre, ok, dur, fallos, reintentos in resultados:
            estado = _clasificar_modulo(nombre, ok, fallos, reintentos, dur)
            es_validacion = str(nombre).strip().lower().startswith("modulo 9")

            modulos.append({
                "nombre": nombre,
                "estado": estado,
                "duracion_seg": dur,
                "reintentos": reintentos,
                "fallos": fallos[:3] if fallos else [],  # máx 3 para el JSON
            })

            if not es_validacion and estado in ("FALLO", "PARCIAL"):
                hay_fallos = True
            if es_validacion and estado == "ADVERTENCIA":
                hay_advertencias = True

        if hay_fallos:
            estado_global = "CON_FALLOS"
        elif hay_advertencias:
            estado_global = "CON_ADVERTENCIAS"
        else:
            estado_global = "OK"

        val_payload = _leer_validacion_json(logdir)
        validacion = _resumir_validacion(val_payload)

        payload = {
            "fecha": inicio_total.strftime("%Y-%m-%d"),
            "timestamp": inicio_total.isoformat(),
            "hora_inicio": inicio_total.strftime("%H:%M:%S"),
            "pipeline": {
                "estado_global": estado_global,
                "duracion_total_seg": dur_total,
                "duracion_label": f"{dur_total // 60}m {dur_total % 60}s",
                "n_modulos": len([m for m in modulos if m["estado"] != "SKIP"]),
                "modulos": modulos,
            },
            "validacion": validacion,
        }

        nombre_archivo = f"resumen_ops_{inicio_total.strftime('%Y%m%d')}.json"
        ruta = os.path.join(logdir, nombre_archivo)
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

        print(f"  [OPS] Resumen operacional guardado: {nombre_archivo}")
        return ruta

    except Exception as e:
        import traceback
        print(f"  [OPS] Error generando resumen_ops: {e}")
        print(f"  [TRACEBACK] {traceback.format_exc()}")
        return None
