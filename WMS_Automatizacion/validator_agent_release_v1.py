import sys
if sys.stdout:
    sys.stdout.reconfigure(encoding="utf-8")

import json
import os
import html
from datetime import datetime
from time import perf_counter
from importlib import util as importlib_util
from pathlib import Path, PureWindowsPath
from typing import Any, Dict, List, Optional, Tuple

from validation_utils import ensure_log_dir, safe_print

ROOT_DIR = Path(__file__).resolve().parent
LOG_DIR = ensure_log_dir()


# =====================================================================================
# Carga de modulos locales
# =====================================================================================

def _load_local_module(module_name: str, filename: str):
    module_path = ROOT_DIR / filename
    if not module_path.exists():
        raise FileNotFoundError(f"No se encontró el módulo requerido: {module_path}")

    spec = importlib_util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"No se pudo cargar spec para {module_path}")

    module = importlib_util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _norm_path(path: str) -> str:
    return os.path.normcase(os.path.normpath(str(path)))


# =====================================================================================
# Descubrimiento de archivos
# =====================================================================================

def _discover_structure_targets(structure_module) -> List[Tuple[Path, str]]:
    targets: List[Tuple[Path, str]] = []
    for fn_name in [
        "encontrar_stock_wms",
        "encontrar_staging",
        "encontrar_posiciones",
        "encontrar_clientes_ek_preparacion",
        "encontrar_clientes_ek_recepciones",
    ]:
        fn = getattr(structure_module, fn_name)
        targets.extend(fn())

    seen = set()
    unique_targets: List[Tuple[Path, str]] = []
    for path, schema in targets:
        key = (_norm_path(path), schema)
        if key not in seen:
            unique_targets.append((path, schema))
            seen.add(key)

    unique_targets.sort(key=lambda x: (x[1], str(x[0]).lower()))
    return unique_targets


def _discover_business_target_map(business_module) -> Dict[str, str]:
    targets: Dict[str, str] = {}
    for fn_name in [
        "encontrar_stock_wms",
        "encontrar_staging",
        "encontrar_clientes_ek_preparacion",
        "encontrar_clientes_ek_recepciones",
    ]:
        fn = getattr(business_module, fn_name)
        for path, schema in fn():
            targets[_norm_path(path)] = schema
    return targets


# =====================================================================================
# Helpers de consolidación
# =====================================================================================

def _file_modified_at(path: Path) -> Optional[str]:
    try:
        if path.exists():
            return datetime.fromtimestamp(path.stat().st_mtime).isoformat()
    except Exception:
        pass
    return None


def _merge_messages(prefix: str, messages: List[str]) -> List[str]:
    return [f"[{prefix}] {m}" for m in messages if m]


def _collect_consolidated_messages(structure_result: Dict[str, Any], business_result: Optional[Dict[str, Any]]) -> Tuple[List[str], List[str], List[str]]:
    errores: List[str] = []
    warnings: List[str] = []
    notas: List[str] = []

    errores.extend(_merge_messages("ESTRUCTURA", structure_result.get("errores", [])))
    warnings.extend(_merge_messages("ESTRUCTURA", structure_result.get("warnings", [])))
    notas.extend(_merge_messages("ESTRUCTURA", structure_result.get("notas", [])))

    if business_result:
        errores.extend(_merge_messages("NEGOCIO", business_result.get("errores", [])))
        warnings.extend(_merge_messages("NEGOCIO", business_result.get("warnings", [])))
        notas.extend(_merge_messages("NEGOCIO", business_result.get("notas", [])))

    return errores, warnings, notas


def _status_ranking(status: str) -> int:
    return {"OK": 0, "WARNING": 1, "PARCIAL": 2, "ERROR": 3}.get(status or "OK", 0)


def _build_summary(details: List[Dict[str, Any]]) -> Dict[str, int]:
    summary = {"OK": 0, "WARNING": 0, "PARCIAL": 0, "ERROR": 0}
    for row in details:
        state = row.get("estado_final", "OK")
        if state not in summary:
            summary[state] = 0
        summary[state] += 1
    return summary


def _build_warning_bullets(details: List[Dict[str, Any]], max_items: int = 5) -> Tuple[List[str], int]:
    bullets: List[str] = []
    zero_rows_count = 0

    friendly_map = {
        "descripcion_vacia": "Se detectaron registros con descripción vacía.",
        "fecha_alta_futura": "Se detectó una fecha futura fuera de tolerancia.",
        "articulo_vacio": "Se detectaron registros con artículo vacío.",
        "npedido_vacio": "Se detectaron registros con número de pedido vacío.",
        "cantidad_negativa": "Se detectaron cantidades negativas.",
    }

    for row in details:
        state = row.get("estado_final", "OK")
        if state not in {"WARNING", "PARCIAL", "ERROR"}:
            continue

        row_warnings = row.get("warnings", [])
        if any("sin registros" in str(msg).lower() for msg in row_warnings):
            zero_rows_count += 1

        for msg in row_warnings:
            lower = str(msg).lower()
            if "sin registros" in lower or "outlier" in lower or "umbral robusto" in lower:
                continue

            raw_path = str(row.get("archivo", ""))
            path_obj = PureWindowsPath(raw_path) if "\\" in raw_path or ":" in raw_path else Path(raw_path)
            archivo = path_obj.name
            parent = path_obj.parent.name if getattr(path_obj, "parent", None) else ""
            etiqueta = f"{parent} | {archivo}" if parent else archivo

            friendly = None
            for key, text in friendly_map.items():
                if key in lower:
                    friendly = text
                    break

            bullet = f"{etiqueta}: {friendly or str(msg)}"
            if bullet not in bullets:
                bullets.append(bullet)
            if len(bullets) >= max_items:
                return bullets, zero_rows_count

    return bullets, zero_rows_count


def build_email_subject(summary: Dict[str, int]) -> str:
    if summary.get("ERROR", 0) > 0:
        prefix = "WMS finalizado con errores"
    elif summary.get("PARCIAL", 0) > 0:
        prefix = "WMS finalizado con observaciones parciales"
    elif summary.get("WARNING", 0) > 0:
        prefix = "WMS finalizado sin errores críticos"
    else:
        prefix = "WMS finalizado OK"

    return (
        f"{prefix} | OK: {summary.get('OK', 0)} | "
        f"WARNING: {summary.get('WARNING', 0)} | "
        f"PARCIAL: {summary.get('PARCIAL', 0)} | "
        f"ERROR: {summary.get('ERROR', 0)}"
    )


def build_email_body(payload: Dict[str, Any]) -> str:
    summary = payload["resumen"]
    details = payload["detalles"]
    warnings_relevantes, zero_rows_count = _build_warning_bullets(details)

    if summary.get("ERROR", 0) > 0:
        conclusion = "La validación finalizó con errores. Se requiere revisión antes de considerar la corrida como cerrada."
    elif summary.get("PARCIAL", 0) > 0:
        conclusion = "La validación finalizó sin errores críticos, pero con observaciones parciales que conviene revisar."
    elif summary.get("WARNING", 0) > 0:
        conclusion = "La validación finalizó sin errores críticos. Las observaciones detectadas son no bloqueantes."
    else:
        conclusion = "La validación finalizó sin observaciones."

    lines: List[str] = []
    lines.append("Estimados,")
    lines.append("")
    lines.append("Se informa el cierre de la validación automática WMS del proceso ejecutado.")
    lines.append("")
    lines.append("Resultado general:")
    lines.append(f"- Archivos revisados: {payload['total_revisados']}")
    lines.append(f"- OK: {summary.get('OK', 0)}")
    lines.append(f"- WARNING: {summary.get('WARNING', 0)}")
    lines.append(f"- PARCIAL: {summary.get('PARCIAL', 0)}")
    lines.append(f"- ERROR: {summary.get('ERROR', 0)}")
    lines.append(f"- Duración total: {payload.get('duracion_total_legible', '0m 0s')}")
    lines.append("")
    lines.append("Conclusión:")
    lines.append(f"- {conclusion}")

    if zero_rows_count > 0:
        lines.append(
            f"- Se detectaron {zero_rows_count} archivo(s) sin registros, clasificados como advertencia esperable y no bloqueante."
        )

    if warnings_relevantes:
        lines.append("")
        lines.append("Observaciones relevantes:")
        for bullet in warnings_relevantes:
            lines.append(f"- {bullet}")

    lines.append("")
    lines.append("Adjunto sugerido:")
    lines.append("- Resumen consolidado TXT")
    lines.append("")
    lines.append("El detalle consolidado JSON se recomienda dejarlo solo como respaldo interno para revisión técnica.")
    lines.append("")
    lines.append("Notificación automática generada por Sistema Automatizado WMS Egakat.")

    return "\n".join(lines)


def _schema_label(schema: str) -> str:
    mapping = {
        "stock_wms": "Stock WMS Semanal",
        "staging_estandar": "Staging IN/OUT",
        "posiciones": "Consulta de Posiciones",
        "pedidos_preparados": "Pedidos Preparados",
        "recepciones_recibidas": "Recepciones Recibidas",
    }
    return mapping.get(schema, schema)


def _status_badge(status: str) -> str:
    mapping = {
        "OK": "✅ OK",
        "WARNING": "🟡 WARNING",
        "PARCIAL": "🟠 PARCIAL",
        "ERROR": "🔴 ERROR",
        "NO APLICA": "⚪ NO APLICA",
        "NO_EJECUTADO": "⚪ NO EJECUTADO",
    }
    return mapping.get(status or "OK", f"⚪ {status}")


def _status_colors(status: str) -> Dict[str, str]:
    palette = {
        "OK": {"bg": "#2fb463", "soft": "#edf4ee", "text": "#1d5f37"},
        "WARNING": {"bg": "#d6a21b", "soft": "#f5efd8", "text": "#7a5600"},
        "PARCIAL": {"bg": "#f08a24", "soft": "#fff0e2", "text": "#8a4300"},
        "ERROR": {"bg": "#d64545", "soft": "#fdeaea", "text": "#7a1f1f"},
        "NO APLICA": {"bg": "#6b7280", "soft": "#f3f4f6", "text": "#374151"},
        "NO_EJECUTADO": {"bg": "#6b7280", "soft": "#f3f4f6", "text": "#374151"},
    }
    return palette.get(status or "OK", palette["OK"])


def _build_schema_rows(details: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for row in details:
        grouped.setdefault(row.get("schema", ""), []).append(row)

    rows: List[Dict[str, Any]] = []
    for schema, items in grouped.items():
        final_state = "OK"
        for item in items:
            if _status_ranking(item.get("estado_final", "OK")) > _status_ranking(final_state):
                final_state = item.get("estado_final", "OK")

        warning_count = sum(1 for item in items if item.get("estado_final") == "WARNING")
        partial_count = sum(1 for item in items if item.get("estado_final") == "PARCIAL")
        error_count = sum(1 for item in items if item.get("estado_final") == "ERROR")
        duration_seconds = sum(float(item.get("duracion_segundos", 0.0) or 0.0) for item in items)
        rows.append({
            "schema": schema,
            "label": _schema_label(schema),
            "estado": final_state,
            "archivos": len(items),
            "warning_count": warning_count,
            "partial_count": partial_count,
            "error_count": error_count,
            "duracion_segundos": duration_seconds,
        })

    rows.sort(key=lambda r: (-_status_ranking(r["estado"]), r["label"].lower()))
    return rows


def _html_escape(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def _format_duration(seconds: float) -> str:
    total = int(round(seconds or 0))
    minutes, secs = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    if hours > 0:
        return f"{hours}h {minutes}m {secs}s"
    return f"{minutes}m {secs}s"


def build_email_html(payload: Dict[str, Any]) -> str:
    summary = payload["resumen"]
    details = payload["detalles"]
    warnings_relevantes, zero_rows_count = _build_warning_bullets(details)
    schema_rows = _build_schema_rows(details)

    if summary.get("ERROR", 0) > 0:
        overall_state = "ERROR"
        subtitle = "La validación terminó con errores que requieren revisión antes de considerar la corrida cerrada."
    elif summary.get("PARCIAL", 0) > 0:
        overall_state = "PARCIAL"
        subtitle = "La validación terminó sin errores críticos, pero con observaciones parciales que conviene revisar."
    elif summary.get("WARNING", 0) > 0:
        overall_state = "WARNING"
        subtitle = "La validación terminó sin errores críticos. Las observaciones detectadas son no bloqueantes."
    else:
        overall_state = "OK"
        subtitle = "La validación terminó sin observaciones."

    colors = _status_colors(overall_state)
    fecha_iso = payload.get("fecha_ejecucion", "")[:10]
    fecha = f"{fecha_iso[8:10]}/{fecha_iso[5:7]}/{fecha_iso[0:4]}" if len(fecha_iso) >= 10 else fecha_iso

    kpis = [
        ("Archivos", payload.get("total_revisados", 0)),
        ("OK", summary.get("OK", 0)),
        ("Warning", summary.get("WARNING", 0)),
        ("Parcial", summary.get("PARCIAL", 0)),
        ("Error", summary.get("ERROR", 0)),
        ("Duración", payload.get("duracion_total_legible", "0m 0s")),
    ]
    kpi_html = "".join(
        [
            (
                "<div style='display:inline-block;min-width:112px;margin:0 8px 8px 0;padding:10px 14px;"
                "border-radius:10px;background:#ffffff;border:1px solid #d8e3dc;'>"
                f"<div style='font-size:11px;color:#667085;line-height:1.2;'>{_html_escape(label)}</div>"
                f"<div style='font-size:20px;font-weight:700;color:#1f2937;line-height:1.2;'>{_html_escape(value)}</div>"
                "</div>"
            )
            for label, value in kpis
        ]
    )

    table_html = "".join(
        [
            (
                "<tr>"
                f"<td style='padding:10px 12px;border-bottom:1px solid #e5e7eb;color:#111827;'>{_html_escape(row['label'])}</td>"
                f"<td style='padding:10px 12px;border-bottom:1px solid #e5e7eb;color:#111827;text-align:center;'>{row['archivos']}</td>"
                f"<td style='padding:10px 12px;border-bottom:1px solid #e5e7eb;color:#111827;text-align:center;'>{_html_escape(_status_badge(row['estado']))}</td>"
                f"<td style='padding:10px 12px;border-bottom:1px solid #e5e7eb;color:#111827;text-align:center;'>{row['warning_count']}</td>"
                f"<td style='padding:10px 12px;border-bottom:1px solid #e5e7eb;color:#111827;text-align:center;'>{_html_escape(_format_duration(row['duracion_segundos']))}</td>"
                "</tr>"
            )
            for row in schema_rows
        ]
    )

    observaciones_html = ""
    if zero_rows_count > 0 or warnings_relevantes:
        items = []
        if zero_rows_count > 0:
            items.append(
                f"Se detectaron <strong>{zero_rows_count}</strong> archivo(s) sin registros, clasificados como advertencia esperable y no bloqueante."
            )
        for bullet in warnings_relevantes:
            items.append(_html_escape(bullet))
        lis = "".join([f"<li style='margin:0 0 8px 0;'>{item}</li>" for item in items])
        observaciones_html = (
            "<div style='margin-top:18px;padding:16px 18px;background:#fafafa;border:1px solid #e5e7eb;border-radius:12px;'>"
            "<div style='font-size:14px;font-weight:700;color:#111827;margin-bottom:10px;'>Observaciones relevantes</div>"
            f"<ul style='margin:0;padding-left:18px;color:#374151;font-size:13px;line-height:1.45;'>{lis}</ul>"
            "</div>"
        )

    html_body = (
        "<!DOCTYPE html><html><body style='margin:0;padding:24px;background:#f3f4f6;font-family:Segoe UI, Arial, sans-serif;color:#111827;'>"
        "<div style='max-width:760px;margin:0 auto;background:#ffffff;border:1px solid #d1d5db;border-radius:14px;overflow:hidden;'>"
        f"<div style='background:{colors['bg']};padding:18px 22px;color:#ffffff;'>"
        "<div style='font-size:30px;line-height:1;margin-bottom:8px;'>📋</div>"
        "<div style='font-size:30px;font-weight:700;line-height:1.1;'>WMS Egakat — Validación Diaria</div>"
        f"<div style='margin-top:8px;font-size:16px;font-weight:700;opacity:0.98;'>{_html_escape(_status_badge(overall_state))} &nbsp;|&nbsp; {fecha}</div>"
        f"<div style='margin-top:6px;font-size:13px;line-height:1.45;opacity:0.96;'>{_html_escape(subtitle)}</div>"
        "</div>"
        f"<div style='padding:20px 22px;background:{colors['soft']};border-bottom:1px solid #e5e7eb;'>{kpi_html}</div>"
        "<div style='padding:20px 22px;'>"
        "<table role='presentation' style='width:100%;border-collapse:collapse;font-size:13px;'>"
        "<thead><tr>"
        "<th style='background:#2f455c;color:#ffffff;text-align:left;padding:11px 12px;'>Reporte</th>"
        "<th style='background:#2f455c;color:#ffffff;text-align:center;padding:11px 12px;'>Archivos</th>"
        "<th style='background:#2f455c;color:#ffffff;text-align:center;padding:11px 12px;'>Estado</th>"
        "<th style='background:#2f455c;color:#ffffff;text-align:center;padding:11px 12px;'>Warnings</th>"
        "<th style='background:#2f455c;color:#ffffff;text-align:center;padding:11px 12px;'>Duración</th>"
        "</tr></thead><tbody>"
        f"{table_html}"
        "</tbody></table>"
        f"{observaciones_html}"
        "<div style='margin-top:18px;padding-top:14px;border-top:1px solid #e5e7eb;color:#6b7280;font-size:12px;line-height:1.45;'>"
        "<div>Adjunto sugerido: resumen consolidado TXT.</div>"
        "<div style='margin-top:4px;'>El detalle consolidado JSON se recomienda dejarlo como respaldo interno para revisión técnica.</div>"
        "<div style='margin-top:6px;'>Notificación automática generada por Sistema Automatizado WMS Egakat.</div>"
        "</div></div></div></body></html>"
    )
    return html_body


def _json_default(obj: Any):
    if isinstance(obj, Path):
        return str(obj)
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def save_total_json(payload: Dict[str, Any], timestamp: str) -> Path:
    out = LOG_DIR / f"validacion_total_{timestamp}.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, default=_json_default)
    return out


def save_total_txt(payload: Dict[str, Any], timestamp: str) -> Path:
    out = LOG_DIR / f"validacion_total_{timestamp}.txt"
    summary = payload["resumen"]
    details = payload["detalles"]

    lines: List[str] = []
    lines.append("RESUMEN VALIDACION TOTAL WMS")
    lines.append("=" * 110)
    lines.append(f"Fecha ejecucion         : {payload['fecha_ejecucion']}")
    lines.append(f"Modulo estructura       : {payload['modulo_estructura']}")
    lines.append(f"Modulo negocio          : {payload['modulo_negocio']}")
    lines.append(f"Total revisados         : {payload['total_revisados']}")
    lines.append(f"OK                      : {summary.get('OK', 0)}")
    lines.append(f"WARNING                 : {summary.get('WARNING', 0)}")
    lines.append(f"PARCIAL                 : {summary.get('PARCIAL', 0)}")
    lines.append(f"ERROR                   : {summary.get('ERROR', 0)}")
    lines.append(f"Duración total          : {payload.get('duracion_total_legible', '')}")
    lines.append("")

    for row in details:
        lines.append(f"[{row['estado_final']}] {row['schema']} | {row['archivo']}")
        lines.append(f"   Últ. modif.           : {row.get('ultima_modificacion') or ''}")
        lines.append(f"   Estructura            : {row['estructura']['estado']}")
        lines.append(f"   Negocio               : {row['negocio']['estado'] if row.get('negocio') else 'NO APLICA'}")
        lines.append(f"   Header row            : {row['estructura'].get('header_row_1_based')}")
        lines.append(f"   Filas estructura      : {row['estructura'].get('row_count')}")
        lines.append(f"   Columnas estructura   : {row['estructura'].get('column_count')}")
        if row.get('negocio'):
            lines.append(f"   Filas negocio         : {row['negocio'].get('row_count')}")

        for note in row.get('notas', []):
            lines.append(f"   - NOTA: {note}")
        for warn in row.get('warnings', []):
            lines.append(f"   - WARNING: {warn}")
        for err in row.get('errores', []):
            lines.append(f"   - ERROR: {err}")
        lines.append("")

    lines.append("=" * 110)
    lines.append("VISTA PREVIA CORREO CONCLUSION")
    lines.append("=" * 110)
    lines.append(f"Asunto: {payload['email_preview']['subject']}")
    lines.append("")
    lines.extend(payload['email_preview']['body_text'].splitlines())
    lines.append("")

    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return out


def save_email_preview(payload: Dict[str, Any], timestamp: str) -> Tuple[Path, Path]:
    out_txt = LOG_DIR / f"correo_validacion_total_{timestamp}.txt"
    out_html = LOG_DIR / f"correo_validacion_total_{timestamp}.html"
    with open(out_txt, "w", encoding="utf-8") as f:
        f.write(f"Asunto: {payload['email_preview']['subject']}\n\n")
        f.write(payload['email_preview']['body_text'])
    with open(out_html, "w", encoding="utf-8") as f:
        f.write(payload['email_preview']['body_html'])
    return out_txt, out_html


# =====================================================================================
# Orquestación principal
# =====================================================================================

def run_validation() -> Dict[str, Any]:
    structure_module = _load_local_module("validator_estructura_local", "validator_estructura.py")
    business_module = _load_local_module("validator_negocio_local", "validator_negocio.py")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    started_at = perf_counter()
    details: List[Dict[str, Any]] = []

    structure_targets = _discover_structure_targets(structure_module)
    business_target_map = _discover_business_target_map(business_module)

    safe_print("=" * 70)
    safe_print("VALIDADOR TOTAL WMS - release_v1")
    safe_print("=" * 70)
    safe_print(f"Archivos detectados para validar: {len(structure_targets)}")

    for path, structure_schema in structure_targets:
        file_started_at = perf_counter()
        path_str = str(path)
        structure_result = structure_module.validate_structure(path_str, structure_schema)

        business_result: Optional[Dict[str, Any]] = None
        final_state = structure_result.get("estado", "OK")

        business_schema = business_target_map.get(_norm_path(path_str))
        if business_schema and structure_result.get("estado") != "ERROR":
            business_result = business_module.validate_business(path_str, business_schema)
            final_state = business_module.merge_structure_business_states(
                structure_result.get("estado", "OK"),
                business_result.get("estado", "OK"),
            )
        elif business_schema and structure_result.get("estado") == "ERROR":
            business_result = {
                "estado": "NO_EJECUTADO",
                "errores": [],
                "warnings": ["Validación de negocio no ejecutada porque estructura terminó en ERROR."],
                "notas": [],
                "row_count": None,
                "column_count": None,
                "header_row_1_based": structure_result.get("header_row_1_based"),
                "sheet_used": structure_result.get("sheet_used"),
                "hallazgos": [],
            }

        errores, warnings, notas = _collect_consolidated_messages(structure_result, business_result)
        file_duration = perf_counter() - file_started_at

        detail = {
            "archivo": path_str,
            "archivo_existe": Path(path_str).exists(),
            "ultima_modificacion": _file_modified_at(Path(path_str)),
            "schema": structure_schema,
            "estado_final": final_state,
            "estructura": structure_result,
            "negocio": business_result,
            "errores": errores,
            "warnings": warnings,
            "notas": notas,
            "duracion_segundos": round(file_duration, 4),
        }
        details.append(detail)

        safe_print(f"[{final_state}] {structure_schema} | {Path(path_str).name}")

    details.sort(key=lambda r: (-_status_ranking(r["estado_final"]), r["schema"], r["archivo"].lower()))
    summary = _build_summary(details)
    total_duration = perf_counter() - started_at

    payload: Dict[str, Any] = {
        "fecha_ejecucion": datetime.now().isoformat(),
        "modulo_estructura": "validator_estructura.py",
        "modulo_negocio": "validator_negocio.py",
        "total_revisados": len(details),
        "duracion_total_segundos": round(total_duration, 4),
        "duracion_total_legible": _format_duration(total_duration),
        "resumen": summary,
        "detalles": details,
    }

    payload["email_preview"] = {
        "subject": build_email_subject(summary),
        "body_text": build_email_body(payload),
        "body_html": build_email_html(payload),
    }

    json_path = save_total_json(payload, ts)
    txt_path = save_total_txt(payload, ts)
    email_txt_path, email_html_path = save_email_preview(payload, ts)

    safe_print(f"JSON: {json_path}")
    safe_print(f"TXT : {txt_path}")
    safe_print(f"MAIL TXT : {email_txt_path}")
    safe_print(f"MAIL HTML: {email_html_path}")

    return {
        "summary": summary,
        "details": details,
        "json_path": str(json_path),
        "txt_path": str(txt_path),
        "email_preview_txt_path": str(email_txt_path),
        "email_preview_html_path": str(email_html_path),
        "email_preview": payload["email_preview"],
        "payload": payload,
    }


if __name__ == "__main__":
    output = run_validation()
    summary = output["summary"]
    safe_print(
        f"Resumen -> Total: {sum(summary.values())} | OK: {summary.get('OK', 0)} | "
        f"WARNING: {summary.get('WARNING', 0)} | PARCIAL: {summary.get('PARCIAL', 0)} | "
        f"ERROR: {summary.get('ERROR', 0)}"
    )
