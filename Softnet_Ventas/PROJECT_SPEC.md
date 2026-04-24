# PROJECT SPEC — Softnet_Ventas

Spec técnico para implementación por Claude Code. Lee MEMORY.md primero para contexto.

## Estructura de carpetas a crear

```
C:\ClaudeWork\Softnet_Ventas\
├── MEMORY.md                    ← contexto de negocio (ya provisto)
├── PROJECT_SPEC.md              ← este archivo
├── README.md                    ← instrucciones de uso (generar)
├── requirements.txt             ← dependencias
├── config\
│   └── parametros.json          ← ventana_dias, site_name, rutas SP
├── logs\                        ← auto-crear, .gitignore
│   ├── log_cambios_pagos.xlsx   ← bitácora de auditoría
│   └── softnet_ventas_*.log     ← log técnico por ejecución
├── downloads\                   ← temporal, auto-limpiar, .gitignore
├── snapshots_cierre\            ← backups inmutables, .gitignore
│   └── 2026\
└── src\
    ├── __init__.py
    ├── run_ventas.py            ← orquestador principal (entrypoint)
    ├── softnet_scraper.py       ← Playwright: login + descarga
    ├── sp_graph.py              ← Graph API: upload/download SharePoint
    ├── comparador.py            ← detecta cambios entre versiones
    ├── event_logger.py          ← append al log_cambios_pagos.xlsx
    ├── notificador.py           ← correo resumen (reutiliza azure_graph)
    └── utils.py                 ← helpers: meses, nombres, locks, checkpoint
```

## Archivos a crear fuera del proyecto

- **`C:\ClaudeWork\.env`**: agregar 3 variables nuevas (ver MEMORY.md sección "Variables de entorno")
- **`.gitignore`** del proyecto: ignora `logs/`, `downloads/`, `snapshots_cierre/`, `.env`

## Configuración: config/parametros.json

```json
{
  "ventana_dias": 60,
  "softnet": {
    "url_login": "https://www.softnet.cl/sistems/contabilidad/login.php",
    "url_libro_ventas": "https://www.softnet.cl/sistems/contabilidad/m_venta.php",
    "timeout_default_ms": 60000,
    "timeout_download_ms": 180000,
    "retry_attempts": 3,
    "retry_backoff_seconds": [60, 120, 180]
  },
  "sharepoint": {
    "hostname": "egakatcom.sharepoint.com",
    "site_path": "/sites/FinanzasyMejoraContinua",
    "drive_name": "Documentos",
    "ruta_base": "Informe Ventas Mensual"
  },
  "notificacion": {
    "destinatarios": [
      "socrates.cabral@egakat.cl"
    ],
    "enviar_siempre": true
  }
}
```

## Módulo: src/utils.py

Funciones helper. Pseudo-código:

```python
from datetime import date, timedelta
from calendar import monthrange
import os, subprocess, json
from pathlib import Path

MESES_ES = {
    1:"Enero", 2:"Febrero", 3:"Marzo", 4:"Abril", 5:"Mayo", 6:"Junio",
    7:"Julio", 8:"Agosto", 9:"Septiembre", 10:"Octubre", 11:"Noviembre", 12:"Diciembre"
}

def meses_en_ventana(fecha_ref: date, ventana_dias: int = 60) -> list[tuple[int, int]]:
    """Retorna lista de (año, mes) abiertos según regla de ventana.
    Un mes está abierto si: último_día_mes + ventana_dias >= fecha_ref
    Itera hacia atrás desde el mes actual hasta encontrar el primer cerrado.
    Retorna lista en orden cronológico ascendente.
    """
    abiertos = []
    año, mes = fecha_ref.year, fecha_ref.month
    while True:
        ultimo_dia = monthrange(año, mes)[1]
        fecha_cierre = date(año, mes, ultimo_dia) + timedelta(days=ventana_dias)
        if fecha_cierre < fecha_ref:
            break
        abiertos.append((año, mes))
        mes -= 1
        if mes == 0:
            mes = 12
            año -= 1
    return sorted(abiertos)

def nombre_archivo_sp(año: int, mes: int) -> str:
    """{mes}.0 Ventas {Mes_español} {año}.xlsx"""
    return f"{mes}.0 Ventas {MESES_ES[mes]} {año}.xlsx"

def mes_a_nombre_softnet(mes: int) -> str:
    """ENERO, FEBRERO, ... (uppercase, para selector del form)"""
    return MESES_ES[mes].upper()

def adquirir_lock(lockfile: Path) -> bool:
    """Patrón idéntico a run_todos.py: PID check con tasklist.
    Retorna True si obtuvo el lock, False si ya hay instancia corriendo.
    """
    # Verificar si existe lock y si PID está vivo
    # Si vivo → abortar (False)
    # Si muerto → limpiar y continuar
    # Escribir PID actual

def liberar_lock(lockfile: Path) -> None:
    # Eliminar lockfile si existe

def limpiar_downloads(downloads_dir: Path) -> None:
    """Elimina todos los .xlsx en downloads/ para evitar sufijos '(1)', '(2)'."""

def snapshot_existe(snapshot_dir: Path, año: int, mes: int) -> bool:
    """Verifica si ya existe el _cierre.xlsx de ese mes."""
    nombre = nombre_archivo_sp(año, mes).replace(".xlsx", "_cierre.xlsx")
    return (snapshot_dir / str(año) / nombre).exists()

def guardar_snapshot_cierre(snapshot_dir: Path, año: int, mes: int, contenido: bytes) -> Path:
    """Escribe el archivo de cierre a disco. Retorna path."""
```

## Módulo: src/softnet_scraper.py

Playwright. Pseudo-código:

```python
from playwright.sync_api import sync_playwright, Page
from pathlib import Path
import os, time

def descargar_libro_ventas(año: int, mes: int, target_path: Path, log_fn) -> Path:
    """Descarga el libro de ventas de un (año, mes) y lo guarda en target_path.
    Retorna el path del archivo descargado.
    Levanta excepción si falla todos los reintentos.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()
        page.set_default_timeout(60_000)
        
        try:
            _login(page, log_fn)
            _navegar_libro_ventas(page, log_fn)
            _seleccionar_periodo(page, año, mes, log_fn)
            _descargar_excel(page, target_path, log_fn)
            return target_path
        finally:
            browser.close()

def _login(page: Page, log_fn):
    rut = os.getenv("EMPRESA_SOFTNET_RUT")
    usuario = os.getenv("USUARIO_SOFTNET")
    clave = os.getenv("CLAVE_SOFTNET")
    assert rut and usuario and clave, "Credenciales Softnet faltantes en .env"
    
    page.goto("https://www.softnet.cl/sistems/contabilidad/login.php")
    page.fill("input[name='empresa']", rut)
    page.fill("input[name='usuario']", usuario)
    page.fill("input[name='clave']", clave)
    # click "Ingresar" (botón submit del form)
    page.click("button:has-text('Ingresar'), input[type='submit'][value*='Ingresar']")
    page.wait_for_load_state("networkidle")
    log_fn("Login OK")

def _navegar_libro_ventas(page: Page, log_fn):
    """Navegar directo a m_venta.php (más robusto que expandir menús)."""
    page.goto("https://www.softnet.cl/sistems/contabilidad/m_venta.php")
    page.wait_for_load_state("networkidle")
    log_fn("En pantalla Libro de Ventas")

def _seleccionar_periodo(page: Page, año: int, mes: int, log_fn):
    # Selector periodo (dropdown)
    page.select_option("select[name='periodo']", str(año))
    # Selector mes (value es número: "4" para abril)
    page.select_option("select[name='select']", str(mes))
    # Sucursal queda default ""
    # Click "Siguiente"
    page.click("input[name='agregar2']")
    page.wait_for_load_state("networkidle")
    log_fn(f"Periodo {año}-{mes:02d} seleccionado")

def _descargar_excel(page: Page, target_path: Path, log_fn):
    """Click en el PRIMER botón de Excel (name='Submit22', title='Excel de Libro')."""
    with page.expect_download(timeout=180_000) as dl_info:
        page.click("input[name='Submit22']")
    download = dl_info.value
    download.save_as(str(target_path))
    log_fn(f"Descarga completada: {target_path}")
```

**Nota crítica**: Softnet muestra 6 botones de Excel. El que necesitamos es el **primero de izquierda a derecha** con `name="Submit22"`, `title="Excel de Libro"` (ver imágenes del usuario).

**Retry con backoff** (3 intentos, 60s/120s/180s): envolver `descargar_libro_ventas` en un wrapper que capture `PlaywrightTimeoutError` y reintente.

## Módulo: src/comparador.py

```python
import pandas as pd
from pathlib import Path
from openpyxl import load_workbook

def parse_libro_ventas(xlsx_path: Path) -> pd.DataFrame:
    """Lee el archivo Softnet. Headers en fila 10 (índice 9), datos desde fila 11.
    Normaliza tipos y agrega columna clave 'doc_id' = 'tipo_doc-cto'.
    Retorna DataFrame o DataFrame vacío si el archivo no existe.
    """
    if not xlsx_path.exists():
        return pd.DataFrame()
    df = pd.read_excel(xlsx_path, header=9, engine="openpyxl")
    df = df.dropna(subset=["Cto", "Tipo Doc"])
    df["doc_id"] = df["Tipo Doc"].astype(int).astype(str) + "-" + df["Cto"].astype(int).astype(str)
    # Normalizar columnas dinámicas
    df["Estado"] = df["Estado"].fillna("").astype(str).str.strip()
    df["Fecha Ultimo pago"] = df["Fecha Ultimo pago"].fillna("-").astype(str).str.strip()
    df["Saldo"] = pd.to_numeric(df["Saldo"], errors="coerce").fillna(0)
    return df

def detectar_cambios(df_nuevo: pd.DataFrame, df_anterior: pd.DataFrame, mes_archivo: str) -> list[dict]:
    """Compara dos DataFrames del mismo mes y retorna lista de eventos.
    mes_archivo: string 'YYYY-MM' para etiquetar en el log.
    
    Tipos de evento:
    - NUEVA_FACTURA: doc_id en nuevo, no en anterior (solo tipo_doc=33)
    - NC_APLICADA: doc_id en nuevo, no en anterior, tipo_doc=61
    - PAGO_APLICADO: Estado 'NO Pagado' → 'Pagado'
    - CAMBIO_SALDO: Saldo cambió sin cambio de Estado
    """
    eventos = []
    if df_anterior.empty:
        # Primera vez: no generar eventos, solo marcar todo como existente
        return eventos
    
    idx_ant = df_anterior.set_index("doc_id")
    idx_nuevo = df_nuevo.set_index("doc_id")
    
    # Nuevos documentos
    nuevos_ids = set(idx_nuevo.index) - set(idx_ant.index)
    for doc_id in nuevos_ids:
        row = idx_nuevo.loc[doc_id]
        tipo_evento = "NC_APLICADA" if row["Tipo Doc"] == 61 else "NUEVA_FACTURA"
        eventos.append(_build_evento(row, mes_archivo, tipo_evento, estado_anterior=None))
    
    # Cambios en docs existentes
    comunes = set(idx_nuevo.index) & set(idx_ant.index)
    for doc_id in comunes:
        r_ant = idx_ant.loc[doc_id]
        r_new = idx_nuevo.loc[doc_id]
        
        estado_ant = r_ant["Estado"]
        estado_new = r_new["Estado"]
        
        if estado_ant == "NO Pagado" and estado_new == "Pagado":
            eventos.append(_build_evento(r_new, mes_archivo, "PAGO_APLICADO", estado_anterior=estado_ant))
        elif r_ant["Saldo"] != r_new["Saldo"] and estado_ant == estado_new:
            eventos.append(_build_evento(r_new, mes_archivo, "CAMBIO_SALDO", estado_anterior=estado_ant))
    
    return eventos

def _build_evento(row, mes_archivo: str, tipo: str, estado_anterior):
    from datetime import datetime
    return {
        "fecha_deteccion": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "mes_archivo": mes_archivo,
        "tipo_doc": int(row["Tipo Doc"]),
        "n_cto": int(row["Cto"]),
        "rut": row["Rut"],
        "razon_social": row["Razon Social"],
        "tipo_cambio": tipo,
        "estado_anterior_actual": f"{estado_anterior or '-'} → {row['Estado']}",
        "fecha_pago": row["Fecha Ultimo pago"],
        "monto_total": float(row["Total"]) if pd.notna(row["Total"]) else 0,
    }

def hay_cambios(eventos: list[dict]) -> bool:
    return len(eventos) > 0
```

## Módulo: src/event_logger.py

```python
from pathlib import Path
from openpyxl import load_workbook, Workbook

LOG_HEADERS = [
    "fecha_deteccion", "mes_archivo", "tipo_doc", "n_cto", "rut",
    "razon_social", "tipo_cambio", "estado_anterior_actual", "fecha_pago", "monto_total"
]

def append_eventos(log_path: Path, eventos: list[dict]) -> None:
    """Agrega eventos al log_cambios_pagos.xlsx. Crea archivo con headers si no existe."""
    if not eventos:
        return
    
    if log_path.exists():
        wb = load_workbook(log_path)
        ws = wb.active
    else:
        wb = Workbook()
        ws = wb.active
        ws.title = "cambios"
        ws.append(LOG_HEADERS)
    
    for ev in eventos:
        ws.append([ev.get(h, "") for h in LOG_HEADERS])
    
    wb.save(log_path)
```

## Módulo: src/sp_graph.py

Helper Graph API minimalista. Pseudo-código:

```python
import os
import requests
from msal import ConfidentialClientApplication
from pathlib import Path

_token_cache = {"token": None, "expires_at": 0}

def _get_token() -> str:
    """Obtiene access token con client_credentials flow. Cachea hasta expiración."""
    import time
    if _token_cache["token"] and _token_cache["expires_at"] > time.time() + 60:
        return _token_cache["token"]
    
    client_id = os.getenv("AZURE_CLIENT_ID")
    client_secret = os.getenv("AZURE_CLIENT_SECRET")
    tenant_id = os.getenv("AZURE_TENANT_ID")
    
    app = ConfidentialClientApplication(
        client_id,
        authority=f"https://login.microsoftonline.com/{tenant_id}",
        client_credential=client_secret,
    )
    result = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
    if "access_token" not in result:
        raise RuntimeError(f"Graph API auth failed: {result.get('error_description')}")
    
    _token_cache["token"] = result["access_token"]
    _token_cache["expires_at"] = time.time() + result.get("expires_in", 3600)
    return result["access_token"]

def _headers() -> dict:
    return {"Authorization": f"Bearer {_get_token()}"}

def get_site_id(hostname: str, site_path: str) -> str:
    """hostname='egakatcom.sharepoint.com', site_path='/sites/FinanzasyMejoraContinua'"""
    url = f"https://graph.microsoft.com/v1.0/sites/{hostname}:{site_path}"
    r = requests.get(url, headers=_headers(), timeout=30)
    r.raise_for_status()
    return r.json()["id"]

def get_drive_id(site_id: str, drive_name: str = "Documentos") -> str:
    """Lista drives del site y retorna el id del drive llamado drive_name."""
    url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drives"
    r = requests.get(url, headers=_headers(), timeout=30)
    r.raise_for_status()
    for d in r.json()["value"]:
        if d["name"] == drive_name:
            return d["id"]
    raise ValueError(f"Drive '{drive_name}' no encontrado en site")

def descargar_archivo(drive_id: str, ruta_archivo: str) -> bytes | None:
    """ruta_archivo ej: 'Informe Ventas Mensual/2026/3.0 Ventas Marzo 2026.xlsx'
    Retorna bytes del archivo o None si no existe (404).
    """
    url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/root:/{ruta_archivo}:/content"
    r = requests.get(url, headers=_headers(), timeout=60)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.content

def subir_archivo(drive_id: str, ruta_archivo: str, contenido: bytes) -> dict:
    """Sobreescribe si existe. Para archivos <4MB usa PUT directo."""
    url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/root:/{ruta_archivo}:/content"
    headers = {**_headers(), "Content-Type": "application/octet-stream"}
    r = requests.put(url, headers=headers, data=contenido, timeout=120)
    r.raise_for_status()
    return r.json()

def asegurar_carpeta(drive_id: str, ruta_carpeta: str) -> None:
    """Crea carpetas padre si no existen. Idempotente.
    ruta_carpeta ej: 'Informe Ventas Mensual/2026'
    """
    partes = ruta_carpeta.strip("/").split("/")
    parent = ""
    for parte in partes:
        actual = f"{parent}/{parte}" if parent else parte
        # Intentar crear; si ya existe, Graph retorna 409 → ignorar
        if parent:
            url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/root:/{parent}:/children"
        else:
            url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/root/children"
        body = {"name": parte, "folder": {}, "@microsoft.graph.conflictBehavior": "fail"}
        r = requests.post(url, headers={**_headers(), "Content-Type":"application/json"}, json=body, timeout=30)
        if r.status_code not in (201, 409):
            r.raise_for_status()
        parent = actual
```

**Permiso requerido en la app de Azure AD**: `Sites.ReadWrite.All` (Application, con admin consent).

## Módulo: src/notificador.py

Correo resumen. Si `C:\ClaudeWork\azure_graph.py` existe y tiene función `enviar_email(from, to, subject, html)`, importarlo. Fallback: SMTP Office 365 con `SHAREPOINT_USER`/`SHAREPOINT_PASSWORD` (patrón heredado de run_todos.py).

```python
def enviar_resumen_diario(resumen: dict, destinatarios: list[str]) -> bool:
    """resumen = {
        'meses_procesados': [(año, mes, 'OK'|'FALLO'|'SIN_CAMBIOS')],
        'total_eventos': int,
        'eventos_por_tipo': {'PAGO_APLICADO': n, 'NUEVA_FACTURA': n, ...},
        'snapshots_generados': [(año, mes)],
        'errores': [str],
        'log_path': str,
    }"""
    asunto = _build_asunto(resumen)
    html = _build_html(resumen)
    # Intentar Graph API → fallback SMTP
```

## Módulo: src/run_ventas.py (ORQUESTADOR — ENTRYPOINT)

```python
"""Entrypoint: py C:\\ClaudeWork\\Softnet_Ventas\\src\\run_ventas.py"""
import sys
sys.stdout.reconfigure(encoding="utf-8")

from pathlib import Path
from datetime import datetime, date
from dotenv import load_dotenv
import json, os, traceback

BASE = Path(__file__).resolve().parent.parent         # C:\ClaudeWork\Softnet_Ventas
ROOT = BASE.parent                                     # C:\ClaudeWork
load_dotenv(ROOT / ".env")

from utils import (
    meses_en_ventana, nombre_archivo_sp, mes_a_nombre_softnet,
    adquirir_lock, liberar_lock, limpiar_downloads,
    snapshot_existe, guardar_snapshot_cierre, MESES_ES
)
from softnet_scraper import descargar_libro_ventas
from sp_graph import get_site_id, get_drive_id, descargar_archivo, subir_archivo, asegurar_carpeta
from comparador import parse_libro_ventas, detectar_cambios, hay_cambios
from event_logger import append_eventos
from notificador import enviar_resumen_diario

# Paths
DOWNLOADS = BASE / "downloads"
LOGS_DIR = BASE / "logs"
SNAPSHOTS_DIR = BASE / "snapshots_cierre"
CONFIG_PATH = BASE / "config" / "parametros.json"
LOCKFILE = LOGS_DIR / "softnet_ventas.lock"
LOG_CAMBIOS = LOGS_DIR / "log_cambios_pagos.xlsx"
LOG_TECNICO = Path(r"C:\ClaudeWork\logs") / f"softnet_ventas_{datetime.now():%Y-%m-%d_%H%M%S}.log"

def log(msg: str):
    line = f"[{datetime.now():%H:%M:%S}] {msg}"
    print(line)
    LOG_TECNICO.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_TECNICO, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def main() -> int:
    # Setup
    DOWNLOADS.mkdir(exist_ok=True)
    LOGS_DIR.mkdir(exist_ok=True)
    SNAPSHOTS_DIR.mkdir(exist_ok=True)
    
    with open(CONFIG_PATH, encoding="utf-8") as f:
        cfg = json.load(f)
    
    if not adquirir_lock(LOCKFILE):
        log("[LOCK] Ya hay una instancia corriendo. Abortando.")
        return 0
    
    resumen = {
        "meses_procesados": [],
        "total_eventos": 0,
        "eventos_por_tipo": {},
        "snapshots_generados": [],
        "errores": [],
        "log_path": str(LOG_TECNICO),
    }
    
    try:
        # 1. Setup Graph API (lazy: solo si hay algo que subir)
        site_id = get_site_id(cfg["sharepoint"]["hostname"], cfg["sharepoint"]["site_path"])
        drive_id = get_drive_id(site_id, cfg["sharepoint"]["drive_name"])
        
        # 2. Detectar meses abiertos
        hoy = date.today()
        meses_abiertos = meses_en_ventana(hoy, cfg["ventana_dias"])
        log(f"Meses en ventana de {cfg['ventana_dias']} días: {meses_abiertos}")
        
        # 3. Detectar meses que ACABAN de salir de ventana (para snapshot _cierre)
        # Mes que estaba abierto ayer pero no hoy
        meses_ayer = meses_en_ventana(hoy, cfg["ventana_dias"])  # placeholder, ver lógica abajo
        # Lógica real: revisar snapshots_cierre\{año}\ y detectar meses que ya no están en
        # meses_abiertos pero no tienen snapshot → generar snapshot desde SP
        _generar_snapshots_pendientes(drive_id, cfg, meses_abiertos, resumen, log)
        
        # 4. Procesar cada mes abierto
        for (año, mes) in meses_abiertos:
            _procesar_mes(año, mes, drive_id, cfg, resumen, log)
        
        # 5. Notificación
        destinatarios = cfg["notificacion"]["destinatarios"]
        enviar_resumen_diario(resumen, destinatarios)
        log("[OK] Ejecución completada")
        return 0
        
    except Exception as e:
        log(f"[FALLO] Error fatal: {e}")
        log(traceback.format_exc())
        resumen["errores"].append(str(e))
        try:
            enviar_resumen_diario(resumen, cfg["notificacion"]["destinatarios"])
        except Exception:
            pass
        return 1
    finally:
        liberar_lock(LOCKFILE)
        limpiar_downloads(DOWNLOADS)

def _procesar_mes(año, mes, drive_id, cfg, resumen, log_fn):
    """Descarga mes, compara, sube si hay cambios, registra eventos."""
    nombre_sp = nombre_archivo_sp(año, mes)
    ruta_sp = f"{cfg['sharepoint']['ruta_base']}/{año}/{nombre_sp}"
    mes_label = f"{año}-{mes:02d}"
    
    try:
        log_fn(f"--- Procesando {mes_label} ---")
        
        # 1. Descargar desde Softnet con retry
        target = DOWNLOADS / f"libro_ventas_{año}_{mes:02d}.xlsx"
        _descargar_con_retry(año, mes, target, cfg, log_fn)
        
        # 2. Descargar versión anterior de SP (puede no existir)
        log_fn("Descargando versión anterior de SharePoint...")
        contenido_anterior = descargar_archivo(drive_id, ruta_sp)
        
        df_nuevo = parse_libro_ventas(target)
        
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
        
        # 3. Registrar eventos
        if eventos:
            append_eventos(LOG_CAMBIOS, eventos)
            log_fn(f"Registrados {len(eventos)} eventos en log de cambios")
            for ev in eventos:
                t = ev["tipo_cambio"]
                resumen["eventos_por_tipo"][t] = resumen["eventos_por_tipo"].get(t, 0) + 1
            resumen["total_eventos"] += len(eventos)
        
        # 4. Subir si aplica
        if debe_subir:
            asegurar_carpeta(drive_id, f"{cfg['sharepoint']['ruta_base']}/{año}")
            subir_archivo(drive_id, ruta_sp, target.read_bytes())
            log_fn(f"[OK] Subido a SP: {ruta_sp}")
            resumen["meses_procesados"].append((año, mes, "OK"))
        else:
            log_fn("Sin cambios detectados, no se sube")
            resumen["meses_procesados"].append((año, mes, "SIN_CAMBIOS"))
            
    except Exception as e:
        log_fn(f"[FALLO] {mes_label}: {e}")
        resumen["errores"].append(f"{mes_label}: {e}")
        resumen["meses_procesados"].append((año, mes, "FALLO"))

def _descargar_con_retry(año, mes, target, cfg, log_fn):
    """Retry con backoff 60s/120s/180s."""
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
    raise RuntimeError(f"Falló después de {cfg['softnet']['retry_attempts']} intentos: {ultimo_error}")

def _hay_filas_nuevas(df_nuevo, df_anterior):
    """Detecta si hay filas en nuevo que no están en anterior (para forzar upload)."""
    if df_anterior.empty:
        return not df_nuevo.empty
    return len(set(df_nuevo["doc_id"]) - set(df_anterior["doc_id"])) > 0

def _generar_snapshots_pendientes(drive_id, cfg, meses_abiertos, resumen, log_fn):
    """Para cada mes que NO esté en meses_abiertos y NO tenga snapshot local → descargar de SP y guardar."""
    from datetime import date
    from calendar import monthrange
    
    hoy = date.today()
    año_actual = hoy.year
    
    # Revisar los últimos 24 meses hacia atrás
    año, mes = año_actual, hoy.month
    for _ in range(24):
        mes -= 1
        if mes == 0:
            mes = 12
            año -= 1
        
        if (año, mes) in meses_abiertos:
            continue
        if snapshot_existe(SNAPSHOTS_DIR, año, mes):
            continue
        
        # Mes cerrado sin snapshot → intentar descargar de SP y guardar
        nombre_sp = nombre_archivo_sp(año, mes)
        ruta_sp = f"{cfg['sharepoint']['ruta_base']}/{año}/{nombre_sp}"
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
```

## Fases de implementación sugeridas para Claude Code

Pedirle que implemente en este orden y valide cada fase antes de avanzar:

**Fase 1 — Estructura base + utils**
1. Crear estructura de carpetas
2. Crear `requirements.txt`, `config/parametros.json`, `.gitignore`
3. Crear `utils.py` con funciones puras
4. **Test**: `py -c "from src.utils import meses_en_ventana; from datetime import date; print(meses_en_ventana(date(2026,4,24), 60))"` → debe retornar `[(2026,2),(2026,3),(2026,4)]`

**Fase 2 — Scraper Softnet**
1. Crear `softnet_scraper.py`
2. **Test manual**: descargar abril 2026 a `downloads/` y verificar que el archivo tiene >11 filas y headers correctos

**Fase 3 — Graph API**
1. Crear `sp_graph.py`
2. **Test**: `get_site_id` + `get_drive_id` retornan IDs válidos; `descargar_archivo` sobre un archivo existente retorna bytes

**Fase 4 — Comparador + logger**
1. Crear `comparador.py` y `event_logger.py`
2. **Test**: parsear los dos archivos adjuntos (`libro_ventas.xlsx` abril 2026 y `libro_ventas__1_.xlsx` diciembre 2025), comparar artificialmente con versión "anterior" simulada, verificar que detecta PAGO_APLICADO correctamente

**Fase 5 — Notificador**
1. Crear `notificador.py` reutilizando patrón de `C:\ClaudeWork\azure_graph.py`

**Fase 6 — Orquestador**
1. Crear `run_ventas.py`
2. **Test end-to-end**: ejecutar una vez con logs verbose, verificar que sube el mes actual a SP y genera log de cambios

**Fase 7 — Task Scheduler**
1. Registrar tarea `Softnet Ventas - Descarga Diaria` con horario L-V 08:30
2. Verificar ejecución programada

## Criterios de aceptación v1

- [ ] Script ejecuta diariamente sin intervención manual
- [ ] Sube 3-4 archivos a SharePoint (meses abiertos) solo cuando hay cambios
- [ ] Genera snapshots `_cierre` cuando un mes sale de ventana
- [ ] Registra eventos en `log_cambios_pagos.xlsx` con los 4 tipos de cambio
- [ ] Envía correo diario con resumen (éxito o fallo)
- [ ] Lock impide ejecuciones simultáneas
- [ ] Retry 3x con backoff ante fallos transitorios de Softnet
- [ ] Credenciales jamás loggeadas
- [ ] Compatible con convención Egakat (py, UTF-8, `[FALLO]`, logs en `C:\ClaudeWork\logs\`)

## Prompt inicial para Claude Code

```
Lee MEMORY.md y PROJECT_SPEC.md en esta carpeta. 
Implementa el proyecto por fases 1-7 según lo especificado. 
Al terminar cada fase, detente y reporta lo hecho antes de avanzar. 
No toques `.env` (regla sagrada). 
Valida cada fase con los tests propuestos.
Archivos de referencia en uploads (si Claude Code los tiene): 
- libro_ventas.xlsx (abril 2026, mes abierto)
- libro_ventas__1_.xlsx (diciembre 2025, mes cerrado con pagos retroactivos)
Empieza por Fase 1.
```
