"""
Base del modulo Productividad.

Estado actual:
- Catalogo historico confirmado
- Regla de rango oficial centralizada
- Validacion del Excel descargado implementada
- Navegacion WMS pendiente de confirmacion runtime

No se improvisan selectores ni labels no confirmados.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

from productividad_config import CLIENTS, RANGE_END_TIME, RANGE_START_TIME
from productividad_utils import (
    build_catalog_table_rows,
    build_log_path,
    build_reporting_window,
    find_client,
    format_window,
    log,
    validate_downloaded_workbook,
)


if sys.stdout:
    sys.stdout.reconfigure(encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Base del modulo Productividad WMS Egakat")
    parser.add_argument("--list-catalog", action="store_true", help="Imprime el catalogo configurado y termina.")
    parser.add_argument(
        "--validate-file",
        help="Valida un Excel ya descargado contra el catalogo y las reglas historicas.",
    )
    parser.add_argument("--cd", help="CD esperado para validacion, por ejemplo 'CD PUDAHUEL'.")
    parser.add_argument("--alias", help="Alias historico esperado, por ejemplo 'MovRuno'.")
    parser.add_argument(
        "--mode",
        choices=("current", "closed"),
        default="current",
        help="Regla de rango a evaluar.",
    )
    parser.add_argument("--year", type=int, default=datetime.now().year, help="Ano objetivo del proceso.")
    parser.add_argument("--month", type=int, default=datetime.now().month, help="Mes objetivo del proceso.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Muestra rango y clientes activos sin intentar navegacion WMS.",
    )
    return parser.parse_args()


def print_catalog() -> None:
    print("CD | Alias archivo | Empresa WMS | Deposito origen | Carpeta destino | Active")
    for row in build_catalog_table_rows(CLIENTS):
        print(row)


def run_validation(args: argparse.Namespace, log_path: Path) -> int:
    if not args.cd or not args.alias:
        raise RuntimeError("--validate-file requiere tambien --cd y --alias.")

    client = find_client(args.cd, args.alias)
    result = validate_downloaded_workbook(Path(args.validate_file), client, args.year, args.month)

    log(f"[VALIDACION] Target oficial: {result.target_path}", log_path)
    if result.inspection:
        log(
            (
                "[VALIDACION] Interno -> "
                f"cd={result.inspection.internal_cd}, "
                f"empresa={result.inspection.internal_company}, "
                f"scope={result.inspection.internal_scope}, "
                f"hoja={result.inspection.sheet_name}, "
                f"con_datos={result.inspection.has_data_rows}"
            ),
            log_path,
        )

    for warning in result.warnings:
        log(f"[WARN] {warning}", log_path)

    for error in result.critical_errors:
        log(f"[CRITICO] {error}", log_path)

    if result.ok:
        status = "VALIDO_VACIO" if result.is_empty_valid else "VALIDO_CON_DATOS"
        log(f"[OK] Validacion completada: {status}", log_path)
        return 0

    log("[FALLO] Validacion rechazada. No debe sobrescribirse el archivo oficial.", log_path)
    return 2


def main() -> int:
    args = parse_args()
    log_path = build_log_path()
    window = build_reporting_window(
        mode=args.mode,
        target_year=args.year,
        target_month=args.month,
    )

    log(
        (
            "[CONFIG] Regla oficial de rango -> "
            f"desde={RANGE_START_TIME}, hasta={RANGE_END_TIME}, ventana={format_window(window)}"
        ),
        log_path,
    )

    if args.list_catalog:
        print_catalog()
        return 0

    if args.validate_file:
        return run_validation(args, log_path)

    if args.dry_run:
        log("[DRY-RUN] Catalogo activo cargado. La navegacion WMS aun requiere confirmacion runtime.", log_path)
        for client in [client for client in CLIENTS if client.get("active")]:
            log(
                (
                    "[CLIENTE] "
                    f"{client['cd']} | {client['alias_archivo']} | "
                    f"{client['empresa_wms']} | deposito={client['deposito_wms_origen']}"
                ),
                log_path,
            )
        log(
            "[PENDIENTE] Confirmar selectores, labels y ruta exacta del reporte de Productividad en WMS.",
            log_path,
        )
        return 0

    raise NotImplementedError(
        "La navegacion y descarga WMS quedan pendientes hasta confirmar selectores y labels en runtime."
    )


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except NotImplementedError as exc:
        print(f"[PENDIENTE] {exc}", flush=True)
        raise SystemExit(3)
