# sharepoint_copy.py v1.0
# Módulo 6 — Copia Staging IN-OUT → Clientes EK (SharePoint)
# Autor: generado Claude.ai 2026-03-11
# Flujo: OneDrive local (origen) → SharePoint Clientes EK (destino)
# Anti-duplicado: compara nombres de archivo en destino antes de subir
# Año y mes son DINÁMICOS — no hardcodear. La carpeta destino se crea automáticamente si no existe.
# Modo: BACKFILL (mes actual completo) o DAILY (solo archivos de hoy)

import os
import sys
import re
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from office365.runtime.auth.user_credential import UserCredential
from office365.sharepoint.client_context import ClientContext

sys.stdout.reconfigure(encoding="utf-8")

# ─── CONFIG ───────────────────────────────────────────────────────────────────

load_dotenv(r"C:\ClaudeWork\.env")

SP_SITE     = "https://egakatcom.sharepoint.com/sites/DatosparaDashboard"
SP_USER     = os.getenv("SHAREPOINT_USER")
SP_PASSWORD = os.getenv("SHAREPOINT_PASSWORD")

ONEDRIVE_BASE = r"C:\Users\Socrates Cabral\OneDrive - EGA KAT LOGISTICA SPA\Datos para Dashboard - Stagin IN- OUT"

MESES_ES = {
    1: "01 Enero",    2: "02 Febrero",   3: "03 Marzo",    4: "04 Abril",
    5: "05 Mayo",     6: "06 Junio",     7: "07 Julio",    8: "08 Agosto",
    9: "09 Septiembre", 10: "10 Octubre", 11: "11 Noviembre", 12: "12 Diciembre"
}

hoy        = datetime.today()
MES_ACTUAL = MESES_ES[hoy.month]
ANO_ACTUAL = str(hoy.year)
HOY_STR    = hoy.strftime("%d%m%Y")

# Modo: "daily" = solo hoy | "backfill" = todo el mes actual
MODO = sys.argv[1] if len(sys.argv) > 1 else "daily"

# Clientes Quilicura: {carpeta_origen_local: nombre_carpeta_destino_SP}
# PUDAHUEL: vacío por ahora — agregar aquí cuando se habilite
CLIENTES = {
    "ABINBEV":          "ABINBEV",
    "DAIKIN":           "DAIKIN",
    "DERCO":            "DERCO",
    "MASCOTAS LATINAS": "MASCOTAS LATINAS",
    "POCHTECA":         "POCHTECA",
}

# ─── LOG ──────────────────────────────────────────────────────────────────────

LOG_DIR  = Path(r"C:\ClaudeWork\logs")
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / f"sharepoint_copy_{hoy.strftime('%Y%m%d')}.log"

def log(msg: str):
    ts   = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")

# ─── SHAREPOINT HELPERS ───────────────────────────────────────────────────────

def get_ctx():
    creds = UserCredential(SP_USER, SP_PASSWORD)
    return ClientContext(SP_SITE).with_credentials(creds)

def listar_archivos_destino(ctx, carpeta_sp: str) -> set:
    nombres = set()
    try:
        folder = ctx.web.get_folder_by_server_relative_url(carpeta_sp)
        files  = folder.files
        ctx.load(files)
        ctx.execute_query()
        for f in files:
            nombres.add(f.properties["Name"])
    except Exception as e:
        log(f"  [WARN] No se pudo listar destino {carpeta_sp}: {e}")
    return nombres

def crear_carpeta_sp(ctx, ruta_relativa: str):
    try:
        ctx.web.ensure_folder_path(ruta_relativa).execute_query()
        log(f"  [OK] Carpeta asegurada: {ruta_relativa}")
    except Exception as e:
        log(f"  [WARN] Error creando carpeta {ruta_relativa}: {e}")

def subir_archivo(ctx, ruta_local: Path, carpeta_sp: str) -> bool:
    try:
        folder = ctx.web.get_folder_by_server_relative_url(carpeta_sp)
        with open(ruta_local, "rb") as f:
            folder.upload_file(ruta_local.name, f.read()).execute_query()
        return True
    except Exception as e:
        log(f"  [ERROR] {ruta_local.name}: {e}")
        return False

# ─── FILTRO DE FECHA ──────────────────────────────────────────────────────────

# Nombre archivo: VISTA_CONSULTA_Pallets_ABINBEVSCABRAL10032026080246.csv
# Timestamp embebido: DDMMYYYYHHMMSS al final antes de .csv
RE_FECHA = re.compile(r"(\d{2})(\d{2})(\d{4})\d{6}\.csv$")

def filtrar_archivos(archivos: list) -> list:
    resultado = []
    for f in archivos:
        m = RE_FECHA.search(f.name)
        if not m:
            continue
        dd, mm, yyyy = m.group(1), m.group(2), m.group(3)
        if MODO == "daily":
            if f"{dd}{mm}{yyyy}" == HOY_STR:
                resultado.append(f)
        else:  # backfill
            if mm == hoy.strftime("%m") and yyyy == ANO_ACTUAL:
                resultado.append(f)
    return resultado

# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    log("=" * 60)
    log(f"sharepoint_copy.py v1.0 | MODO={MODO} | {hoy.strftime('%d/%m/%Y')}")
    log(f"Mes destino: {MES_ACTUAL} {ANO_ACTUAL}")
    log("=" * 60)

    ctx = get_ctx()

    total_subidos = 0
    total_skip    = 0
    total_errores = 0

    for cliente_origen, cliente_destino in CLIENTES.items():
        log(f"\n>> Cliente: {cliente_origen}")

        origen = Path(ONEDRIVE_BASE) / "Quilicura" / cliente_origen
        if not origen.exists():
            log(f"  [SKIP] Carpeta origen no existe: {origen}")
            continue

        csvs       = list(origen.glob("*.csv"))
        candidatos = filtrar_archivos(csvs)
        log(f"  Archivos en origen: {len(csvs)} | Candidatos ({MODO}): {len(candidatos)}")

        if not candidatos:
            log(f"  Sin archivos para copiar en modo {MODO}")
            continue

        # Ruta destino dinámica — año y mes calculados en tiempo de ejecución
        destino_sp = f"/sites/DatosparaDashboard/Documentos compartidos/Clientes EK/{cliente_destino}/Inventario/{ANO_ACTUAL}/{MES_ACTUAL}"

        # Crear carpeta si no existe (ensure crea toda la jerarquía)
        crear_carpeta_sp(ctx, destino_sp)

        # Anti-duplicado
        existentes = listar_archivos_destino(ctx, destino_sp)
        log(f"  Archivos ya en destino: {len(existentes)}")

        for archivo in candidatos:
            if archivo.name in existentes:
                log(f"  [SKIP] Duplicado: {archivo.name}")
                total_skip += 1
                continue

            ok = subir_archivo(ctx, archivo, destino_sp)
            if ok:
                log(f"  [OK] Subido: {archivo.name}")
                total_subidos += 1
            else:
                total_errores += 1

    log("\n" + "=" * 60)
    log(f"RESUMEN | Subidos: {total_subidos} | Duplicados omitidos: {total_skip} | Errores: {total_errores}")
    log("=" * 60)

if __name__ == "__main__":
    main()
