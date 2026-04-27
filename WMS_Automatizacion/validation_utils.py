import sys
if sys.stdout:
    sys.stdout.reconfigure(encoding="utf-8")

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List


LOG_DIR = Path(r"C:\ClaudeWork\logs\validaciones")


def ensure_log_dir() -> Path:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    return LOG_DIR


def now_str() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def now_iso() -> str:
    return datetime.now().isoformat()


def safe_text(text: str) -> str:
    replacements = {
        "✅": "[OK]",
        "⚠️": "[WARN]",
        "❌": "[FALLO]",
        "→": "->",
        "✓": "OK",
        "✗": "ERR",
        "▶": ">>",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def safe_print(text: str) -> None:
    print(safe_text(text), flush=True)


def _normalize_row(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "modulo": row.get("modulo"),
        "submodulo": row.get("submodulo"),
        "archivo": row.get("archivo"),
        "tipo": row.get("tipo"),
        "status": row.get("status"),
        "exists": row.get("exists"),
        "size_bytes": row.get("size_bytes"),
        "modified_at": row.get("modified_at"),
        "row_count": row.get("row_count"),
        "sheet_used": row.get("sheet_used"),
        "missing_columns": " | ".join(row.get("missing_columns", [])),
        "observaciones": " | ".join(row.get("observaciones", [])),
    }


def save_json(summary: Dict[str, Any], results: List[Dict[str, Any]], timestamp: str) -> Path:
    ensure_log_dir()
    path = LOG_DIR / f"validacion_{timestamp}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "results": results}, f, ensure_ascii=False, indent=2)
    return path


def save_csv(results: Iterable[Dict[str, Any]], timestamp: str) -> Path:
    ensure_log_dir()
    path = LOG_DIR / f"validacion_{timestamp}.csv"
    fieldnames = [
        "modulo", "submodulo", "archivo", "tipo", "status", "exists",
        "size_bytes", "modified_at", "row_count", "sheet_used",
        "missing_columns", "observaciones",
    ]
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in results:
            writer.writerow(_normalize_row(row))
    return path


def save_txt(summary: Dict[str, Any], results: List[Dict[str, Any]], timestamp: str) -> Path:
    ensure_log_dir()
    path = LOG_DIR / f"resumen_validacion_{timestamp}.txt"
    lines = [
        "RESUMEN VALIDACION WMS",
        "=" * 80,
        f"Fecha ejecucion : {summary['timestamp']}",
        f"Total revisados  : {summary['total']}",
        f"OK              : {summary['ok']}",
        f"WARNING         : {summary['warning']}",
        f"ERROR           : {summary['error']}",
        "",
    ]
    for row in results:
        lines.append(f"[{row['status']}] {row['modulo']} | {row.get('submodulo', '')}")
        lines.append(f"   Archivo: {row.get('archivo', '')}")
        if row.get("observaciones"):
            for obs in row["observaciones"]:
                lines.append(f"   - {safe_text(str(obs))}")
        lines.append("")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return path
