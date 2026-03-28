# sharepoint_copy.py v2.1
# Módulo 6 — Copia Staging IN-OUT → Clientes EK (OneDrive local sync)
# Autor: generado Claude Code 2026-03-11
# Flujo: OneDrive Stagin IN-OUT (origen) → OneDrive Clientes EK sincronizada (destino)
# OneDrive sincroniza automáticamente el destino con SharePoint
# Anti-duplicado: verifica si el archivo ya existe en destino antes de copiar
# Año y mes son DINÁMICOS — no hardcodear. Carpeta destino creada automáticamente.
# Modo: BACKFILL (mes actual completo) o DAILY (solo archivos de hoy)
# Nota: sharepoint_copy_API_v1.py = versión con Office365 REST API (pendiente auth IT)

import os
import re
import sys
import shutil
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding="utf-8")

load_dotenv(r"C:\ClaudeWork\.env")

# ─── CONFIG ───────────────────────────────────────────────────────────────────

ONEDRIVE = Path(os.getenv("ONEDRIVE_PATH", r"C:\Users\Socrates Cabral\OneDrive - EGA KAT LOGISTICA SPA"))

ORIGEN_BASE  = ONEDRIVE / "Datos para Dashboard - Stagin IN- OUT" / "Quilicura"
DESTINO_BASE = ONEDRIVE / "Datos para Dashboard - Clientes EK"

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

# Clientes Quilicura: {carpeta_origen: carpeta_destino}
# PUDAHUEL: vacío por ahora — agregar cuando se habilite
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

# ─── FILTRO DE FECHA Y NOMBRE DESTINO ────────────────────────────────────────

# Nombre archivo: VISTA_CONSULTA_Pallets_ABINBEVSCABRAL10032026080246.csv
# Timestamp embebido: DDMMYYYYHHMMSS al final antes de .csv
RE_FECHA = re.compile(r"(\d{2})(\d{2})(\d{4})\d{6}\.csv$")

def nombre_destino(archivo: Path) -> str:
    """Prefija YYYY-MM-DD_ al nombre para ordenar descendente (más reciente arriba)."""
    m = RE_FECHA.search(archivo.name)
    if not m:
        return archivo.name
    dd, mm, yyyy = m.group(1), m.group(2), m.group(3)
    return f"{yyyy}-{mm}-{dd}_{archivo.name}"

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
    log(f"sharepoint_copy.py v2.1 | MODO={MODO} | {hoy.strftime('%d/%m/%Y')}")
    log(f"Mes destino: {MES_ACTUAL} {ANO_ACTUAL}")
    log("=" * 60)

    total_copiados = 0
    total_skip     = 0
    total_errores  = 0

    for cliente_origen, cliente_destino in CLIENTES.items():
        log(f"\n>> Cliente: {cliente_origen}")

        origen = ORIGEN_BASE / cliente_origen
        if not origen.exists():
            log(f"  [SKIP] Carpeta origen no existe: {origen}")
            continue

        csvs       = list(origen.glob("*.csv"))
        candidatos = filtrar_archivos(csvs)
        log(f"  Archivos en origen: {len(csvs)} | Candidatos ({MODO}): {len(candidatos)}")

        if not candidatos:
            log(f"  Sin archivos para copiar en modo {MODO}")
            continue

        # Carpeta destino dinámica — creada automáticamente si no existe
        destino = DESTINO_BASE / cliente_destino / "Inventario" / ANO_ACTUAL / MES_ACTUAL
        destino.mkdir(parents=True, exist_ok=True)

        for archivo in candidatos:
            dest_nombre  = nombre_destino(archivo)   # YYYY-MM-DD_original.csv
            dest_archivo = destino / dest_nombre
            if dest_archivo.exists():
                log(f"  [SKIP] Duplicado: {dest_nombre}")
                total_skip += 1
                continue

            try:
                shutil.copy2(archivo, dest_archivo)
                log(f"  [OK] Copiado: {dest_nombre}")
                total_copiados += 1
            except Exception as e:
                log(f"  [ERROR] {dest_nombre}: {e}")
                total_errores += 1

    log("\n" + "=" * 60)
    log(f"RESUMEN | Copiados: {total_copiados} | Duplicados omitidos: {total_skip} | Errores: {total_errores}")
    log("=" * 60)

if __name__ == "__main__":
    main()
