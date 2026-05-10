"""
api_operaciones.py - API de Operaciones WMS Egakat
Expone el estado del pipeline WMS como JSON via HTTP.

Entrypoint Task Scheduler:
  py C:\\ClaudeWork\\WMS_Automatizacion\\api_operaciones.py

Endpoints:
  GET /ops/pipeline/hoy
  GET /ops/contexto/resumen
  GET /ops/fillrate/resumen
  GET /ops/productividad/resumen
  GET /health
"""
import sys
sys.stdout.reconfigure(encoding="utf-8")

import json
import os
import re
import traceback
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, request

_BASE = Path(__file__).resolve().parent.parent   # C:\ClaudeWork
load_dotenv(_BASE / ".env")
load_dotenv(_BASE / "Softnet_Ventas" / ".env")  # fallback - secretos compartidos

LOGDIR = _BASE / "logs"
KPI_OPS_PATTERN = "resumen_kpi_ops_*.json"
app = Flask(__name__)

_RUTAS_PUBLICAS = {"/health"}


@app.before_request
def verificar_api_key():
    if request.path in _RUTAS_PUBLICAS:
        return
    secret = os.getenv("API_OPS_SECRET", "")
    if not secret:
        return jsonify({"error": "API no configurada - falta API_OPS_SECRET"}), 500
    key = request.headers.get("X-API-Key", "")
    if not key or key != secret:
        return jsonify({"error": "No autorizado"}), 401


# Helpers

def _hoy() -> str:
    return datetime.now().strftime("%Y%m%d")


def _ayer() -> str:
    return (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")


def _leer_json_seguro(path: str | Path | None) -> dict | list | None:
    """Lee un JSON local sin propagar errores al endpoint."""
    if not path:
        return None
    ruta = Path(path)
    if not ruta.exists() or not ruta.is_file():
        return None
    try:
        with ruta.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _leer_texto_seguro(path: str | Path | None, max_chars: int = 3000) -> str | None:
    """Lee texto local y recorta la salida para exponer solo un resumen corto."""
    if not path:
        return None
    ruta = Path(path)
    if not ruta.exists() or not ruta.is_file():
        return None
    try:
        texto = ruta.read_text(encoding="utf-8", errors="replace").strip()
    except Exception:
        return None
    if not texto:
        return None
    if len(texto) > max_chars:
        return texto[:max_chars].rstrip() + "\n...[truncado]"
    return texto


def _ultimo_archivo(pattern: str) -> Path | None:
    """Retorna el archivo mas reciente dentro de C:\\ClaudeWork\\logs para un patron dado."""
    candidatos = [p for p in LOGDIR.glob(pattern) if p.is_file()]
    if not candidatos:
        return None
    return max(candidatos, key=lambda p: p.stat().st_mtime)


def _dedupe_textos(items: list[str], max_items: int | None = None) -> list[str]:
    """Elimina duplicados exactos preservando orden y recorta si corresponde."""
    salida: list[str] = []
    vistos: set[str] = set()
    for item in items:
        texto = str(item or "").strip()
        if not texto or texto in vistos:
            continue
        vistos.add(texto)
        salida.append(texto)
        if max_items is not None and len(salida) >= max_items:
            break
    return salida


def _fecha_kpi_desde_nombre(path: Path | None) -> tuple[int, int, int] | None:
    """Extrae YYYYMMDD desde resumen_kpi_ops_YYYYMMDD.json para ordenar defensivamente."""
    if not path:
        return None
    match = re.search(r"resumen_kpi_ops_(\d{4})(\d{2})(\d{2})\.json$", path.name, re.IGNORECASE)
    if not match:
        return None
    try:
        return tuple(int(match.group(i)) for i in range(1, 4))
    except Exception:
        return None


def _ruta_resumen_kpi_ops_reciente() -> Path | None:
    """Busca el resumen KPI mas reciente usando fecha en nombre y mtime como fallback."""
    candidatos = [p for p in LOGDIR.glob(KPI_OPS_PATTERN) if p.is_file()]
    if not candidatos:
        return None

    def _sort_key(path: Path) -> tuple[tuple[int, int, int], float]:
        return (_fecha_kpi_desde_nombre(path) or (0, 0, 0), path.stat().st_mtime)

    return max(candidatos, key=_sort_key)


def _leer_resumen_ops(fecha: str) -> dict | None:
    """Lee resumen_ops_{fecha}.json desde el directorio de logs."""
    payload = _leer_json_seguro(LOGDIR / f"resumen_ops_{fecha}.json")
    return payload if isinstance(payload, dict) else None


def _resolver_payload_pipeline() -> tuple[dict | None, bool, Path | None]:
    """Busca primero el resumen de hoy y luego el de ayer."""
    for fecha, datos_de_ayer in ((_hoy(), False), (_ayer(), True)):
        ruta = LOGDIR / f"resumen_ops_{fecha}.json"
        payload = _leer_json_seguro(ruta)
        if isinstance(payload, dict):
            return payload, datos_de_ayer, ruta
    return None, False, None


def _estado_label(estado: str) -> str:
    mapping = {
        "OK": "Todo OK",
        "CON_ADVERTENCIAS": "Con advertencias",
        "CON_FALLOS": "Con fallos",
    }
    return mapping.get(estado, estado)


def _extraer_cliente_desde_ruta(archivo: str) -> str:
    """Intenta extraer el cliente desde las rutas validadas en logs."""
    if not archivo:
        return "DESCONOCIDO"
    try:
        partes = Path(archivo).parts
        if "Clientes EK" in partes:
            idx = partes.index("Clientes EK")
            if idx + 1 < len(partes):
                return str(partes[idx + 1]).strip()
        if "Stagin IN- OUT" in partes:
            idx = partes.index("Stagin IN- OUT")
            if idx + 2 < len(partes):
                return str(partes[idx + 2]).strip()
        if len(partes) >= 5:
            return str(partes[-5]).strip()
    except Exception:
        pass
    return Path(str(archivo)).stem


def _resumen_pipeline_base(payload_pipeline: dict | None) -> dict:
    """Normaliza el bloque pipeline para reutilizarlo entre endpoints."""
    if not isinstance(payload_pipeline, dict):
        return {"disponible": False}

    pipeline = payload_pipeline.get("pipeline", {}) or {}
    modulos = pipeline.get("modulos", []) or []
    modulos_ops = [
        modulo for modulo in modulos
        if not str(modulo.get("nombre", "")).lower().startswith("modulo 9")
    ]
    modulos_con_problema = [
        modulo for modulo in modulos_ops
        if modulo.get("estado") in ("FALLO", "PARCIAL")
    ]

    return {
        "disponible": True,
        "fecha": payload_pipeline.get("fecha"),
        "hora_inicio": payload_pipeline.get("hora_inicio"),
        "pipeline": {
            "estado_global": pipeline.get("estado_global"),
            "estado_label": _estado_label(pipeline.get("estado_global", "")),
            "duracion_label": pipeline.get("duracion_label"),
            "duracion_total_seg": pipeline.get("duracion_total_seg"),
            "n_modulos_ejecutados": pipeline.get("n_modulos"),
            "modulos": modulos,
            "modulos_con_problema": modulos_con_problema,
        },
    }


def _resumen_validacion(payload_pipeline: dict | None) -> dict:
    """Devuelve el resumen de validacion ya consolidado, con fallback al ultimo JSON."""
    if isinstance(payload_pipeline, dict):
        validacion = payload_pipeline.get("validacion", {}) or {}
        if validacion.get("disponible"):
            return {
                "disponible": True,
                "estado_global": validacion.get("estado_global"),
                "estado_label": _estado_label(validacion.get("estado_global", "")),
                "total_archivos": validacion.get("total_archivos"),
                "ok": validacion.get("ok"),
                "warning": validacion.get("warning"),
                "parcial": validacion.get("parcial"),
                "error": validacion.get("error"),
                "hallazgos_relevantes": validacion.get("hallazgos_relevantes", []),
            }

    payload_validacion = _leer_json_seguro(_ultimo_archivo("validaciones/validacion_total_*.json"))
    if not isinstance(payload_validacion, dict):
        return {"disponible": False}

    resumen = payload_validacion.get("resumen", {}) or {}
    ok_n = int(resumen.get("OK", 0))
    warn = int(resumen.get("WARNING", 0))
    parc = int(resumen.get("PARCIAL", 0))
    err = int(resumen.get("ERROR", 0))

    if err > 0 or parc > 0:
        estado_global = "CON_FALLOS"
    elif warn > 0:
        estado_global = "CON_ADVERTENCIAS"
    else:
        estado_global = "OK"

    return {
        "disponible": True,
        "estado_global": estado_global,
        "estado_label": _estado_label(estado_global),
        "total_archivos": ok_n + warn + parc + err,
        "ok": ok_n,
        "warning": warn,
        "parcial": parc,
        "error": err,
        "hallazgos_relevantes": [],
    }


def _resumen_alertas(payload_pipeline: dict | None, datos_de_ayer: bool = False) -> list[str]:
    """Genera alertas ejecutivas a partir de pipeline y validacion."""
    alertas: list[str] = []

    if datos_de_ayer:
        alertas.append("La informacion corresponde al ultimo cierre disponible.")

    if not isinstance(payload_pipeline, dict):
        alertas.append("No se encontro resumen_ops reciente del pipeline.")
        return alertas

    resumen_pipeline = _resumen_pipeline_base(payload_pipeline)
    validacion = _resumen_validacion(payload_pipeline)
    pipeline = resumen_pipeline.get("pipeline", {}) or {}
    estado_global = pipeline.get("estado_global")

    if estado_global == "CON_FALLOS":
        alertas.append("Revisar modulos operativos con FALLO o PARCIAL.")
    elif estado_global == "CON_ADVERTENCIAS":
        alertas.append("Revisar advertencias del pipeline y la validacion diaria.")

    modulos_con_problema = pipeline.get("modulos_con_problema", []) or []
    if modulos_con_problema:
        nombres = ", ".join(
            str(modulo.get("nombre", "")).strip()
            for modulo in modulos_con_problema
            if modulo.get("nombre")
        )
        if nombres:
            alertas.append(f"Modulos con problema: {nombres}.")

    if int(validacion.get("error") or 0) > 0:
        alertas.append("Validacion detecto archivos con ERROR.")
    elif int(validacion.get("warning") or 0) > 0:
        alertas.append("Validacion detecto archivos con WARNING no bloqueante.")

    for hallazgo in (validacion.get("hallazgos_relevantes") or [])[:3]:
        hallazgo_txt = str(hallazgo).strip()
        if hallazgo_txt:
            alertas.append(f"Hallazgo relevante: {hallazgo_txt}.")

    return list(dict.fromkeys(alertas))


def _resumen_dataset_validado(
    payload_validacion: dict,
    schemas: tuple[str, ...],
    mensaje_faltante: str,
) -> dict:
    """Resume un conjunto de archivos validados sin leer Excel ni recalcular negocio."""
    detalles = payload_validacion.get("detalles", []) or []
    schemas_lower = {schema.lower() for schema in schemas}
    items = [
        item for item in detalles
        if str(item.get("schema", "")).lower() in schemas_lower
    ]
    if not items:
        return {"disponible": False, "mensaje": mensaje_faltante}

    resumen = {"OK": 0, "WARNING": 0, "PARCIAL": 0, "ERROR": 0}
    clientes: list[str] = []
    clientes_con_problemas: list[str] = []
    observaciones: list[str] = []
    registros_totales = 0

    for item in items:
        estado = str(item.get("estado_final") or "OK").upper()
        resumen.setdefault(estado, 0)
        resumen[estado] += 1

        cliente = _extraer_cliente_desde_ruta(str(item.get("archivo") or ""))
        if cliente:
            clientes.append(cliente)
        if estado in ("WARNING", "PARCIAL", "ERROR") and cliente:
            clientes_con_problemas.append(cliente)

        estructura = item.get("estructura", {}) or {}
        try:
            registros_totales += int(estructura.get("row_count") or 0)
        except Exception:
            pass

        negocio = item.get("negocio", {}) or {}
        hallazgos = negocio.get("hallazgos") or item.get("hallazgos") or []
        for hallazgo in hallazgos[:2]:
            detalle = ""
            if isinstance(hallazgo, dict):
                detalle = str(hallazgo.get("detalle") or hallazgo.get("regla") or "").strip()
            else:
                detalle = str(hallazgo).strip()
            if detalle:
                observaciones.append(f"{cliente}: {detalle[:140]}")
            if len(observaciones) >= 4:
                break
        if len(observaciones) >= 4:
            continue

    return {
        "disponible": True,
        "total_archivos": len(items),
        "ok": resumen.get("OK", 0),
        "warning": resumen.get("WARNING", 0),
        "parcial": resumen.get("PARCIAL", 0),
        "error": resumen.get("ERROR", 0),
        "registros_totales": registros_totales,
        "clientes": sorted(set(clientes)),
        "clientes_con_problemas": sorted(set(clientes_con_problemas)),
        "observaciones": observaciones[:4],
    }


def _resumen_nnss_desde_logs() -> dict:
    """Consolida contexto minimo de pedidos preparados y recepciones desde validaciones."""
    ruta = _ultimo_archivo("validaciones/validacion_total_*.json")
    payload = _leer_json_seguro(ruta)
    if not isinstance(payload, dict):
        return {
            "disponible": False,
            "mensaje": "No se encontro resumen NNSS reciente.",
        }

    pedidos_preparados = _resumen_dataset_validado(
        payload,
        ("pedidos_preparados",),
        "No se encontraron archivos validados de pedidos preparados.",
    )
    recepciones = _resumen_dataset_validado(
        payload,
        ("recepciones_recibidas",),
        "No se encontraron archivos validados de recepciones.",
    )

    if not pedidos_preparados.get("disponible") and not recepciones.get("disponible"):
        return {
            "disponible": False,
            "mensaje": "No se encontro resumen NNSS reciente.",
            "_source": str(ruta) if ruta else None,
        }

    partes = []
    if pedidos_preparados.get("disponible"):
        partes.append(
            "Pedidos preparados validados: "
            f"{pedidos_preparados.get('total_archivos', 0)} archivos, "
            f"{pedidos_preparados.get('registros_totales', 0)} registros, "
            f"OK/WARNING/ERROR: {pedidos_preparados.get('ok', 0)}/"
            f"{pedidos_preparados.get('warning', 0)}/"
            f"{pedidos_preparados.get('error', 0)}"
        )
    if recepciones.get("disponible"):
        partes.append(
            "Recepciones validadas: "
            f"{recepciones.get('total_archivos', 0)} archivos, "
            f"{recepciones.get('registros_totales', 0)} registros, "
            f"OK/WARNING/ERROR: {recepciones.get('ok', 0)}/"
            f"{recepciones.get('warning', 0)}/"
            f"{recepciones.get('error', 0)}"
        )

    return {
        "disponible": True,
        "resumen_texto": ". ".join(partes) + ".",
        "pedidos_preparados": pedidos_preparados,
        "recepciones": recepciones,
        "pedidos_pendientes": {
            "disponible": False,
            "mensaje": "No se encontro resumen NNSS reciente de pedidos pendientes en logs.",
        },
        "otif": {
            "disponible": False,
            "mensaje": "No se encontro resumen OTIF reciente en logs.",
        },
        "_source": str(ruta) if ruta else None,
    }


def _resumen_generico_desde_logs(nombre: str, patterns: tuple[str, ...]) -> dict:
    """Busca archivos recientes por nombre y devuelve un extracto defensivo si existen."""
    ruta = None
    for pattern in patterns:
        candidato = _ultimo_archivo(pattern)
        if candidato and (ruta is None or candidato.stat().st_mtime > ruta.stat().st_mtime):
            ruta = candidato

    if ruta is None:
        return {
            "disponible": False,
            "mensaje": f"No se encontro resumen {nombre} reciente.",
        }

    if ruta.suffix.lower() == ".json":
        payload = _leer_json_seguro(ruta)
        if isinstance(payload, dict):
            claves = ", ".join(list(payload.keys())[:6]) or "sin claves visibles"
            return {
                "disponible": True,
                "resumen_texto": f"Se encontro {ruta.name}. Claves visibles: {claves}.",
                "_source": str(ruta),
            }

    texto = _leer_texto_seguro(ruta, max_chars=1200)
    if texto:
        lineas = [line.strip() for line in texto.splitlines() if line.strip()]
        resumen_texto = " | ".join(lineas[:5])[:800]
        return {
            "disponible": True,
            "resumen_texto": resumen_texto,
            "_source": str(ruta),
        }

    return {
        "disponible": False,
        "mensaje": f"Se encontro un archivo {nombre}, pero no se pudo leer con seguridad.",
        "_source": str(ruta),
    }


def _resumen_productividad_desde_logs() -> dict:
    """Busca solo resumentes o logs recientes de productividad sin recalcular nada."""
    return _resumen_generico_desde_logs(
        "de productividad",
        (
            "**/*productividad*.json",
            "**/*productividad*.txt",
            "**/*productividad*.log",
        ),
    )


def _resumen_fillrate_desde_logs() -> dict:
    """Busca solo resumentes o logs recientes de fill rate / OTIF."""
    return _resumen_generico_desde_logs(
        "de fill rate",
        (
            "**/*fillrate*.json",
            "**/*fillrate*.txt",
            "**/*fillrate*.log",
            "**/*otif*.json",
            "**/*otif*.txt",
            "**/*otif*.log",
        ),
    )


def _resumen_despacho_desde_logs() -> dict:
    """Lee el ultimo log de despacho y extrae un resumen corto del pipeline."""
    ruta = _ultimo_archivo("despacho_pipeline_*.log")
    if ruta is None:
        return {
            "disponible": False,
            "mensaje": "No se encontro resumen de despacho reciente.",
        }

    texto = _leer_texto_seguro(ruta, max_chars=2500)
    if not texto:
        return {
            "disponible": False,
            "mensaje": "Se encontro un log de despacho, pero no se pudo leer con seguridad.",
            "_source": str(ruta),
        }

    lineas = [line.strip() for line in texto.splitlines() if line.strip()]
    fecha_linea = next((line for line in lineas if "Fecha:" in line), "")
    etapas_ok = sum(1 for line in lineas if "[OK]" in line)
    fallos = [line for line in lineas if "[FALLO]" in line or "[ERROR]" in line]
    finalizado = any("FIN PIPELINE" in line for line in lineas)
    estado = "CON_FALLOS" if fallos else ("OK" if finalizado else "EN_PROCESO")

    if fallos:
        resumen_texto = f"Despacho con fallos visibles. {fallos[0]}"
    else:
        resumen_texto = (
            f"{fecha_linea or 'Fecha no informada'} | "
            f"estado={estado} | etapas_ok={etapas_ok}"
        )

    return {
        "disponible": True,
        "estado": estado,
        "resumen_texto": resumen_texto,
        "detalle_final": lineas[-4:],
        "_source": str(ruta),
    }


def _resumen_kpi_ops_desde_logs() -> dict:
    """Lee el ultimo resumen_kpi_ops desde logs sin recalcular ni ejecutar procesos."""
    ruta = _ruta_resumen_kpi_ops_reciente()
    if ruta is None:
        return {
            "disponible": False,
            "mensaje": "No se encontró resumen KPI operacional reciente.",
        }

    try:
        payload = _leer_json_seguro(ruta)
        if not isinstance(payload, dict):
            return {
                "disponible": False,
                "mensaje": "No se pudo leer resumen KPI operacional.",
                "error": "Contenido JSON inválido o vacío.",
            }

        return {
            "disponible": True,
            "fuente": str(ruta),
            "fecha_archivo": datetime.fromtimestamp(ruta.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
            "nnss": payload.get("nnss", {}),
            "productividad": payload.get("productividad", {}),
            "inventario": payload.get("inventario", {
                "disponible": False,
                "mensaje": "No se encontró sección de inventario en el resumen KPI operacional.",
            }),
            "historico": payload.get("historico"),
            "alertas": payload.get("alertas", []) or [],
            "recomendaciones": payload.get("recomendaciones", []) or [],
        }
    except Exception as exc:
        return {
            "disponible": False,
            "mensaje": "No se pudo leer resumen KPI operacional.",
            "error": str(exc),
        }


def _filtrar_recomendaciones_obsoletas(recomendaciones: list[str], kpi_ops_disponible: bool) -> list[str]:
    """Elimina recomendaciones de Fase 1 que quedan obsoletas si ya existe kpi_ops."""
    if not kpi_ops_disponible:
        return recomendaciones

    obsoletas = {
        "Fill Rate / OTIF requiere una fuente estructurada en Fase 2.",
        "Productividad requiere un resumen estructurado en logs para Fase 2.",
        "Pedidos pendientes siguen sin fuente estructurada en Fase 1.",
    }
    return [item for item in recomendaciones if str(item).strip() not in obsoletas]


def _resumen_contexto_ops() -> dict:
    """Arma el JSON consolidado para EgakatOpsBot sin ejecutar procesos productivos."""
    payload_pipeline, datos_de_ayer, ruta_pipeline = _resolver_payload_pipeline()
    resumen_pipeline = _resumen_pipeline_base(payload_pipeline)
    resumen_validacion = _resumen_validacion(payload_pipeline)
    resumen_nnss = _resumen_nnss_desde_logs()
    resumen_productividad = _resumen_productividad_desde_logs()
    resumen_fillrate = _resumen_fillrate_desde_logs()
    resumen_despacho = _resumen_despacho_desde_logs()
    resumen_kpi_ops = _resumen_kpi_ops_desde_logs()
    alertas = _resumen_alertas(payload_pipeline, datos_de_ayer=datos_de_ayer)

    fuentes = {
        "pipeline": str(ruta_pipeline) if ruta_pipeline else None,
        "nnss": resumen_nnss.get("_source"),
        "productividad": resumen_productividad.get("_source"),
        "fillrate": resumen_fillrate.get("_source"),
        "despacho": resumen_despacho.get("_source"),
        "kpi_ops": resumen_kpi_ops.get("fuente"),
    }

    recomendaciones: list[str] = []
    if alertas:
        recomendaciones.extend(alertas)
    if not resumen_nnss.get("disponible"):
        recomendaciones.append("NNSS aun no tiene una fuente consolidada mas alla de validaciones.")
    if not resumen_fillrate.get("disponible"):
        recomendaciones.append("Fill Rate / OTIF requiere una fuente estructurada en Fase 2.")
    if not resumen_productividad.get("disponible"):
        recomendaciones.append("Productividad requiere un resumen estructurado en logs para Fase 2.")
    if resumen_nnss.get("disponible") and not (resumen_nnss.get("pedidos_pendientes", {}) or {}).get("disponible"):
        recomendaciones.append("Pedidos pendientes siguen sin fuente estructurada en Fase 1.")
    if resumen_kpi_ops.get("disponible"):
        recomendaciones.extend((resumen_kpi_ops.get("recomendaciones") or [])[:5])
    recomendaciones = _filtrar_recomendaciones_obsoletas(
        recomendaciones,
        kpi_ops_disponible=bool(resumen_kpi_ops.get("disponible")),
    )

    return {
        "disponible": any([
            resumen_pipeline.get("disponible"),
            resumen_validacion.get("disponible"),
            resumen_nnss.get("disponible"),
            resumen_productividad.get("disponible"),
            resumen_fillrate.get("disponible"),
            resumen_despacho.get("disponible"),
            resumen_kpi_ops.get("disponible"),
        ]),
        "fecha_consulta": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "datos_de_ayer": datos_de_ayer,
        "fuentes": fuentes,
        "pipeline": resumen_pipeline.get("pipeline") if resumen_pipeline.get("disponible") else {"disponible": False},
        "validacion": resumen_validacion,
        "alertas": alertas,
        "nnss": {k: v for k, v in resumen_nnss.items() if k != "_source"},
        "productividad": {k: v for k, v in resumen_productividad.items() if k != "_source"},
        "fillrate": {k: v for k, v in resumen_fillrate.items() if k != "_source"},
        "despacho": {k: v for k, v in resumen_despacho.items() if k != "_source"},
        "kpi_ops": resumen_kpi_ops,
        "recomendaciones": _dedupe_textos(recomendaciones),
    }


# Endpoints

@app.route("/ops/pipeline/hoy")
def pipeline_hoy():
    """
    Estado del pipeline WMS del dia actual.
    Si no hay datos del dia, retorna los del dia anterior con flag datos_de_ayer=true.
    """
    try:
        payload, datos_de_ayer, _ = _resolver_payload_pipeline()
        if payload is None:
            return jsonify({
                "disponible": False,
                "mensaje": "No se encontraron datos del pipeline. "
                           "El pipeline aun no ha corrido hoy.",
            })

        resumen_pipeline = _resumen_pipeline_base(payload)
        return jsonify({
            "disponible": True,
            "datos_de_ayer": datos_de_ayer,
            "fecha": resumen_pipeline.get("fecha"),
            "hora_inicio": resumen_pipeline.get("hora_inicio"),
            "pipeline": resumen_pipeline.get("pipeline"),
            "validacion": _resumen_validacion(payload),
        })

    except Exception as e:
        print(f"[FALLO] /ops/pipeline/hoy: {traceback.format_exc()}")
        return jsonify({"error": str(e)}), 500


@app.route("/ops/contexto/resumen")
def contexto_resumen():
    """Contexto ejecutivo-operativo consolidado para EgakatOpsBot."""
    try:
        respuesta = _resumen_contexto_ops()
        return jsonify(respuesta)
    except Exception as e:
        print(f"[FALLO] /ops/contexto/resumen: {traceback.format_exc()}")
        return jsonify({"error": str(e)}), 500


@app.route("/ops/fillrate/resumen")
def fillrate_resumen():
    """Sprint 2 - pendiente de implementacion."""
    return jsonify({
        "disponible": False,
        "mensaje": "Fill Rate disponible en Sprint 2.",
    })


@app.route("/ops/productividad/resumen")
def productividad_resumen():
    """Sprint 3 - pendiente de implementacion."""
    return jsonify({
        "disponible": False,
        "mensaje": "Productividad disponible en Sprint 3.",
    })


@app.route("/health")
def health():
    """Healthcheck comprehensivo: datos, archivos JSON, LLMs."""
    hoy = _hoy()
    tiene_datos_hoy = (LOGDIR / f"resumen_ops_{hoy}.json").exists()
    tiene_kpi_ops = _ruta_resumen_kpi_ops_reciente() is not None

    checks = {
        "servicio": "api_operaciones WMS Egakat",
        "status": "ok",
        "datos_hoy": tiene_datos_hoy,
        "datos_kpi_ops": tiene_kpi_ops,
        "llm_disponible": False,
    }

    # LLM disponibilidad (Claude para análisis)
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        checks["llm_disponible"] = bool(client)
    except Exception as e:
        checks["status"] = "degraded"
        checks["llm_error"] = str(e)[:100]

    # Si no hay datos del día, estado degraded
    if not tiene_datos_hoy:
        checks["status"] = "degraded"
        checks["mensaje"] = "Sin datos pipeline hoy — ejecutar run_todos.py"

    checks["endpoints"] = [
        "/ops/pipeline/hoy", "/ops/contexto/resumen",
        "/ops/fillrate/resumen", "/ops/productividad/resumen",
        "/health"
    ]

    return jsonify(checks), 200 if checks["status"] == "ok" else 503


if __name__ == "__main__":
    # Validar configuración crítica al inicio
    if not os.getenv("API_OPS_SECRET"):
        print("[FALLO] API_OPS_SECRET no configurado en .env")
        print("        Generar secret: python -c 'import secrets; print(secrets.token_hex(16))'")
        sys.exit(1)

    port = int(os.getenv("API_OPS_PORT", 8086))
    print(f"[INFO] API Operaciones Egakat corriendo en http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
