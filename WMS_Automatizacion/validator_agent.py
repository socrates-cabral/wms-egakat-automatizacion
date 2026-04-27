import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
import json
import importlib.util


# ============================================================
# VALIDADOR AGENTE WMS EGAKAT
# v2.0 — Integración estructura + negocio
#
# Objetivo:
# - Orquestar la validación completa por archivo
# - Correr estructura primero y negocio después
# - Consolidar un estado final por archivo
# - Mantener capas desacopladas para no romper el sistema actual
#
# Uso manual:
#   py validator_agent.py
#
# Notas:
# - Si negocio no aplica para un schema (ej. posiciones), se conserva solo estructura.
# - Si estructura falla en ERROR, negocio no corre.
# - Si estructura queda WARNING por archivo vacío, negocio puede correr y decidir,
#   pero si el dataset está vacío, negocio devolverá WARNING no bloqueante.
# ============================================================

LOG_DIR = Path(r"C:\ClaudeWork\logs\validaciones")
LOG_DIR.mkdir(parents=True, exist_ok=True)

BASE_DIR = Path(__file__).resolve().parent

STRUCTURE_MODULE_CANDIDATES = [
    "validator_estructura.py",
    "validator_estructura_v5.py",
    "validator_estructura_v4.py",
    "validator_estructura_v3.py",
]

BUSINESS_MODULE_CANDIDATES = [
    "validator_negocio.py",
    "validator_negocio_v1_4.py",
    "validator_negocio_v1_3.py",
    "validator_negocio_v1_2.py",
    "validator_negocio_v1_1.py",
    "validator_negocio_v1.py",
]

BUSINESS_SUPPORTED_SCHEMAS = {
    "stock_wms",
    "staging_estandar",
    "staging_unilever",
    "pedidos_preparados",
    "recepciones_recibidas",
}


# ============================================================
# CARGA DINAMICA DE MODULOS
# ============================================================

def _resolve_first_existing(base_dir: Path, candidates: List[str]) -> Path:
    for name in candidates:
        p = base_dir / name
        if p.exists():
            return p
    raise FileNotFoundError(
        f"No se encontró ninguno de los archivos esperados: {', '.join(candidates)}"
    )



def _load_module(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"No se pudo crear spec para {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ============================================================
# HELPERS
# ============================================================

def safe_file_mtime(path: Path) -> Optional[str]:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds")
    except Exception:
        return None



def ranking_state(state: str) -> int:
    ranking = {
        "OK": 0,
        "OK ↻": 0,
        "WARNING": 1,
        "PARCIAL": 2,
        "ERROR": 3,
    }
    return ranking.get(state, 3)



def worst_state(a: str, b: str) -> str:
    reverse = {0: "OK", 1: "WARNING", 2: "PARCIAL", 3: "ERROR"}
    return reverse[max(ranking_state(a), ranking_state(b))]



def summarize_counts(results: List[Dict[str, Any]]) -> Dict[str, int]:
    buckets = {"OK": 0, "WARNING": 0, "PARCIAL": 0, "ERROR": 0}
    for r in results:
        state = r.get("estado_final", "ERROR")
        if state not in buckets:
            state = "ERROR"
        buckets[state] += 1
    return buckets



def append_prefixed(messages: List[str], prefix: str) -> List[str]:
    return [f"{prefix}{m}" for m in messages]



def business_should_run(schema_name: str, structure_result: Dict[str, Any]) -> Tuple[bool, str]:
    if schema_name not in BUSINESS_SUPPORTED_SCHEMAS:
        return False, "Schema sin reglas de negocio en esta fase."

    structure_state = structure_result.get("estado", "ERROR")
    if structure_state == "ERROR":
        return False, "Negocio omitido porque estructura falló con ERROR."

    return True, "OK"


# ============================================================
# DESCUBRIMIENTO DE ARCHIVOS
# ============================================================

def discover_all_targets(structure_module) -> List[Tuple[Path, str]]:
    results: List[Tuple[Path, str]] = []

    for fn_name in [
        "encontrar_stock_wms",
        "encontrar_staging",
        "encontrar_posiciones",
        "encontrar_clientes_ek_preparacion",
        "encontrar_clientes_ek_recepciones",
    ]:
        fn = getattr(structure_module, fn_name, None)
        if callable(fn):
            partial = fn()
            if partial:
                results.extend(partial)

    # Deduplicación defensiva por archivo + schema
    seen = set()
    deduped: List[Tuple[Path, str]] = []
    for path, schema in results:
        key = (str(path), schema)
        if key not in seen:
            seen.add(key)
            deduped.append((path, schema))

    return deduped


# ============================================================
# EJECUCIÓN
# ============================================================

def validate_one_file(path: Path, schema_name: str, structure_module, business_module) -> Dict[str, Any]:
    file_exists = path.exists()
    file_mtime = safe_file_mtime(path) if file_exists else None

    structure_result = structure_module.validate_structure(str(path), schema_name)

    run_business, reason = business_should_run(schema_name, structure_result)
    business_result: Optional[Dict[str, Any]] = None

    if run_business:
        business_result = business_module.validate_business(str(path), schema_name)
        if hasattr(business_module, "merge_structure_business_states"):
            estado_final = business_module.merge_structure_business_states(
                structure_result.get("estado", "ERROR"),
                business_result.get("estado", "ERROR"),
            )
        else:
            estado_final = worst_state(
                structure_result.get("estado", "ERROR"),
                business_result.get("estado", "ERROR"),
            )
    else:
        estado_final = structure_result.get("estado", "ERROR")

    consolidated = {
        "archivo": str(path),
        "archivo_existe": file_exists,
        "ultima_modificacion": file_mtime,
        "schema": schema_name,
        "estado_final": estado_final,
        "estructura": {
            "estado": structure_result.get("estado"),
            "sheet_used": structure_result.get("sheet_used"),
            "header_row_1_based": structure_result.get("header_row_1_based"),
            "row_count": structure_result.get("row_count"),
            "column_count": structure_result.get("column_count"),
            "errores": structure_result.get("errores", []),
            "warnings": structure_result.get("warnings", []),
            "notas": structure_result.get("notas", []),
            "actual_columns": structure_result.get("actual_columns", []),
        },
        "negocio": None,
        "errores": [],
        "warnings": [],
        "notas": [],
    }

    consolidated["errores"].extend(append_prefixed(structure_result.get("errores", []), "[ESTRUCTURA] "))
    consolidated["warnings"].extend(append_prefixed(structure_result.get("warnings", []), "[ESTRUCTURA] "))
    consolidated["notas"].extend(append_prefixed(structure_result.get("notas", []), "[ESTRUCTURA] "))

    if business_result is not None:
        consolidated["negocio"] = {
            "estado": business_result.get("estado"),
            "dataset_group": business_result.get("dataset_group"),
            "sheet_used": business_result.get("sheet_used"),
            "header_row_1_based": business_result.get("header_row_1_based"),
            "row_count": business_result.get("row_count"),
            "column_count": business_result.get("column_count"),
            "errores": business_result.get("errores", []),
            "warnings": business_result.get("warnings", []),
            "notas": business_result.get("notas", []),
            "hallazgos": business_result.get("hallazgos", []),
            "actual_columns": business_result.get("actual_columns", []),
        }
        consolidated["errores"].extend(append_prefixed(business_result.get("errores", []), "[NEGOCIO] "))
        consolidated["warnings"].extend(append_prefixed(business_result.get("warnings", []), "[NEGOCIO] "))
        consolidated["notas"].extend(append_prefixed(business_result.get("notas", []), "[NEGOCIO] "))
    else:
        consolidated["notas"].append(f"[NEGOCIO] {reason}")

    return consolidated



def run_all() -> Tuple[List[Dict[str, Any]], Path, Path]:
    structure_path = _resolve_first_existing(BASE_DIR, STRUCTURE_MODULE_CANDIDATES)
    business_path = _resolve_first_existing(BASE_DIR, BUSINESS_MODULE_CANDIDATES)

    structure_module = _load_module("validator_estructura_runtime", structure_path)
    business_module = _load_module("validator_negocio_runtime", business_path)

    targets = discover_all_targets(structure_module)
    results: List[Dict[str, Any]] = []

    for path, schema_name in targets:
        results.append(validate_one_file(path, schema_name, structure_module, business_module))

    txt_path = save_results_txt(results, structure_path.name, business_path.name)
    json_path = save_results_json(results, structure_path.name, business_path.name)
    return results, txt_path, json_path


# ============================================================
# EXPORTACIÓN
# ============================================================

def save_results_txt(results: List[Dict[str, Any]], structure_module_name: str, business_module_name: str) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = LOG_DIR / f"validacion_total_{ts}.txt"

    counts = summarize_counts(results)

    with open(out, "w", encoding="utf-8") as f:
        f.write("RESUMEN VALIDACION TOTAL WMS\n")
        f.write("=" * 110 + "\n")
        f.write(f"Fecha ejecucion         : {datetime.now().isoformat()}\n")
        f.write(f"Modulo estructura       : {structure_module_name}\n")
        f.write(f"Modulo negocio          : {business_module_name}\n")
        f.write(f"Total revisados         : {len(results)}\n")
        f.write(f"OK                      : {counts['OK']}\n")
        f.write(f"WARNING                 : {counts['WARNING']}\n")
        f.write(f"PARCIAL                 : {counts['PARCIAL']}\n")
        f.write(f"ERROR                   : {counts['ERROR']}\n")
        f.write("\n")

        for r in results:
            f.write(f"[{r['estado_final']}] {r['schema']} | {r['archivo']}\n")
            f.write(f"   Últ. modif.           : {r.get('ultima_modificacion') or '-'}\n")
            f.write(f"   Estructura            : {r['estructura'].get('estado', '-')}\n")
            if r.get("negocio") is not None:
                f.write(f"   Negocio               : {r['negocio'].get('estado', '-')}\n")
            else:
                f.write("   Negocio               : NO APLICA / OMITIDO\n")

            f.write(f"   Header row            : {r['estructura'].get('header_row_1_based', '-') }\n")
            f.write(f"   Filas estructura      : {r['estructura'].get('row_count', '-') }\n")
            f.write(f"   Columnas estructura   : {r['estructura'].get('column_count', '-') }\n")
            if r.get("negocio") is not None:
                f.write(f"   Filas negocio         : {r['negocio'].get('row_count', '-') }\n")

            for note in r.get("notas", []):
                f.write(f"   - NOTA: {note}\n")
            for warn in r.get("warnings", []):
                f.write(f"   - WARNING: {warn}\n")
            for err in r.get("errores", []):
                f.write(f"   - ERROR: {err}\n")

            f.write("\n")

    return out



def save_results_json(results: List[Dict[str, Any]], structure_module_name: str, business_module_name: str) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = LOG_DIR / f"validacion_total_{ts}.json"

    payload = {
        "fecha_ejecucion": datetime.now().isoformat(),
        "modulo_estructura": structure_module_name,
        "modulo_negocio": business_module_name,
        "total_revisados": len(results),
        "resumen": summarize_counts(results),
        "detalles": results,
    }

    with open(out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    return out


# ============================================================
# MAIN
# ============================================================

def main() -> None:
    results, txt_path, json_path = run_all()
    counts = summarize_counts(results)
    print("=" * 110)
    print("VALIDACION TOTAL WMS — COMPLETADA")
    print(f"Total revisados : {len(results)}")
    print(f"OK              : {counts['OK']}")
    print(f"WARNING         : {counts['WARNING']}")
    print(f"PARCIAL         : {counts['PARCIAL']}")
    print(f"ERROR           : {counts['ERROR']}")
    print(f"TXT             : {txt_path}")
    print(f"JSON            : {json_path}")
    print("=" * 110)


if __name__ == "__main__":
    main()
