"""
api_operaciones.py — API de Operaciones WMS Egakat
Expone el estado del pipeline WMS como JSON via HTTP.

Entrypoint Task Scheduler:
  py C:\\ClaudeWork\\WMS_Automatizacion\\api_operaciones.py

Endpoints:
  GET /ops/pipeline/hoy       — estado pipeline WMS del día (resumen_ops JSON)
  GET /ops/fillrate/resumen   — OTIF y pendientes por cliente (Sprint 2)
  GET /ops/productividad/resumen — movimientos por cliente (Sprint 3)
  GET /health                 — heartbeat sin autenticación
"""
import sys
sys.stdout.reconfigure(encoding="utf-8")

import os
import json
import glob
import traceback
from pathlib import Path
from datetime import datetime, timedelta
from dotenv import load_dotenv
from flask import Flask, jsonify, request

_BASE = Path(__file__).resolve().parent.parent   # C:\ClaudeWork
load_dotenv(_BASE / ".env")
load_dotenv(_BASE / "Softnet_Ventas" / ".env")  # fallback — secretos compartidos

LOGDIR = _BASE / "logs"
app    = Flask(__name__)

_RUTAS_PUBLICAS = {"/health"}


@app.before_request
def verificar_api_key():
    if request.path in _RUTAS_PUBLICAS:
        return
    secret = os.getenv("API_OPS_SECRET", "")
    if not secret:
        return jsonify({"error": "API no configurada — falta API_OPS_SECRET"}), 500
    key = request.headers.get("X-API-Key", "")
    if not key or key != secret:
        return jsonify({"error": "No autorizado"}), 401


# ── Helpers ───────────────────────────────────────────────────────

def _hoy() -> str:
    return datetime.now().strftime("%Y%m%d")

def _ayer() -> str:
    return (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")


def _leer_resumen_ops(fecha: str) -> dict | None:
    """Lee resumen_ops_{fecha}.json desde el directorio de logs."""
    ruta = LOGDIR / f"resumen_ops_{fecha}.json"
    if not ruta.exists():
        return None
    try:
        with open(ruta, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _estado_label(estado: str) -> str:
    mapping = {
        "OK":            "✅ Todo OK",
        "CON_ADVERTENCIAS": "⚠️ Con advertencias",
        "CON_FALLOS":    "🔴 Con fallos",
    }
    return mapping.get(estado, estado)


# ── Endpoints ─────────────────────────────────────────────────────

@app.route("/ops/pipeline/hoy")
def pipeline_hoy():
    """
    Estado del pipeline WMS del día actual.
    Si no hay datos del día, retorna los del día anterior con flag datos_de_ayer=true.
    """
    try:
        payload = _leer_resumen_ops(_hoy())
        datos_de_ayer = False

        if payload is None:
            payload = _leer_resumen_ops(_ayer())
            datos_de_ayer = True

        if payload is None:
            return jsonify({
                "disponible": False,
                "mensaje": "No se encontraron datos del pipeline. "
                           "El pipeline aún no ha corrido hoy.",
            })

        pipeline = payload.get("pipeline", {})
        validacion = payload.get("validacion", {})

        # Módulos operativos (sin M9 validación) para el resumen
        modulos_ops = [
            m for m in pipeline.get("modulos", [])
            if not str(m.get("nombre", "")).lower().startswith("modulo 9")
        ]
        modulos_con_problema = [
            m for m in modulos_ops
            if m.get("estado") in ("FALLO", "PARCIAL")
        ]

        return jsonify({
            "disponible":   True,
            "datos_de_ayer": datos_de_ayer,
            "fecha":        payload.get("fecha"),
            "hora_inicio":  payload.get("hora_inicio"),
            "pipeline": {
                "estado_global":    pipeline.get("estado_global"),
                "estado_label":     _estado_label(pipeline.get("estado_global", "")),
                "duracion_label":   pipeline.get("duracion_label"),
                "duracion_total_seg": pipeline.get("duracion_total_seg"),
                "n_modulos_ejecutados": pipeline.get("n_modulos"),
                "modulos":          pipeline.get("modulos", []),
                "modulos_con_problema": modulos_con_problema,
            },
            "validacion": {
                "estado_global":     validacion.get("estado_global"),
                "estado_label":      _estado_label(validacion.get("estado_global", "")),
                "total_archivos":    validacion.get("total_archivos"),
                "ok":                validacion.get("ok"),
                "warning":           validacion.get("warning"),
                "error":             validacion.get("error"),
                "hallazgos_relevantes": validacion.get("hallazgos_relevantes", []),
            } if validacion.get("disponible") else {"disponible": False},
        })

    except Exception as e:
        print(f"[FALLO] /ops/pipeline/hoy: {traceback.format_exc()}")
        return jsonify({"error": str(e)}), 500


@app.route("/ops/fillrate/resumen")
def fillrate_resumen():
    """Sprint 2 — pendiente de implementación."""
    return jsonify({
        "disponible": False,
        "mensaje": "Fill Rate disponible en Sprint 2.",
    })


@app.route("/ops/productividad/resumen")
def productividad_resumen():
    """Sprint 3 — pendiente de implementación."""
    return jsonify({
        "disponible": False,
        "mensaje": "Productividad disponible en Sprint 3.",
    })


@app.route("/health")
def health():
    hoy = _hoy()
    tiene_datos_hoy = (LOGDIR / f"resumen_ops_{hoy}.json").exists()
    return jsonify({
        "status":  "ok",
        "servicio": "api_operaciones WMS Egakat",
        "datos_hoy": tiene_datos_hoy,
        "endpoints": [
            "/ops/pipeline/hoy",
            "/ops/fillrate/resumen",
            "/ops/productividad/resumen",
        ],
    })


if __name__ == "__main__":
    port = int(os.getenv("API_OPS_PORT", 8086))
    print(f"[INFO] API Operaciones Egakat corriendo en http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
