"""
Base del modulo Productividad.

Estado actual:
- Catalogo historico confirmado
- Regla de rango oficial centralizada
- Validacion del Excel descargado implementada
- Navegacion WMS confirmada en staging para clientes livianos

No se improvisan selectores ni labels no confirmados.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

from productividad_config import (
    CLIENTS,
    CONTROLLED_LIGHTWEIGHT_CLIENT,
    CONTROLLED_LIGHTWEIGHT_CLIENTS,
    CONTROLLED_HEAVY_CLIENTS,
    CONTROLLED_EXECUTION_CLIENTS,
    DOWNLOAD_DIR,
    PRODUCTION_LIGHTWEIGHT_CLIENTS,
    RANGE_END_TIME,
    RANGE_START_TIME,
    WMS_LOGIN_URL,
)
from productividad_utils import (
    build_catalog_table_rows,
    build_operational_chunks,
    build_log_path,
    build_reporting_window,
    compare_runtime_to_historical,
    consolidate_normalized_chunks,
    create_sharepoint_remote_backup,
    audit_chunk_coverage,
    build_productividad_closure_email,
    count_normalized_rows,
    save_productividad_email_artifacts,
    find_latest_normalized_candidate,
    find_client,
    format_dt,
    format_wms_date,
    format_window,
    get_sharepoint_file_state,
    load_azure_graph_module,
    log,
    log_structural_validation,
    normalize_legacy_html_to_xlsx,
    prepare_sharepoint_publish_plan,
    quarantine_file,
    resolve_sharepoint_remote_state,
    save_legacy_html_as_raw_xlsx,
    send_html_notification,
    upload_file_to_sharepoint,
    validate_structural_xlsx,
    validate_downloaded_workbook,
    verify_sharepoint_upload,
)


if sys.stdout:
    sys.stdout.reconfigure(encoding="utf-8")

_LOGS_DIR = Path(__file__).resolve().parent / "logs"
_LOCKFILE = _LOGS_DIR / "productividad_run.lock"


def _pid_alive(pid: int) -> bool:
    try:
        import subprocess
        result = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
            capture_output=True, text=True, timeout=5,
        )
        return str(pid) in result.stdout
    except Exception:
        return False


def _acquire_lock(log_path: Path) -> bool:
    _LOGS_DIR.mkdir(exist_ok=True)
    if _LOCKFILE.exists():
        try:
            pid = int(_LOCKFILE.read_text().strip())
            if _pid_alive(pid):
                log(f"[ERROR] Ya hay una instancia corriendo (PID {pid}). Abortando.", log_path)
                return False
        except Exception:
            pass
        _LOCKFILE.unlink(missing_ok=True)
    _LOCKFILE.write_text(str(os.getpid()))
    return True


def _release_lock() -> None:
    try:
        _LOCKFILE.unlink(missing_ok=True)
    except Exception:
        pass


def _checkpoint_path() -> Path:
    return _LOGS_DIR / f"productividad_checkpoint_{datetime.now().strftime('%Y%m%d')}.json"


def _load_checkpoint() -> set:
    path = _checkpoint_path()
    if not path.exists():
        return set()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return set(data.get("completados", []))
    except Exception:
        return set()


def _save_checkpoint(client_key: str, rows: int = -1) -> None:
    path = _checkpoint_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except Exception:
        data = {}
    completados = set(data.get("completados", []))
    completados.add(client_key)
    rows_map: dict = data.get("rows", {})
    if rows >= 0:
        rows_map[client_key] = rows
    path.write_text(
        json.dumps({"completados": sorted(completados), "rows": rows_map}, ensure_ascii=False),
        encoding="utf-8",
    )


def _checkpoint_rows(client_key: str) -> int:
    """Retorna el conteo de filas guardado en checkpoint, o -1 si no existe."""
    path = _checkpoint_path()
    if not path.exists():
        return -1
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return int(data.get("rows", {}).get(client_key, -1))
    except Exception:
        return -1


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
    parser.add_argument(
        "--controlled-daikin",
        action="store_true",
        help="Ejecuta una descarga real controlada en staging para DAIKIN/QUILICURA.",
    )
    parser.add_argument(
        "--controlled-client",
        choices=tuple(CONTROLLED_LIGHTWEIGHT_CLIENTS.keys()),
        help="Ejecuta una descarga real controlada en staging para un cliente liviano configurado.",
    )
    parser.add_argument(
        "--controlled-heavy-client",
        choices=tuple(CONTROLLED_HEAVY_CLIENTS.keys()),
        help="Ejecuta una descarga heavy/chunked en staging para un cliente especial configurado.",
    )
    parser.add_argument(
        "--sharepoint-client",
        choices=tuple(CONTROLLED_EXECUTION_CLIENTS.keys()),
        help="Prepara o ejecuta escritura oficial controlada a SharePoint para un cliente controlado.",
    )
    parser.add_argument(
        "--source-file",
        help="Archivo .xlsx normalizado en staging que se usara como candidato de escritura oficial.",
    )
    parser.add_argument(
        "--commit",
        action="store_true",
        help="Ejecuta la escritura oficial en SharePoint. Sin este flag, el flujo corre en dry-run.",
    )
    parser.add_argument(
        "--production-lightweight",
        action="store_true",
        help="Ejecuta publicacion acotada para clientes livianos habilitados, sin bloquear el lote por fallos individuales.",
    )
    parser.add_argument(
        "--daily-run",
        action="store_true",
        help="Ejecuta la corrida diaria completa del modulo: staging, SharePoint y correo final.",
    )
    parser.add_argument(
        "--production-clients",
        help="Lista separada por comas para limitar la publicacion acotada a clientes livianos especificos.",
    )
    parser.add_argument(
        "--final-email",
        action="store_true",
        help="Genera el correo ejecutivo final del modulo Productividad y guarda preview en logs.",
    )
    parser.add_argument(
        "--send-email",
        action="store_true",
        help="Envia el correo final del modulo Productividad. Requiere --final-email.",
    )
    parser.add_argument(
        "--email-to",
        help="Override de destinatarios para esta corrida (separados por ;). Util para pruebas.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Ignora el checkpoint diario y fuerza la descarga aunque ya se haya ejecutado hoy.",
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

    log(f"[VALIDACION] Target oficial ({result.target_mode}): {result.target_path}", log_path)
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


def _select_option_by_label(page, label: str, field_name: str, log_path: Path) -> str:
    selects = page.locator("select")
    observed_options = []
    for index in range(selects.count()):
        locator = selects.nth(index)
        options = [" ".join(text.split()).strip() for text in locator.locator("option").all_inner_texts()]
        observed_options.append(f"select[index={index}] -> {options}")
        if label in options:
            locator.select_option(label=label)
            selector = f"select[index={index}]"
            log(f"[OK] Selector {field_name}: {selector} -> {label}", log_path)
            return selector
    for observed in observed_options:
        log(f"[DEBUG] Opciones disponibles {field_name}: {observed}", log_path)
    raise RuntimeError(f"No se encontro selector para {field_name} con opcion '{label}'.")


def _wait_for_option(page, label: str, field_name: str, log_path: Path,
                     poll_ms: int = 500, timeout_ms: int = 15_000) -> None:
    """Polling activo: espera hasta que 'label' aparezca en algún <select>.
    Reemplaza wait_for_timeout fijo cuando el dropdown depende de AJAX.
    """
    import time
    deadline = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < deadline:
        selects = page.locator("select")
        for index in range(selects.count()):
            options = [
                " ".join(t.split()).strip()
                for t in selects.nth(index).locator("option").all_inner_texts()
            ]
            if label in options:
                log(f"[OK] Opcion '{label}' disponible en select[index={index}] tras espera AJAX.", log_path)
                return
        page.wait_for_timeout(poll_ms)
    log(f"[WARN] Timeout {timeout_ms}ms esperando '{label}' en {field_name}. Se intentara igual.", log_path)


def _fill_first(page, selectors, value: str, field_name: str, log_path: Path) -> str:
    for selector in selectors:
        locator = page.locator(selector)
        if locator.count() == 0:
            continue
        locator.first.fill("")
        locator.first.fill(value)
        locator.first.press("Tab")
        log(f"[OK] Campo {field_name}: {selector} -> {value}", log_path)
        return selector
    raise RuntimeError(f"No se encontro campo para {field_name}.")


def _load_wms_credentials() -> tuple[str, str]:
    load_dotenv(Path(r"C:\ClaudeWork\.env"))
    wms_user = os.getenv("WMS_USUARIO") or "SCABRAL"
    wms_password = os.getenv("WMS_PASSWORD") or os.getenv("WMS_CLAVE") or ""
    if not wms_password:
        raise RuntimeError("No se encontro credencial WMS en .env para la prueba controlada.")
    return wms_user, wms_password


def _download_runtime_export(
    *,
    client: dict,
    from_date: str,
    to_date: str,
    from_time: str,
    to_time: str,
    log_path: Path,
    alias_prefix: str,
    chunk_label: str | None = None,
) -> Path:
    wms_user, wms_password = _load_wms_credentials()
    html_name = f"{alias_prefix}_html_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xls"
    html_path = Path(DOWNLOAD_DIR) / html_name

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, slow_mo=0)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()
        page.set_default_timeout(60_000)

        try:
            page.goto(WMS_LOGIN_URL, wait_until="load", timeout=60_000)
            page.fill("input[name='vUSR']", wms_user)
            page.fill("input[name='vPASSWORD']", wms_password)
            page.click("input[name='BUTTON3']")
            page.wait_for_load_state("load", timeout=60_000)
            page.wait_for_timeout(1500)
            log("[OK] Login WMS completado.", log_path)

            _select_option_by_label(page, client["deposito_wms_origen"], "deposito inicial", log_path)
            page.click("input[value='Aceptar']")
            page.wait_for_load_state("load", timeout=60_000)
            page.wait_for_timeout(1500)
            log("[OK] Deposito inicial confirmado.", log_path)

            page.click("text=Procesos WMS")
            page.wait_for_load_state("load", timeout=60_000)
            page.wait_for_timeout(1000)
            log("[OK] Menu Procesos WMS cargado.", log_path)

            page.get_by_role("link", name="Movimientos por Operación").click()
            page.wait_for_load_state("load", timeout=60_000)
            page.wait_for_timeout(1500)
            log("[OK] Pantalla Movimientos por Operacion cargada.", log_path)

            _select_option_by_label(page, client["deposito_wms_origen"], "deposito", log_path)
            page.wait_for_timeout(1500)
            _select_option_by_label(page, client["empresa_wms"], "empresa", log_path)
            page.wait_for_timeout(2000)  # WMS recarga tipo-operacion y cuenta por AJAX tras cambio de empresa
            _select_option_by_label(page, "ORDEN DE PREP. C/STOCK", "tipo de operacion", log_path)
            _wait_for_option(page, "Stock Físico", "cuenta", log_path, poll_ms=500, timeout_ms=45_000)
            _select_option_by_label(page, "Stock Físico", "cuenta", log_path)
            page.wait_for_timeout(500)

            _fill_first(page, ["input[name='vFECDESDE']"], from_date, "desde fecha", log_path)
            _fill_first(page, ["input[name='vFECHASTA']"], to_date, "hasta fecha", log_path)
            _fill_first(page, ["input[name='vHORADES']"], from_time, "desde hora", log_path)
            _fill_first(page, ["input[name='vHORAHAS']"], to_time, "hasta hora", log_path)

            page.click("input[name='CONFIRMAR']")
            # Espera dinámica: WMS termina todas las requests antes de intentar el Excel.
            # Fallback a 30s fijo si networkidle no resuelve en 120s.
            try:
                page.wait_for_load_state("networkidle", timeout=120_000)
            except Exception:
                pass
            # Mínimo 15s independiente de networkidle: WMS puede tardar en habilitar el botón Excel.
            page.wait_for_timeout(15_000)
            if chunk_label:
                log(f"[OK] Consulta ejecutada para {chunk_label}.", log_path)
            else:
                log("[OK] Consulta ejecutada.", log_path)

            download_timeout_ms = client.get("download_timeout_ms", 180_000)

            if client.get("heavy_client"):
                # Clientes heavy (DERCO): WMS sirve el Excel via URL directa, no via evento download.
                # Interceptamos el request post-click y descargamos directo (patrón staging_descarga).
                xls_urls: list[str] = []
                debug_requests: list[str] = []

                def _on_request(request: object) -> None:
                    url: str = request.url  # type: ignore[attr-defined]
                    debug_requests.append(url)
                    if any(x in url.lower() for x in (".xls", "excel", "salidaexcel", "download", "export")):
                        xls_urls.append(url)

                context.on("request", _on_request)
                page.locator("img#W0155SALIDAEXCEL").click()

                for _ in range(600):  # poll hasta 60s
                    if xls_urls:
                        break
                    page.wait_for_timeout(100)

                context.remove_listener("request", _on_request)

                if not xls_urls:
                    for debug_url in debug_requests[-15:]:
                        log(f"[DEBUG][EXCEL] Request post-click: {debug_url}", log_path)
                    raise RuntimeError("No se capturó URL del Excel tras 60s — WMS no generó el archivo.")

                url_excel = xls_urls[-1]
                log(f"[OK] URL Excel capturada via intercepción: {url_excel}", log_path)
                response = page.request.get(url_excel, timeout=download_timeout_ms)
                with open(str(html_path), "wb") as f:
                    f.write(response.body())
            else:
                with page.expect_download(timeout=download_timeout_ms) as dl_info:
                    page.locator("img#W0155SALIDAEXCEL").click()
                download = dl_info.value
                download.save_as(str(html_path))

            log(f"[OK] Export HTML recibido desde WMS: {html_path}", log_path)
            return html_path
        finally:
            context.close()
            browser.close()


def _process_runtime_export(
    *,
    client: dict,
    historical_path: Path,
    html_path: Path,
    alias_prefix: str,
    log_path: Path,
    target_year: int,
    target_month: int,
    keep_html_on_failure: bool = True,
) -> dict:
    staged_path = save_legacy_html_as_raw_xlsx(html_path, alias_prefix, log_path)
    validation = validate_downloaded_workbook(staged_path, client, target_year, target_month)
    comparison = compare_runtime_to_historical(staged_path, historical_path)
    raw_structural = validate_structural_xlsx(staged_path, historical_path, client, "raw")

    log(
        f"[CONTROLADO] Formato detectado: {validation.inspection.source_format if validation.inspection else 'desconocido'}",
        log_path,
    )
    log(f"[CONTROLADO] Archivo vacio valido: {validation.is_empty_valid}", log_path)
    log(f"[CONTROLADO] Coincidencia exacta cabecera vs historico: {comparison.headers_match_exact}", log_path)
    log(
        f"[CONTROLADO] Coincidencia normalizada cabecera vs historico: {comparison.headers_match_normalized}",
        log_path,
    )
    log(f"[CONTROLADO] Normalizacion viable: {comparison.normalized_viable}", log_path)
    log_structural_validation(raw_structural, log_path)
    for note in comparison.notes:
        log(f"[INFO] {note}", log_path)
    for warning in validation.warnings:
        log(f"[WARN] {warning}", log_path)
    for error in validation.critical_errors:
        log(f"[CRITICO] {error}", log_path)

    if validation.critical_errors or not raw_structural.ok:
        quarantine_file(staged_path, "validacion_critica", log_path)
        if html_path.exists() and not keep_html_on_failure:
            html_path.unlink()
            log("[OK] Archivo HTML transitorio eliminado tras validacion critica.", log_path)
        return {
            "ok": False,
            "raw_path": staged_path,
            "html_path": html_path,
            "normalized_path": None,
            "validation": validation,
            "comparison": comparison,
            "raw_structural": raw_structural,
            "normalized_structural": None,
            "normalized_comparison": None,
        }

    if not comparison.normalized_viable:
        quarantine_file(staged_path, "normalizacion_no_segura", log_path)
        return {
            "ok": False,
            "raw_path": staged_path,
            "html_path": html_path,
            "normalized_path": None,
            "validation": validation,
            "comparison": comparison,
            "raw_structural": raw_structural,
            "normalized_structural": None,
            "normalized_comparison": None,
        }

    normalized = normalize_legacy_html_to_xlsx(html_path, historical_path, alias_prefix, log_path)
    log(f"[OK] Normalizacion staging completada: {normalized['normalized_path']}", log_path)
    normalized_comparison = compare_runtime_to_historical(normalized["normalized_path"], historical_path)
    normalized_structural = validate_structural_xlsx(
        normalized["normalized_path"], historical_path, client, "normalized"
    )
    log(
        f"[CONTROLADO] Normalizado exacto vs historico: {normalized_comparison.headers_match_exact}",
        log_path,
    )
    log_structural_validation(normalized_structural, log_path)
    if not normalized_comparison.headers_match_exact or not normalized_structural.ok:
        quarantine_file(normalized["normalized_path"], "normalizado_no_exacto", log_path)
        return {
            "ok": False,
            "raw_path": staged_path,
            "html_path": html_path,
            "normalized_path": normalized["normalized_path"],
            "validation": validation,
            "comparison": comparison,
            "raw_structural": raw_structural,
            "normalized_structural": normalized_structural,
            "normalized_comparison": normalized_comparison,
        }

    if html_path.exists():
        html_path.unlink()
        log("[OK] Archivo HTML transitorio eliminado tras generar los .xlsx de staging.", log_path)

    return {
        "ok": True,
        "raw_path": staged_path,
        "html_path": html_path,
        "normalized_path": normalized["normalized_path"],
        "validation": validation,
        "comparison": comparison,
        "raw_structural": raw_structural,
        "normalized_structural": normalized_structural,
        "normalized_comparison": normalized_comparison,
    }


def run_controlled_lightweight(client_key: str, log_path: Path) -> int:
    client = CONTROLLED_LIGHTWEIGHT_CLIENTS[client_key]
    historical_path = Path(client["historical_reference"])

    log(
        (
            "[CONTROLADO] Inicio descarga real en staging para "
            f"{client['empresa_wms']} / {client['deposito_wms_origen']}."
        ),
        log_path,
    )
    log("[CONTROLADO] Esta corrida no escribe al historico oficial.", log_path)
    html_path = _download_runtime_export(
        client=client,
        from_date=client["test_from"],
        to_date=client["test_to"],
        from_time=RANGE_START_TIME,
        to_time=RANGE_END_TIME,
        log_path=log_path,
        alias_prefix=client["alias_archivo"],
    )
    result = _process_runtime_export(
        client=client,
        historical_path=historical_path,
        html_path=html_path,
        alias_prefix=client["alias_archivo"],
        log_path=log_path,
        target_year=2026,
        target_month=4,
        keep_html_on_failure=False,
    )

    if not result["ok"]:
        log("[FALLO] La descarga controlada no paso validacion critica/estructural.", log_path)
        return 2

    log(
        (
            "[CONTROLADO] Fin de corrida en staging para "
            f"{client['empresa_wms']}. No se realizo overwrite del historico oficial."
        ),
        log_path,
    )
    return 0


def run_runtime_lightweight_client(
    *,
    client_key: str,
    log_path: Path,
    from_date: str,
    to_date: str,
    from_time: str,
    to_time: str,
    target_year: int,
    target_month: int,
) -> int:
    client = CONTROLLED_LIGHTWEIGHT_CLIENTS[client_key]
    historical_path = Path(client["historical_reference"])

    log(
        (
            "[DIARIO] Inicio descarga real en staging para "
            f"{client['empresa_wms']} / {client['deposito_wms_origen']} | "
            f"rango={from_date} {from_time} -> {to_date} {to_time}"
        ),
        log_path,
    )
    MAX_DOWNLOAD_ATTEMPTS = 3
    RETRY_WAIT_S = 30
    result = None
    for attempt in range(1, MAX_DOWNLOAD_ATTEMPTS + 1):
        try:
            html_path = _download_runtime_export(
                client=client,
                from_date=from_date,
                to_date=to_date,
                from_time=from_time,
                to_time=to_time,
                log_path=log_path,
                alias_prefix=client["alias_archivo"],
            )
            result = _process_runtime_export(
                client=client,
                historical_path=historical_path,
                html_path=html_path,
                alias_prefix=client["alias_archivo"],
                log_path=log_path,
                target_year=target_year,
                target_month=target_month,
                keep_html_on_failure=False,
            )
            break
        except Exception as exc:
            exc_str = str(exc)
            is_retriable = (
                "WMS_EMPRESA_TODAS" in exc_str
                or "TimeoutError" in type(exc).__name__
                or "Timeout" in exc_str
                or "No se encontro selector para" in exc_str  # WMS lento: selector no renderizado aún
            )
            if is_retriable and attempt < MAX_DOWNLOAD_ATTEMPTS:
                log(f"[WARN][DIARIO] Intento {attempt}/{MAX_DOWNLOAD_ATTEMPTS} fallo (retriable): {exc}. Reintentando en {RETRY_WAIT_S}s...", log_path)
                time.sleep(RETRY_WAIT_S)
            elif not is_retriable:
                log(f"[FALLO][DIARIO] Error no retriable en intento {attempt}: {exc}", log_path)
                return 2
            else:
                log(f"[FALLO][DIARIO] Fallo tras {MAX_DOWNLOAD_ATTEMPTS} intentos: {exc}", log_path)
                return 2
    if result is None or not result["ok"]:
        log("[FALLO][DIARIO] La corrida staging no paso validacion critica/estructural.", log_path)
        return 2

    log(
        (
            "[DIARIO] Candidato staging listo para publicacion: "
            f"{result['normalized_path']}"
        ),
        log_path,
    )
    return 0


def _run_derco_chunk_attempt(
    *,
    client: dict,
    historical_path: Path,
    chunk,
    log_path: Path,
    target_year: int,
    target_month: int,
) -> dict:
    alias_prefix = f"chunk_{client['alias_archivo']}_{chunk.chunk_id}"
    log(
        (
            f"[DERCO][{chunk.chunk_id}] Descarga chunk "
            f"{format_dt(chunk.start_dt)} -> {format_dt(chunk.end_dt)}"
        ),
        log_path,
    )
    html_path = _download_runtime_export(
        client=client,
        from_date=format_wms_date(chunk.start_dt),
        to_date=format_wms_date(chunk.end_dt),
        from_time=chunk.start_dt.strftime("%H:%M:%S"),
        to_time=chunk.end_dt.strftime("%H:%M:%S"),
        log_path=log_path,
        alias_prefix=alias_prefix,
        chunk_label=chunk.chunk_id,
    )
    result = _process_runtime_export(
        client=client,
        historical_path=historical_path,
        html_path=html_path,
        alias_prefix=alias_prefix,
        log_path=log_path,
        target_year=target_year,
        target_month=target_month,
        keep_html_on_failure=True,
    )
    result["chunk"] = chunk
    return result


def _run_derco_chunk_tree(
    *,
    client: dict,
    historical_path: Path,
    chunk,
    chunk_sizes: tuple[int, ...],
    chunk_size_index: int,
    log_path: Path,
    target_year: int,
    target_month: int,
) -> tuple[list[dict], dict]:
    retry_attempts = int(client.get("chunk_retry_attempts", 2))
    retry_pause_seconds = int(client.get("chunk_retry_pause_seconds", 60))
    had_retry = False
    had_split = False
    last_failure: dict | None = None

    for attempt in range(1, retry_attempts + 1):
        log(
            (
                f"[DERCO][{chunk.chunk_id}] Intento {attempt}/{retry_attempts} | "
                f"rango={format_dt(chunk.start_dt)} -> {format_dt(chunk.end_dt)}"
            ),
            log_path,
        )
        try:
            result = _run_derco_chunk_attempt(
                client=client,
                historical_path=historical_path,
                chunk=chunk,
                log_path=log_path,
                target_year=target_year,
                target_month=target_month,
            )
        except Exception as exc:
            result = {
                "ok": False,
                "chunk": chunk,
                "issues": [f"Excepcion runtime: {exc}"],
                "normalized_path": None,
                "validation": None,
            }

        if result["ok"]:
            status = "REINTENTO_OK" if had_retry else "OK"
            log(f"[DERCO][{chunk.chunk_id}] Estado chunk: {status}", log_path)
            return [result], {"ok": True, "had_retry": had_retry, "had_split": had_split, "status": status}

        had_retry = had_retry or attempt > 1
        last_failure = result
        issue_messages = result.get("issues") or []
        for issue in issue_messages:
            log(f"[CRITICO][DERCO][{chunk.chunk_id}] {issue}", log_path)
        if attempt < retry_attempts:
            log(
                f"[DERCO][{chunk.chunk_id}] Reintento en {retry_pause_seconds}s por fallo del chunk.",
                log_path,
            )
            time.sleep(retry_pause_seconds)

    if chunk_size_index + 1 < len(chunk_sizes):
        next_chunk_days = chunk_sizes[chunk_size_index + 1]
        subchunks = build_operational_chunks(
            start_dt=chunk.start_dt,
            end_dt=chunk.end_dt,
            chunk_days=next_chunk_days,
            prefix=f"{chunk.chunk_id}S",
            level=chunk.level + 1,
        )
        if len(subchunks) > 1:
            had_split = True
            audit = audit_chunk_coverage(subchunks, expected_start=chunk.start_dt, expected_end=chunk.end_dt)
            for issue in audit.issues:
                log(f"[CRITICO][DERCO][{chunk.chunk_id}] {issue}", log_path)
            if not audit.ok:
                return [], {
                    "ok": False,
                    "had_retry": True,
                    "had_split": True,
                    "status": "REINTENTO_FALLO",
                    "issues": audit.issues,
                }

            log(
                (
                    f"[DERCO][{chunk.chunk_id}] Subdivision aplicada -> {len(subchunks)} subchunks "
                    f"de {next_chunk_days} dia(s) operativos."
                ),
                log_path,
            )
            collected_results: list[dict] = []
            child_failed = False
            child_retry = had_retry
            child_split = True
            for subchunk in subchunks:
                sub_results, sub_meta = _run_derco_chunk_tree(
                    client=client,
                    historical_path=historical_path,
                    chunk=subchunk,
                    chunk_sizes=chunk_sizes,
                    chunk_size_index=chunk_size_index + 1,
                    log_path=log_path,
                    target_year=target_year,
                    target_month=target_month,
                )
                collected_results.extend(sub_results)
                child_retry = child_retry or sub_meta.get("had_retry", False)
                child_split = child_split or sub_meta.get("had_split", False)
                if not sub_meta.get("ok"):
                    child_failed = True
            if child_failed:
                return collected_results, {
                    "ok": False,
                    "had_retry": child_retry,
                    "had_split": child_split,
                    "status": "REINTENTO_PARCIAL",
                    "issues": ["Cobertura incompleta tras subdivision progresiva del chunk."],
                }
            return collected_results, {
                "ok": True,
                "had_retry": child_retry,
                "had_split": child_split,
                "status": "REINTENTO_OK",
            }

    return [], {
        "ok": False,
        "had_retry": had_retry,
        "had_split": had_split,
        "status": "REINTENTO_FALLO" if had_retry else "FALLO",
        "issues": (last_failure or {}).get("issues", ["No fue posible completar el chunk heavy."]),
    }


def run_controlled_heavy_derco(args: argparse.Namespace, log_path: Path) -> int:
    client = CONTROLLED_HEAVY_CLIENTS["derco"]
    historical_path = Path(client["historical_reference"])
    window = build_reporting_window(mode=args.mode, target_year=args.year, target_month=args.month)
    chunk_sizes = tuple(client.get("chunk_days", (7, 3, 1)))
    initial_chunks = build_operational_chunks(
        start_dt=window.from_dt,
        end_dt=window.to_dt,
        chunk_days=chunk_sizes[0],
        prefix="DERCO",
        level=0,
    )
    coverage = audit_chunk_coverage(initial_chunks, expected_start=window.from_dt, expected_end=window.to_dt)

    log(
        (
            "[DERCO] Inicio dry-run heavy/chunked en staging | "
            f"ventana={format_window(window)} | chunk_sizes={chunk_sizes}"
        ),
        log_path,
    )
    for issue in coverage.issues:
        log(f"[CRITICO][DERCO] {issue}", log_path)
    if not coverage.ok:
        log("[FALLO][DERCO] La planificacion inicial de chunks no cubre exactamente el rango solicitado.", log_path)
        return 2

    for chunk in initial_chunks:
        log(
            (
                f"[DERCO] Chunk planificado {chunk.chunk_id}: "
                f"{format_dt(chunk.start_dt)} -> {format_dt(chunk.end_dt)}"
            ),
            log_path,
        )

    collected_results: list[dict] = []
    had_retry_or_split = False
    failed = False
    final_status = "OK"
    for chunk in initial_chunks:
        chunk_results, meta = _run_derco_chunk_tree(
            client=client,
            historical_path=historical_path,
            chunk=chunk,
            chunk_sizes=chunk_sizes,
            chunk_size_index=0,
            log_path=log_path,
            target_year=args.year,
            target_month=args.month,
        )
        collected_results.extend(chunk_results)
        had_retry_or_split = had_retry_or_split or meta.get("had_retry", False) or meta.get("had_split", False)
        if not meta.get("ok"):
            failed = True
            final_status = meta.get("status", "FALLO")
            for issue in meta.get("issues", []):
                log(f"[CRITICO][DERCO] {issue}", log_path)

    normalized_paths = [result["normalized_path"] for result in collected_results if result.get("normalized_path")]
    consolidated = consolidate_normalized_chunks(
        chunk_paths=normalized_paths,
        historical_path=historical_path,
        target_alias=client["alias_archivo"],
        log_path=log_path,
    )
    if not consolidated.ok or not consolidated.consolidated_path:
        failed = True
        final_status = "REINTENTO_PARCIAL" if had_retry_or_split else "FALLO"
        for issue in consolidated.issues:
            log(f"[CRITICO][DERCO][CONSOLIDADO] {issue}", log_path)
        log("[FALLO][DERCO] No se pudo construir consolidado final seguro.", log_path)
        return 2

    log(
        (
            "[DERCO][CONSOLIDADO] Archivo final staging: "
            f"{consolidated.consolidated_path} | chunks={consolidated.total_chunks} "
            f"con_datos={consolidated.chunks_with_rows} vacios={consolidated.empty_chunks} "
            f"filas={consolidated.unique_rows} duplicados_descartados={consolidated.duplicate_rows_removed}"
        ),
        log_path,
    )

    validation = validate_downloaded_workbook(consolidated.consolidated_path, client, args.year, args.month)
    comparison = compare_runtime_to_historical(consolidated.consolidated_path, historical_path)
    structural = validate_structural_xlsx(consolidated.consolidated_path, historical_path, client, "normalized")
    log_structural_validation(structural, log_path)
    for warning in validation.warnings:
        log(f"[WARN][DERCO][CONSOLIDADO] {warning}", log_path)
    for error in validation.critical_errors:
        log(f"[CRITICO][DERCO][CONSOLIDADO] {error}", log_path)
    if not comparison.headers_match_exact:
        log("[CRITICO][DERCO][CONSOLIDADO] El consolidado no coincide exactamente con el layout historico.", log_path)
        failed = True

    if validation.critical_errors or not structural.ok:
        quarantine_file(consolidated.consolidated_path, "derco_consolidado_invalido", log_path)
        failed = True

    if failed:
        final_status = "REINTENTO_PARCIAL" if had_retry_or_split else final_status
        log(f"[FALLO][DERCO] Dry-run heavy incompleto. Estado final: {final_status}", log_path)
        return 2

    final_status = "REINTENTO_OK" if had_retry_or_split else "OK"
    log(f"[OK][DERCO] Dry-run heavy completado. Estado final: {final_status}", log_path)
    log(f"[OK][DERCO] Candidato consolidado listo para SharePoint: {consolidated.consolidated_path}", log_path)
    return 0


def run_controlled_daikin(log_path: Path) -> int:
    return run_controlled_lightweight("daikin", log_path)


def run_sharepoint_publish_for_client(
    *,
    client_key: str,
    log_path: Path,
    target_year: int,
    target_month: int,
    commit: bool,
    source_file: Path | None = None,
) -> int:
    client = CONTROLLED_EXECUTION_CLIENTS[client_key]
    historical_path = Path(client["historical_reference"])
    candidate_path = source_file if source_file else find_latest_normalized_candidate(client["alias_archivo"])
    if candidate_path is None:
        raise RuntimeError(
            f"No se encontro candidato normalizado en staging para {client['alias_archivo']}. "
            "Usa --source-file o genera primero una corrida controlada."
        )

    log(
        (
            "[SP] Inicio publicacion controlada a SharePoint para "
            f"{client['empresa_wms']} | modo={'COMMIT' if commit else 'DRY-RUN'}."
        ),
        log_path,
    )
    log(f"[SP] Staging local candidato: {candidate_path}", log_path)

    plan = prepare_sharepoint_publish_plan(
        client_key=client_key,
        client=client,
        candidate_path=candidate_path,
        historical_path=historical_path,
        target_year=target_year,
        target_month=target_month,
    )

    log(f"[SP] Destino oficial SharePoint: {plan.sharepoint_target_path}", log_path)
    if plan.remote_backup_target_path:
        log(f"[SP] Politica backup remoto previa: {plan.remote_backup_target_path}", log_path)
    for warning in plan.warnings:
        log(f"[WARN][SP] {warning}", log_path)
    for issue in plan.issues:
        log(f"[CRITICO][SP] {issue}", log_path)

    if not plan.ready:
        log("[BLOQUEADO][SP] El candidato no paso el gating previo a publicacion.", log_path)
        return 2

    try:
        azure_graph = load_azure_graph_module()
        token = azure_graph.get_token()
        drive_id = azure_graph.get_drive_id(token)
        plan = resolve_sharepoint_remote_state(plan, token=token, drive_id=drive_id)
        remote_before = get_sharepoint_file_state(token, drive_id, plan.sharepoint_folder_path, plan.sharepoint_filename)
    except Exception as exc:
        log(f"[FALLO][SP] No se pudo resolver el estado remoto en SharePoint: {exc}", log_path)
        return 2

    log(
        (
            "[SP] Estado remoto: "
            f"{'EXISTE y seria overwrite controlado' if plan.remote_exists else 'NO existe, seria alta inicial'}"
        ),
        log_path,
    )

    if not commit:
        log("[SP][DRY-RUN] Validaciones OK. No se ejecuto escritura remota.", log_path)
        return 0

    try:
        backup_state = None
        if remote_before.exists:
            backup_state = create_sharepoint_remote_backup(
                token=token,
                drive_id=drive_id,
                client=client,
                plan=plan,
                target_year=target_year,
                target_month=target_month,
            )
            if backup_state:
                log(
                    (
                        "[SP] Backup remoto creado antes del overwrite: "
                        f"{plan.remote_backup_target_path} | size={backup_state.size}"
                    ),
                    log_path,
                )

        ok = upload_file_to_sharepoint(
            token=token,
            drive_id=drive_id,
            folder_path=plan.sharepoint_folder_path,
            local_path=plan.local_candidate,
            remote_name=plan.sharepoint_filename,
        )
    except Exception as exc:
        log(f"[FALLO][SP] Error durante la escritura oficial a SharePoint: {exc}", log_path)
        return 2

    if not ok:
        log("[FALLO][SP] La subida a SharePoint retorno False.", log_path)
        return 2

    try:
        verification = verify_sharepoint_upload(
            token=token,
            drive_id=drive_id,
            client=client,
            plan=plan,
            historical_path=historical_path,
            target_year=target_year,
            target_month=target_month,
            remote_before=remote_before,
            backup_state=backup_state,
        )
    except Exception as exc:
        log(f"[FALLO][SP] Error durante la verificacion post-subida: {exc}", log_path)
        return 2

    log(
        (
            "[SP] Verificacion post-subida: "
            f"remote_size={verification.remote_size} local_size={verification.local_size} "
            f"last_modified={verification.remote_state.last_modified}"
        ),
        log_path,
    )
    log(
        f"[SP] Hash local={verification.local_sha256} | hash remoto={verification.remote_sha256}",
        log_path,
    )
    log(
        (
            "[SP] Huella semantica local="
            f"{verification.local_semantic_sha256} | remota={verification.remote_semantic_sha256}"
        ),
        log_path,
    )
    if verification.remote_verify_copy:
        log(f"[SP] Copia local de verificacion remota: {verification.remote_verify_copy}", log_path)
    for warning in verification.warnings:
        log(f"[WARN][SP][POST] {warning}", log_path)
    for issue in verification.issues:
        log(f"[CRITICO][SP][POST] {issue}", log_path)

    if verification.ok:
        log("[OK][SP] Escritura oficial controlada confirmada en SharePoint.", log_path)
        return 0

    log("[FALLO][SP] La escritura remota no supero la verificacion post-subida.", log_path)
    return 2


def run_sharepoint_publish(args: argparse.Namespace, log_path: Path) -> int:
    client_key = args.sharepoint_client
    if not client_key:
        raise RuntimeError("Falta --sharepoint-client.")

    source_file = Path(args.source_file) if args.source_file else None
    return run_sharepoint_publish_for_client(
        client_key=client_key,
        log_path=log_path,
        target_year=args.year,
        target_month=args.month,
        commit=args.commit,
        source_file=source_file,
    )


def run_production_lightweight(args: argparse.Namespace, log_path: Path) -> int:
    if args.source_file:
        raise RuntimeError("--source-file no aplica al modo batch --production-lightweight.")

    selected = list(PRODUCTION_LIGHTWEIGHT_CLIENTS)
    if args.production_clients:
        requested = [item.strip().lower() for item in args.production_clients.split(",") if item.strip()]
        invalid = [item for item in requested if item not in PRODUCTION_LIGHTWEIGHT_CLIENTS]
        if invalid:
            raise RuntimeError(f"Clientes no habilitados para produccion acotada: {invalid}")
        selected = requested

    log(
        (
            "[PRODUCCION_ACOTADA] Inicio lote clientes livianos | "
            f"modo={'COMMIT' if args.commit else 'DRY-RUN'} | clientes={selected}"
        ),
        log_path,
    )
    log("[PRODUCCION_ACOTADA] DERCO queda fuera de esta etapa.", log_path)

    results: list[tuple[str, int]] = []
    for client_key in selected:
        client = CONTROLLED_LIGHTWEIGHT_CLIENTS[client_key]
        log(
            f"[PRODUCCION_ACOTADA] >>> Cliente {client['empresa_wms']} / {client['deposito_wms_origen']}",
            log_path,
        )
        try:
            code = run_sharepoint_publish_for_client(
                client_key=client_key,
                log_path=log_path,
                target_year=args.year,
                target_month=args.month,
                commit=args.commit,
            )
        except Exception as exc:
            code = 2
            log(f"[FALLO][PRODUCCION_ACOTADA] {client_key}: {exc}", log_path)
        results.append((client_key, code))

    ok_count = sum(1 for _client, code in results if code == 0)
    fail_count = sum(1 for _client, code in results if code != 0)
    log("[PRODUCCION_ACOTADA] Resumen final por cliente:", log_path)
    for client_key, code in results:
        client = CONTROLLED_LIGHTWEIGHT_CLIENTS[client_key]
        status = "OK" if code == 0 else "FALLO"
        log(f"[PRODUCCION_ACOTADA] {client['empresa_wms']}: {status}", log_path)
    log(
        f"[PRODUCCION_ACOTADA] Totales | ok={ok_count} | fallo={fail_count} | clientes={len(results)}",
        log_path,
    )
    return 0 if fail_count == 0 else 2


def run_daily_operational(args: argparse.Namespace, log_path: Path) -> int:
    window = build_reporting_window(mode=args.mode, target_year=args.year, target_month=args.month)
    lightweight_clients = list(PRODUCTION_LIGHTWEIGHT_CLIENTS)

    log(
        (
            "[DIARIO] Inicio corrida diaria completa | "
            f"modo={'COMMIT' if args.commit else 'DRY-RUN'} | ventana={format_window(window)}"
        ),
        log_path,
    )
    log(
        (
            "[DIARIO] Livianos/estandar: "
            f"{lightweight_clients} | heavy_final=['derco']"
        ),
        log_path,
    )

    if args.dry_run:
        log("[DIARIO][DRY-RUN] Previsualizacion completada. No se ejecuto WMS ni SharePoint.", log_path)
        return 0

    completados_hoy = set() if getattr(args, "force", False) else _load_checkpoint()
    if completados_hoy:
        log(f"[CHECKPOINT] Clientes ya completados hoy: {', '.join(sorted(completados_hoy))}", log_path)

    results: list[dict] = []
    from_date = format_wms_date(window.from_dt)
    to_date = format_wms_date(window.to_dt)
    from_time = window.from_dt.strftime("%H:%M:%S")
    to_time = window.to_dt.strftime("%H:%M:%S")

    for client_key in lightweight_clients:
        client = CONTROLLED_LIGHTWEIGHT_CLIENTS[client_key]
        if client_key in completados_hoy:
            log(f"[SKIP][DIARIO] {client['empresa_wms']} — ya descargado hoy (checkpoint).", log_path)
            results.append({"client_key": client_key, "code": 0, "rows": _checkpoint_rows(client_key)})
            continue
        log(
            f"[DIARIO] >>> Cliente {client['empresa_wms']} / {client['deposito_wms_origen']}",
            log_path,
        )
        try:
            stage_code = run_runtime_lightweight_client(
                client_key=client_key,
                log_path=log_path,
                from_date=from_date,
                to_date=to_date,
                from_time=from_time,
                to_time=to_time,
                target_year=args.year,
                target_month=args.month,
            )
            if stage_code != 0:
                results.append({"client_key": client_key, "code": 2, "rows": -1})
                continue
            rows_count = count_normalized_rows(client["alias_archivo"])
            publish_code = run_sharepoint_publish_for_client(
                client_key=client_key,
                log_path=log_path,
                target_year=args.year,
                target_month=args.month,
                commit=args.commit,
            )
            results.append({"client_key": client_key, "code": publish_code, "rows": rows_count})
            if publish_code == 0:
                _save_checkpoint(client_key, rows=rows_count)
        except Exception as exc:
            log(f"[FALLO][DIARIO] {client_key}: {exc}", log_path)
            results.append({"client_key": client_key, "code": 2, "rows": -1})

    log("[DIARIO] >>> Cliente heavy DERCO / QUILICURA", log_path)
    if "derco" in completados_hoy:
        log("[SKIP][DIARIO] DERCO — ya descargado hoy (checkpoint).", log_path)
        results.append({"client_key": "derco", "code": 0, "rows": _checkpoint_rows("derco")})
    else:
        try:
            derco_stage = run_controlled_heavy_derco(args, log_path)
            if derco_stage == 0:
                derco_rows = count_normalized_rows(CONTROLLED_HEAVY_CLIENTS["derco"]["alias_archivo"])
                derco_publish = run_sharepoint_publish_for_client(
                    client_key="derco",
                    log_path=log_path,
                    target_year=args.year,
                    target_month=args.month,
                    commit=args.commit,
                )
                results.append({"client_key": "derco", "code": derco_publish, "rows": derco_rows})
                if derco_publish == 0:
                    _save_checkpoint("derco", rows=derco_rows)
            else:
                results.append({"client_key": "derco", "code": 2, "rows": -1})
        except Exception as exc:
            log(f"[FALLO][DIARIO] derco: {exc}", log_path)
            results.append({"client_key": "derco", "code": 2, "rows": -1})

    ok_count = sum(1 for r in results if r["code"] == 0)
    fail_count = sum(1 for r in results if r["code"] != 0)
    log("[DIARIO] Resumen final por cliente:", log_path)
    for r in results:
        client = CONTROLLED_EXECUTION_CLIENTS[r["client_key"]]
        status = "OK" if r["code"] == 0 else "FALLO"
        mov_str = str(r["rows"]) if r["rows"] >= 0 else "N/D"
        log(f"[DIARIO] {client['empresa_wms']}: {status} | movimientos={mov_str}", log_path)
    log(
        f"[DIARIO] Totales | ok={ok_count} | fallo={fail_count} | clientes={len(results)}",
        log_path,
    )

    email_code = run_final_email(args, log_path, results_detail=results, has_failures=(fail_count > 0))
    if email_code != 0:
        log("[FALLO][DIARIO] El correo final no pudo emitirse.", log_path)
        return 2
    return 0 if fail_count == 0 else 2


def run_final_email(
    args: argparse.Namespace,
    log_path: Path,
    results_detail: list | None = None,
    has_failures: bool = False,
) -> int:
    if results_detail:
        summary_rows = []
        for r in results_detail:
            client = CONTROLLED_EXECUTION_CLIENTS.get(r["client_key"], {})
            rows = r["rows"]
            code = r["code"]
            if code != 0:
                estado = "FALLO"
            elif rows == 0:
                estado = "SIN_DATOS"
            else:
                estado = "OK"
            summary_rows.append({
                "cliente": client.get("empresa_wms", r["client_key"]),
                "cd": client.get("cd", ""),
                "movimientos": rows if rows >= 0 else None,
                "estado": estado,
            })
        active_clients = sum(1 for r in results_detail if r["code"] == 0)
    else:
        # Fallback: leer conteos desde archivos normalizados del día (si existen)
        FALLBACK_CLIENTS = [
            ("Daikin",         "CD QUILICURA", "daikin"),
            ("Pochteca",       "CD QUILICURA", "pochteca"),
            ("Cerveceria ABI", "CD QUILICURA", "abinbev"),
            ("BHA",            "CD QUILICURA", "bha"),
            ("Mascotas Latinas","CD QUILICURA","mascota_quilicura"),
            ("Derco",          "CD QUILICURA", "derco"),
            ("Barentz",        "CD PUDAHUEL",  "barentz"),
            ("Buraschi",       "CD PUDAHUEL",  "buraschi"),
            ("Cepas Chile",    "CD PUDAHUEL",  "cepas_chile"),
            ("Collico",        "CD PUDAHUEL",  "collico"),
            ("Delibest",       "CD PUDAHUEL",  "delibest"),
            ("Intime",         "CD PUDAHUEL",  "intime"),
            ("Tres Montes",    "CD PUDAHUEL",  "tresmontes"),
            ("Unilever",       "CD PUDAHUEL",  "unilever"),
            ("Runo SPA",       "CD PUDAHUEL",  "runo"),
        ]
        summary_rows = []
        for nombre, cd, client_key in FALLBACK_CLIENTS:
            try:
                client_cfg = CONTROLLED_LIGHTWEIGHT_CLIENTS.get(client_key) or \
                             CONTROLLED_HEAVY_CLIENTS.get(client_key)
                alias = client_cfg["alias_archivo"] if client_cfg else None
                rows = count_normalized_rows(alias) if alias else None
            except Exception:
                rows = None
            summary_rows.append({"cliente": nombre, "cd": cd,
                                  "movimientos": rows if rows and rows > 0 else None,
                                  "estado": "OK"})
        active_clients = 15
    subject, html_body, payload = build_productividad_closure_email(
        summary_rows=summary_rows,
        active_clients_closed=active_clients,
        log_file=log_path,
    )
    if has_failures:
        subject = f"[FALLO PARCIAL] {subject}"
    artifacts = save_productividad_email_artifacts(
        subject=subject,
        html_body=html_body,
        payload=payload,
    )
    log(f"[EMAIL] Asunto: {subject}", log_path)
    log(f"[EMAIL] Preview HTML: {artifacts['html_path']}", log_path)
    log(f"[EMAIL] Resumen JSON: {artifacts['json_path']}", log_path)

    if not args.send_email:
        log("[EMAIL] Preview generado. No se envio correo porque no se indico --send-email.", log_path)
        return 0

    email_to_override = getattr(args, "email_to", None)
    ok = send_html_notification(
        subject=subject,
        html_body=html_body,
        log_path=log_path,
        recipients_override=[e.strip() for e in email_to_override.split(";") if e.strip()] if email_to_override else None,
    )
    if ok:
        log("[EMAIL] Correo final de Productividad enviado correctamente.", log_path)
        return 0

    log("[EMAIL] No se pudo enviar el correo final de Productividad.", log_path)
    return 2


def main() -> int:
    args = parse_args()
    log_path = build_log_path()

    # Modo por defecto: si no se especificó ningún flag de ejecución, actúa como --daily-run --commit --send-email
    no_mode_flag = not any([
        args.list_catalog, args.validate_file, args.controlled_daikin,
        args.controlled_client, args.controlled_heavy_client, args.sharepoint_client,
        args.daily_run, args.production_lightweight, args.final_email, args.dry_run,
    ])
    if no_mode_flag:
        args.daily_run = True
        args.commit = True
        args.send_email = True

    # Anti-colisión: solo una instancia de la corrida diaria a la vez
    if args.daily_run:
        if not _acquire_lock(log_path):
            return 1

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

    if args.controlled_daikin:
        return run_controlled_daikin(log_path)

    if args.controlled_client:
        return run_controlled_lightweight(args.controlled_client, log_path)

    if args.controlled_heavy_client:
        if args.controlled_heavy_client != "derco":
            raise RuntimeError("Solo DERCO esta habilitado como heavy_client en esta etapa.")
        return run_controlled_heavy_derco(args, log_path)

    if args.sharepoint_client:
        return run_sharepoint_publish(args, log_path)

    if args.daily_run:
        return run_daily_operational(args, log_path)

    if args.production_lightweight:
        return run_production_lightweight(args, log_path)

    if args.final_email:
        # Detectar fallos desde checkpoint: clientes activos no en completados
        checkpoint_completados = _load_checkpoint()
        ACTIVE_KEYS = set(CONTROLLED_EXECUTION_CLIENTS.keys())
        faltantes = ACTIVE_KEYS - checkpoint_completados
        has_failures = bool(faltantes)
        if has_failures:
            log(f"[EMAIL] Clientes sin completar en checkpoint: {', '.join(sorted(faltantes))}", log_path)
        # Construir results_detail desde checkpoint
        ck_data = {}
        try:
            ck_path = LOG_DIR / f"productividad_checkpoint_{datetime.now().strftime('%Y%m%d')}.json"
            if ck_path.exists():
                ck_data = json.load(open(ck_path, encoding="utf-8"))
        except Exception:
            pass
        rows_map = ck_data.get("rows", {})
        FALLBACK_CLIENTS_ORDERED = [
            ("Daikin",          "CD QUILICURA", "daikin"),
            ("Pochteca",        "CD QUILICURA", "pochteca"),
            ("Cerveceria ABI",  "CD QUILICURA", "abinbev"),
            ("BHA",             "CD QUILICURA", "bha"),
            ("Mascotas Latinas","CD QUILICURA", "mascota_quilicura"),
            ("Derco",           "CD QUILICURA", "derco"),
            ("Barentz",         "CD PUDAHUEL",  "barentz"),
            ("Buraschi",        "CD PUDAHUEL",  "buraschi"),
            ("Cepas Chile",     "CD PUDAHUEL",  "cepas_chile"),
            ("Collico",         "CD PUDAHUEL",  "collico"),
            ("Delibest",        "CD PUDAHUEL",  "delibest"),
            ("Intime",          "CD PUDAHUEL",  "intime"),
            ("Tres Montes",     "CD PUDAHUEL",  "tresmontes"),
            ("Unilever",        "CD PUDAHUEL",  "unilever"),
            ("Runo SPA",        "CD PUDAHUEL",  "runo"),
        ]
        results_detail = []
        for nombre, cd, key in FALLBACK_CLIENTS_ORDERED:
            completed = key in checkpoint_completados
            rows = rows_map.get(key, 0)
            results_detail.append({
                "client_key": key,
                "rows": rows if completed else -1,
                "code": 0 if completed else 1,
            })
        return run_final_email(args, log_path, results_detail=results_detail, has_failures=has_failures)

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

    # No debería llegar aquí — el modo por defecto ya cubre el caso sin flags
    return run_daily_operational(args, log_path)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    finally:
        _release_lock()
