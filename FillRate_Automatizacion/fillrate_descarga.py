"""
Script principal de descarga y actualizacion de Fill Rate.

Prioridades:
- compatibilidad con ecosistema WMS vivo
- no leer secretos manualmente ni hardcodearlos
- no tocar hoja `base`
- reemplazar solo el mes actual en SharePoint
- marcar claramente lo que requiere validacion runtime
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError, sync_playwright

from fillrate_config import (
    CLIENTS,
    DEFAULT_DOWNLOAD_ATTEMPTS,
    DEFAULT_DOWNLOAD_BACKOFF_MULTIPLIER,
    DOWNLOAD_TIMEOUT_MS,
    HEAVY_DOWNLOAD_TIMEOUT_MS,
    MESES_CORTE,
    WMS_ESTADO_DEFAULT,
    WMS_FECHA_TIPO_DEFAULT,
    WMS_FILLRATE_URL,
    WMS_LOGIN_URL,
    WMS_MENU_URL,
    WMS_OPERACION_LABEL,
)
from fillrate_utils import (
    ClientExecutionResult,
    build_log_path,
    build_summary_html,
    build_warnings,
    compute_otif_from_wms_rows,
    compute_pending_from_wms_rows,
    format_wms_date,
    get_reporting_window,
    get_wms_credentials,
    log,
    read_fillrate_rows,
    send_summary_email,
    update_sharepoint_workbook,
)


if sys.stdout:
    sys.stdout.reconfigure(encoding="utf-8")

_LOGS_DIR = Path(__file__).resolve().parent / "logs"
LOCKFILE = _LOGS_DIR / "fillrate_run.lock"


def _pid_alive(pid: int) -> bool:
    """Comprueba si un PID está activo (Windows-compatible, sin dependencias extra)."""
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
    """Crea lock file con PID actual. Retorna False si ya hay una instancia activa."""
    _LOGS_DIR.mkdir(exist_ok=True)
    if LOCKFILE.exists():
        try:
            pid = int(LOCKFILE.read_text().strip())
            if _pid_alive(pid):
                log(f"[ERROR] Ya hay una instancia corriendo (PID {pid}). Abortando.", log_path)
                return False
        except Exception:
            pass
        LOCKFILE.unlink(missing_ok=True)
    LOCKFILE.write_text(str(os.getpid()))
    return True


def _release_lock() -> None:
    try:
        LOCKFILE.unlink(missing_ok=True)
    except Exception:
        pass


def _checkpoint_path() -> Path:
    return _LOGS_DIR / f"fillrate_checkpoint_{datetime.now().strftime('%Y%m%d')}.json"


def _load_checkpoint() -> set:
    path = _checkpoint_path()
    if not path.exists():
        return set()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return set(data.get("completados", []))
    except Exception:
        return set()


def _save_checkpoint(client_name: str) -> None:
    path = _checkpoint_path()
    completados = _load_checkpoint()
    completados.add(client_name)
    path.write_text(
        json.dumps({"completados": sorted(completados)}, ensure_ascii=False),
        encoding="utf-8",
    )


LOGIN_USER_SELECTOR = "input[name='vUSR']"
LOGIN_PASS_SELECTOR = "input[name='vPASSWORD']"
LOGIN_BUTTON_SELECTOR = "input[name='BUTTON3']"
ACCEPT_BUTTON_SELECTOR = "input[value='Aceptar']"

EXPORT_BUTTON_CANDIDATES = (
    "input[value='EXPORTAR EXCEL']",
    "input[value='Exportar Excel']",
    "text=EXPORTAR EXCEL",
    "text=Exportar Excel",
)

DEPOSITO_SELECT_CANDIDATES = (
    "select[name='vCTRODISTRIBUCION']",
    "#vCTRODISTRIBUCION",
)

EMPRESA_SELECT_CANDIDATES = (
    "select[name='vCTROEMPRESA']",
    "#vCTROEMPRESA",
)

OPERACION_SELECT_CANDIDATES = (
    "select[name='vCTROOPERACION']",
    "#vCTROOPERACION",
)

FROM_DATE_CANDIDATES = (
    "input[name='vFDESDE']",
    "input[name='vFECHADESDE']",
)

TO_DATE_CANDIDATES = (
    "input[name='vFHASTA']",
    "input[name='vFECHAHASTA']",
)

DATE_TYPE_SELECT_CANDIDATES = (
    "select[name='vTIPOFECHA']",
    "select[name='vTIPODEFECHA']",
)


def is_headless() -> bool:
    value = os.getenv("FILLRATE_HEADLESS", "true").strip().lower()
    return value not in {"0", "false", "no"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Modulo Fill Rate WMS Egakat")
    parser.add_argument(
        "--client",
        help="Nombre exacto o parcial del cliente para correr una prueba controlada.",
    )
    parser.add_argument(
        "--headful",
        action="store_true",
        help="Fuerza ejecucion visible del navegador para debug runtime.",
    )
    parser.add_argument(
        "--skip-email",
        action="store_true",
        help="No envia el correo final; util para pruebas controladas.",
    )
    parser.add_argument(
        "--wms-user",
        help="Override explicito del usuario WMS sin tocar .env.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Ignora el checkpoint diario y fuerza la descarga aunque ya se haya ejecutado hoy.",
    )
    return parser.parse_args()


def filter_clients(client_filter: Optional[str]) -> List[Dict[str, Any]]:
    if not client_filter:
        return list(CLIENTS)

    normalized = client_filter.strip().lower()
    filtered = [client for client in CLIENTS if normalized in client["nombre"].lower()]
    if not filtered:
        raise RuntimeError(f"No hay clientes configurados que coincidan con '{client_filter}'.")
    return filtered


def click_first_available(page: Page, selectors: Sequence[str], *, timeout_ms: int = 5_000) -> bool:
    for selector in selectors:
        locator = page.locator(selector)
        if locator.count() > 0:
            locator.first.click(timeout=timeout_ms)
            return True
    return False


def click_locator_if_present(locator, *, timeout_ms: int = 5_000) -> bool:
    try:
        if locator.count() > 0:
            locator.first.click(timeout=timeout_ms)
            return True
    except Exception:
        return False
    return False


def fill_first_available(page: Page, selectors: Sequence[str], value: str, *, timeout_ms: int = 5_000) -> bool:
    for selector in selectors:
        locator = page.locator(selector)
        if locator.count() > 0:
            locator.first.fill("", timeout=timeout_ms)
            locator.first.fill(value, timeout=timeout_ms)
            locator.first.press("Tab", timeout=timeout_ms)
            return True
    return False


def collect_options(select_locator) -> List[str]:
    return [text.strip() for text in select_locator.locator("option").all_inner_texts()]


def wait_for_option_text(
    page: Page,
    label: str,
    *,
    preferred_selectors: Optional[Sequence[str]] = None,
    timeout_ms: int = 10_000,
) -> Optional[str]:
    deadline = datetime.now().timestamp() + (timeout_ms / 1000)
    preferred_selectors = preferred_selectors or ()

    while datetime.now().timestamp() < deadline:
        for selector in preferred_selectors:
            locator = page.locator(selector)
            if locator.count() == 0:
                continue
            options = collect_options(locator.first)
            if label in options:
                return selector

        page.wait_for_timeout(500)

    return None


def select_by_option_text(
    page: Page,
    label: str,
    *,
    field_name: str,
    preferred_selectors: Optional[Sequence[str]] = None,
    timeout_ms: int = 5_000,
) -> str:
    preferred_selectors = preferred_selectors or ()
    for selector in preferred_selectors:
        locator = page.locator(selector)
        if locator.count() == 0:
            continue
        options = collect_options(locator.first)
        if label in options:
            locator.first.select_option(label=label, timeout=timeout_ms)
            return selector

    select_count = page.locator("select").count()
    for index in range(select_count):
        locator = page.locator("select").nth(index)
        options = collect_options(locator)
        if label in options:
            locator.select_option(label=label, timeout=timeout_ms)
            return f"select[index={index}]"

    # Dump all options across all selects for diagnostics
    all_selects_dump = []
    total_selects = page.locator("select").count()
    for _i in range(total_selects):
        _opts = collect_options(page.locator("select").nth(_i))
        all_selects_dump.append(f"  select[{_i}]: {_opts}")
    dump_str = "\n".join(all_selects_dump) if all_selects_dump else "  (ninguno)"
    raise RuntimeError(
        f"No se encontro opcion '{label}' para campo '{field_name}'. Validacion runtime requerida.\n"
        f"Opciones disponibles en la pagina:\n{dump_str}"
    )


def select_if_option_exists(
    page: Page,
    label: str,
    *,
    field_name: str,
    preferred_selectors: Optional[Sequence[str]] = None,
    timeout_ms: int = 5_000,
    log_path: Optional[Path] = None,
) -> Optional[str]:
    try:
        return select_by_option_text(
            page,
            label,
            field_name=field_name,
            preferred_selectors=preferred_selectors,
            timeout_ms=timeout_ms,
        )
    except Exception:
        log(
            f"[WARN] No se pudo confirmar selector para '{field_name}' con opcion '{label}'. Revisar runtime.",
            log_path,
        )
        return None


def login_and_select_deposito(page: Page, usuario: str, clave: str, deposito: str, log_path: Path) -> None:
    page.set_default_timeout(30_000)
    page.goto(WMS_LOGIN_URL, wait_until="load", timeout=30_000)
    page.wait_for_timeout(1_500)

    page.locator(LOGIN_USER_SELECTOR).fill(usuario)
    page.locator(LOGIN_PASS_SELECTOR).fill(clave)
    page.locator(LOGIN_BUTTON_SELECTOR).click()
    page.wait_for_load_state("load", timeout=30_000)
    page.wait_for_timeout(1_500)
    log("Login WMS OK.", log_path)

    selector_used = select_by_option_text(page, deposito, field_name="deposito inicial")
    log(f"Deposito inicial seleccionado: {deposito} via {selector_used}.", log_path)

    if page.locator(ACCEPT_BUTTON_SELECTOR).count() == 0:
        raise RuntimeError("No se encontro boton 'Aceptar' luego de seleccionar deposito.")
    page.locator(ACCEPT_BUTTON_SELECTOR).first.click()
    page.wait_for_load_state("load", timeout=30_000)
    page.wait_for_timeout(1_500)


def navigate_to_fillrate(page: Page, log_path: Path) -> None:
    menu_attempts = [
        lambda: click_locator_if_present(page.get_by_text("Procesos WMS", exact=True), timeout_ms=5_000),
        lambda: click_locator_if_present(page.get_by_role("link", name=re.compile(r"Procesos WMS", re.I)), timeout_ms=5_000),
        lambda: click_locator_if_present(page.locator("a[href*='trabajarconwms.aspx']"), timeout_ms=5_000),
    ]

    try:
        for action in menu_attempts:
            if action():
                page.wait_for_timeout(1_000)
                break
        else:
            raise RuntimeError("No se pudo abrir 'Procesos WMS' desde la pantalla inicial.")

        fillrate_attempts = [
            lambda: click_locator_if_present(page.get_by_text("Consulta de Fill Rate", exact=True), timeout_ms=5_000),
            lambda: click_locator_if_present(page.get_by_role("link", name=re.compile(r"Consulta de Fill Rate", re.I)), timeout_ms=5_000),
            lambda: click_locator_if_present(page.locator("a[href*='seguimientopedidoswp.aspx']"), timeout_ms=5_000),
        ]
        for action in fillrate_attempts:
            if action():
                page.wait_for_load_state("load", timeout=30_000)
                page.wait_for_timeout(1_000)
                log("Navegacion menu WMS -> Consulta de Fill Rate OK.", log_path)
                return
        raise RuntimeError("No se encontro enlace 'Consulta de Fill Rate' en el menu WMS.")
    except Exception as exc:
        log(
            f"[WARN] Navegacion por menu no estable: {exc}. Se usa URL conocida y debe validarse en runtime.",
            log_path,
        )
    try:
        page.goto(WMS_MENU_URL, wait_until="load", timeout=30_000)
        page.wait_for_timeout(1_000)
        if click_locator_if_present(page.locator("a[href*='seguimientopedidoswp.aspx']"), timeout_ms=5_000):
            page.wait_for_load_state("load", timeout=30_000)
            page.wait_for_timeout(1_000)
            log("Navegacion a Fill Rate lograda desde pagina menu WMS.", log_path)
            return
    except Exception:
        pass
    page.goto(WMS_FILLRATE_URL, wait_until="load", timeout=30_000)
    page.wait_for_timeout(1_500)


def configure_filters(page: Page, client: Dict[str, Any], log_path: Path) -> None:
    fecha_desde, fecha_hasta = get_reporting_window()
    fecha_desde_txt = format_wms_date(fecha_desde)
    fecha_hasta_txt = format_wms_date(fecha_hasta)

    log(
        f"Configurando filtros para {client['nombre']} | {fecha_desde_txt} a {fecha_hasta_txt}.",
        log_path,
    )

    wait_for_option_text(
        page,
        client["deposito_wms"],
        preferred_selectors=DEPOSITO_SELECT_CANDIDATES,
        timeout_ms=12_000,
    )
    deposito_selector = select_by_option_text(
        page,
        client["deposito_wms"],
        field_name="deposito",
        preferred_selectors=DEPOSITO_SELECT_CANDIDATES,
    )

    wait_for_option_text(
        page,
        client["empresa_wms"],
        preferred_selectors=EMPRESA_SELECT_CANDIDATES,
        timeout_ms=12_000,
    )
    empresa_selector = select_by_option_text(
        page,
        client["empresa_wms"],
        field_name="empresa",
        preferred_selectors=EMPRESA_SELECT_CANDIDATES,
    )

    wait_for_option_text(
        page,
        WMS_OPERACION_LABEL,
        preferred_selectors=OPERACION_SELECT_CANDIDATES,
        timeout_ms=12_000,
    )
    operacion_selector = select_by_option_text(
        page,
        WMS_OPERACION_LABEL,
        field_name="operacion",
        preferred_selectors=OPERACION_SELECT_CANDIDATES,
    )

    log(
        "Selectores runtime usados: "
        f"deposito={deposito_selector}, empresa={empresa_selector}, operacion={operacion_selector}.",
        log_path,
    )

    date_type_used = select_if_option_exists(
        page,
        WMS_FECHA_TIPO_DEFAULT,
        field_name="tipo fecha",
        preferred_selectors=DATE_TYPE_SELECT_CANDIDATES,
        log_path=log_path,
    )
    if date_type_used:
        log(f"Tipo fecha confirmado: {WMS_FECHA_TIPO_DEFAULT} via {date_type_used}.", log_path)

    estado_used = select_if_option_exists(
        page,
        WMS_ESTADO_DEFAULT,
        field_name="estado",
        log_path=log_path,
    )
    if estado_used:
        log(f"Estado WMS confirmado: {WMS_ESTADO_DEFAULT} via {estado_used}.", log_path)

    if not fill_first_available(page, FROM_DATE_CANDIDATES, fecha_desde_txt):
        raise RuntimeError("No se encontro campo 'Fecha desde'. Validacion runtime requerida.")
    if not fill_first_available(page, TO_DATE_CANDIDATES, fecha_hasta_txt):
        raise RuntimeError("No se encontro campo 'Fecha hasta'. Validacion runtime requerida.")


def download_fillrate_file(page: Page, client: Dict[str, Any], log_path: Path) -> Path:
    timeout_ms = int(
        client.get(
            "download_timeout_ms",
            HEAVY_DOWNLOAD_TIMEOUT_MS if client["nombre"] == "Derco" else DOWNLOAD_TIMEOUT_MS,
        )
    )
    started_at = datetime.now()

    with page.expect_download(timeout=timeout_ms) as download_info:
        if not click_first_available(page, EXPORT_BUTTON_CANDIDATES, timeout_ms=5_000):
            raise RuntimeError("No se encontro boton 'EXPORTAR EXCEL'. Validacion runtime requerida.")

    download = download_info.value
    suggested_name = download.suggested_filename or "Reporte_Consulta_de_Fill_Rate.xlsx"
    destination = build_log_path().parent / f"temp_fillrate_{client['nombre'].replace(' ', '_')}{Path(suggested_name).suffix or '.xlsx'}"
    if destination.exists():
        destination.unlink()
    download.save_as(str(destination))
    log(
        f"Excel descargado para {client['nombre']} en {(datetime.now() - started_at).total_seconds():.1f}s.",
        log_path,
    )
    return destination


def compute_timeout_for_attempt(client: Dict[str, Any], attempt_number: int) -> int:
    base_timeout = int(
        client.get(
            "download_timeout_ms",
            HEAVY_DOWNLOAD_TIMEOUT_MS if client["nombre"] == "Derco" else DOWNLOAD_TIMEOUT_MS,
        )
    )
    multiplier = float(client.get("download_backoff_multiplier", DEFAULT_DOWNLOAD_BACKOFF_MULTIPLIER))
    if attempt_number <= 1 or multiplier <= 1.0:
        return base_timeout
    return int(base_timeout * (multiplier ** (attempt_number - 1)))


def process_client(page: Page, client: Dict[str, Any], usuario: str, clave: str, log_path: Path) -> Dict[str, Any]:
    login_and_select_deposito(page, usuario, clave, client["deposito_wms"], log_path)
    attempts = int(client.get("download_attempts", DEFAULT_DOWNLOAD_ATTEMPTS))
    last_error: Optional[Exception] = None
    downloaded_path: Optional[Path] = None

    for attempt_number in range(1, attempts + 1):
        navigate_to_fillrate(page, log_path)
        configure_filters(page, client, log_path)
        attempt_timeout = compute_timeout_for_attempt(client, attempt_number)
        client_for_attempt = dict(client)
        client_for_attempt["download_timeout_ms"] = attempt_timeout

        if attempt_number > 1:
            log(
                f"[REINTENTO] Descarga {attempt_number}/{attempts} para {client['nombre']} "
                f"con timeout {attempt_timeout / 1000:.0f}s.",
                log_path,
            )
        try:
            downloaded_path = download_fillrate_file(page, client_for_attempt, log_path)
            break
        except PlaywrightTimeoutError as exc:
            last_error = exc
            if attempt_number >= attempts:
                raise
            log(
                f"[WARN] Timeout de descarga para {client['nombre']} en intento {attempt_number}/{attempts}.",
                log_path,
            )
            try:
                page.goto("about:blank", wait_until="load", timeout=15_000)
            except Exception:
                pass
            page.wait_for_timeout(2_000)

    if downloaded_path is None:
        if last_error:
            raise last_error
        raise RuntimeError("No se obtuvo archivo descargado para el cliente.")

    if not downloaded_path.exists():
        raise RuntimeError("La descarga reportada por Playwright no quedo disponible en disco.")

    rows = read_fillrate_rows(downloaded_path)
    try:
        downloaded_path.unlink(missing_ok=True)
    except Exception:
        pass
    warning_items = build_warnings(client["nombre"], rows)

    if not rows:
        return {
            "status": "SIN_DATOS",
            "rows": 0,
            "replaced_rows": 0,
            "warnings": warning_items,
            "target_sheet": "",
            "used_fallback_sheet": False,
        }

    # Pendientes desde WMS (no requiere formulas Excel)
    _now = datetime.now()
    _month, _year = _now.month, _now.year
    pending_wms = compute_pending_from_wms_rows(rows, _month, _year)

    workbook_result = update_sharepoint_workbook(
        client,
        rows,
        log_path=log_path,
        meses_corte=MESES_CORTE,
    )

    # OTIF viene del archivo recalculado por Excel Online (post-upload)
    # Pendientes: preferimos el dato del archivo recalculado si tiene datos, sino el WMS
    sp_pendientes = workbook_result.get("pendientes") or {}
    sp_otif = workbook_result.get("otif") or {}
    final_pending = sp_pendientes if sp_pendientes.get("total", 0) >= pending_wms["total"] else pending_wms
    final_otif = sp_otif

    log(
        f"Metricas finales — pendientes={final_pending['total']}, otif_pedidos={final_otif.get('pedidos', 0)}.",
        log_path,
    )

    return {
        "status": "OK",
        "rows": workbook_result["new_rows"],
        "replaced_rows": workbook_result["replaced_rows"],
        "duplicates_removed": workbook_result["duplicates_removed"],
        "warnings": warning_items,
        "target_sheet": workbook_result["target_sheet"] or "",
        "used_fallback_sheet": workbook_result["used_fallback_sheet"],
        "pending": final_pending,
        "otif": final_otif,
    }


def build_email_subject(reference_dt: Optional[datetime] = None) -> str:
    reference_dt = reference_dt or datetime.now()
    return f"[WMS Egakat] NNSS - Descarga {reference_dt.strftime('%d/%m/%Y')}"


def main() -> int:
    args = parse_args()
    log_path = build_log_path()
    started_at = datetime.now()

    if not _acquire_lock(log_path):
        return 1

    try:
        return _run(args, log_path, started_at)
    finally:
        _release_lock()


def _run(args: argparse.Namespace, log_path: Path, started_at: datetime) -> int:
    usuario, clave = get_wms_credentials(user_override=args.wms_user)
    selected_clients = filter_clients(args.client)

    log("=" * 60, log_path)
    log("INICIO MODULO FILL RATE", log_path)
    log("=" * 60, log_path)
    log("Playwright aprobado como excepcion documentada para este modulo.", log_path)
    if args.client:
        log(f"Modo prueba controlada activado para filtro de cliente: {args.client}", log_path)
    if args.skip_email:
        log("Modo prueba: correo final deshabilitado por flag.", log_path)
    if args.wms_user:
        log("Override de usuario WMS recibido por parametro.", log_path)

    completados_hoy = set() if args.force else _load_checkpoint()
    if completados_hoy:
        log(f"[CHECKPOINT] Clientes ya completados hoy: {', '.join(sorted(completados_hoy))}", log_path)

    results: List[ClientExecutionResult] = []
    all_warning_items: List[Dict[str, Any]] = []

    # Clientes que necesitan descarga WMS (no están en checkpoint)
    clientes_pendientes = [
        c for c in selected_clients
        if c.get("active", False) and c["nombre"] not in completados_hoy
    ]

    # Clientes ya completados hoy: agregar al resumen sin tocar WMS
    for client in selected_clients:
        if client["nombre"] in completados_hoy:
            log(f"[SKIP] {client['nombre']} — ya descargado hoy (checkpoint). Se omite.", log_path)
            results.append(
                ClientExecutionResult(
                    cliente=client["nombre"],
                    cd=client["cd"],
                    estado="Ya descargado",
                    detalle="Checkpoint diario activo. Usar --force para forzar.",
                )
            )

    if not clientes_pendientes:
        log("[INFO] Todos los clientes activos ya fueron descargados hoy.", log_path)
    else:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=(False if args.headful else is_headless()), slow_mo=0)
            try:
                for client in clientes_pendientes:
                    log("-" * 60, log_path)
                    log(f"Cliente: {client['nombre']} | Deposito: {client['deposito_wms']}", log_path)

                    MAX_CLIENT_ATTEMPTS = 3
                    client_outcome: Optional[Dict[str, Any]] = None
                    client_error: Optional[str] = None
                    retried_success = False

                    for client_attempt in range(1, MAX_CLIENT_ATTEMPTS + 1):
                        context = browser.new_context(accept_downloads=True)
                        page = context.new_page()
                        try:
                            if client_attempt > 1:
                                log(
                                    f"[REINTENTO {client_attempt}/{MAX_CLIENT_ATTEMPTS}] "
                                    f"Reintentando cliente {client['nombre']}.",
                                    log_path,
                                )
                            client_outcome = process_client(page, client, usuario, clave, log_path)
                            if client_attempt > 1:
                                retried_success = True
                            break
                        except PlaywrightTimeoutError as exc:
                            client_error = "Timeout WMS o descarga"
                            log(
                                f"[FALLO {client_attempt}/{MAX_CLIENT_ATTEMPTS}] "
                                f"Timeout en {client['nombre']}: {exc}",
                                log_path,
                            )
                        except Exception as exc:
                            client_error = str(exc)
                            log(
                                f"[FALLO {client_attempt}/{MAX_CLIENT_ATTEMPTS}] "
                                f"{client['nombre']}: {exc}",
                                log_path,
                            )
                        finally:
                            context.close()

                        if client_attempt < MAX_CLIENT_ATTEMPTS:
                            log(f"Esperando 15s antes del reintento...", log_path)
                            time.sleep(15)

                    if client_outcome is None:
                        log(
                            f"[FALLO] {client['nombre']} agoto {MAX_CLIENT_ATTEMPTS} intentos. "
                            f"Se continua con el siguiente cliente.",
                            log_path,
                        )
                        results.append(
                            ClientExecutionResult(
                                cliente=client["nombre"],
                                cd=client["cd"],
                                estado="Error",
                                detalle=client_error or "Error desconocido",
                            )
                        )
                        continue

                    all_warning_items.extend(client_outcome["warnings"])

                    if client_outcome["status"] == "SIN_DATOS":
                        log("WMS devolvio 0 filas; no se modifica SharePoint.", log_path)
                        results.append(
                            ClientExecutionResult(
                                cliente=client["nombre"],
                                cd=client["cd"],
                                estado="Sin datos",
                                filas_nuevas=0,
                                filas_reemplazadas=0,
                                advertencias=len(client_outcome["warnings"]),
                            )
                        )
                        continue

                    log(
                        "SharePoint actualizado OK | "
                        f"nuevas={client_outcome['rows']} | reemplazadas={client_outcome['replaced_rows']} | "
                        f"duplicadas_omitidas={client_outcome.get('duplicates_removed', 0)}.",
                        log_path,
                    )
                    detail = ""
                    if client_outcome.get("duplicates_removed", 0) > 0:
                        detail = f"Duplicadas omitidas: {client_outcome['duplicates_removed']}"
                    results.append(
                        ClientExecutionResult(
                            cliente=client["nombre"],
                            cd=client["cd"],
                            estado="OK",
                            filas_nuevas=client_outcome["rows"],
                            filas_reemplazadas=client_outcome["replaced_rows"],
                            advertencias=len(client_outcome["warnings"]),
                            detalle=detail,
                            used_fallback_sheet=client_outcome["used_fallback_sheet"],
                            target_sheet=client_outcome["target_sheet"],
                            retried_success=retried_success,
                            pendientes=client_outcome.get("pending"),
                            otif=client_outcome.get("otif"),
                        )
                    )
                    _save_checkpoint(client["nombre"])
            finally:
                browser.close()

    if not args.skip_email:
        html_body = build_summary_html(results, all_warning_items)
        try:
            if send_summary_email(build_email_subject(started_at), html_body, log_path=log_path):
                log("Correo resumen enviado via Graph API.", log_path)
        except Exception as exc:
            log(f"[WARN] No se pudo enviar correo resumen: {exc}", log_path)

    elapsed = (datetime.now() - started_at).total_seconds()
    log("=" * 60, log_path)
    log(f"FIN MODULO FILL RATE | Duracion total: {elapsed:.1f}s", log_path)
    log("=" * 60, log_path)
    return 0





if __name__ == "__main__":
    raise SystemExit(main())
