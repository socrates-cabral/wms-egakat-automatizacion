"""
verificar_fechas.py — Verifica integridad de fechas en archivos de Productividad (abril 2026).

Para cada archivo lee la columna Fecha y reporta:
- Total filas de datos
- NaT count (fechas no parseables con dayfirst=True)
- Distribucion por mes (detecta fechas en mes incorrecto)
- Diferencias entre parseo correcto (dayfirst=True) vs buggy (dayfirst=False)
"""

import sys
sys.stdout.reconfigure(encoding="utf-8")

from pathlib import Path
import pandas as pd
import warnings
warnings.filterwarnings("ignore")

ONEDRIVE_BASE = Path(
    r"C:\Users\Socrates Cabral\OneDrive - EGA KAT LOGISTICA SPA"
    r"\Datos para Dashboard - Productividad"
)

ARCHIVOS = {
    "CD QUILICURA": [
        "MovABInbev.xlsx",
        "MovBha.xlsx",
        "MovDaikin.xlsx",
        "MovDerco.xlsx",
        "MovMascota.xlsx",
        "MovPochteca.xlsx",
    ],
    "CD PUDAHUEL": [
        "MovBarentz.xlsx",
        "MovBuraschi.xlsx",
        "MovCepas Chile.xlsx",
        "MovCollico.xlsx",
        "MovDelibest.xlsx",
        "Movintime.xlsx",
        "MovMascota Latina.xlsx",
        "MovRuno.xlsx",
        "Movtresmontes.xlsx",
        "MovUnilever.xlsx",
    ],
}

MES = "04. Abril"
AÑO = "2026"


def leer_datos(xlsx_path: Path) -> pd.DataFrame:
    """Lee filas de datos del archivo usando pandas (skiprows=8 salta portada, fila 9=headers)."""
    df = pd.read_excel(
        xlsx_path,
        skiprows=8,          # salta filas 1-8 (portada), fila 9 queda como header
        engine="openpyxl",
        dtype=str,           # leer todo como str para ver el valor crudo de Fecha
    )
    # Eliminar filas completamente vacías
    df = df.dropna(how="all")
    # Eliminar footer "El reporte está ordenado..."
    if len(df) > 0 and "Comprobante" in df.columns:
        df = df[~df["Comprobante"].astype(str).str.startswith("El reporte")]
    return df


def verificar(df: pd.DataFrame, alias: str) -> dict:
    resultado = {
        "alias": alias,
        "total_filas": len(df),
        "nat_correcto": 0,
        "nat_buggy": 0,
        "swaps": 0,
        "fecha_min": None,
        "fecha_max": None,
        "meses": {},
        "muestra_fechas": [],
        "alertas": [],
    }

    if df.empty:
        resultado["alertas"].append("SIN DATOS")
        return resultado

    if "Fecha" not in df.columns:
        resultado["alertas"].append("COLUMNA Fecha NO ENCONTRADA")
        return resultado

    serie_raw = df["Fecha"].astype(str).str.strip()
    # Muestra de valores raw (primeras 3 únicas)
    resultado["muestra_fechas"] = serie_raw.dropna().unique()[:3].tolist()

    # Parsear correcto (dayfirst=True)
    correcto = pd.to_datetime(serie_raw, dayfirst=True, errors="coerce")
    # Parsear buggy (dayfirst=False, como era antes del fix)
    buggy = pd.to_datetime(serie_raw, dayfirst=False, errors="coerce")

    resultado["nat_correcto"] = int(correcto.isna().sum())
    resultado["nat_buggy"] = int(buggy.isna().sum())

    # Filas donde el parseo difiere entre ambos modos
    mask_diff = correcto.notna() & buggy.notna() & (correcto != buggy)
    resultado["swaps"] = int(mask_diff.sum())

    validas = correcto.dropna()
    if not validas.empty:
        resultado["fecha_min"] = validas.min().strftime("%d/%m/%Y")
        resultado["fecha_max"] = validas.max().strftime("%d/%m/%Y")
        resultado["meses"] = {int(k): int(v) for k, v in validas.dt.month.value_counts().sort_index().items()}

    # Construir alertas
    if resultado["nat_correcto"] > 0:
        resultado["alertas"].append(
            f"NaT={resultado['nat_correcto']} filas con fecha no parseable"
        )
    if resultado["swaps"] > 0:
        # Mostrar ejemplo de swap
        idx = mask_diff[mask_diff].index[0]
        ej_raw = serie_raw.iloc[idx]
        ej_correcto = correcto.iloc[idx].strftime("%d/%m/%Y")
        ej_buggy = buggy.iloc[idx].strftime("%d/%m/%Y")
        resultado["alertas"].append(
            f"SWAP={resultado['swaps']} fechas ambiguas: raw='{ej_raw}' "
            f"→ correcto={ej_correcto} | buggy={ej_buggy}"
        )
    meses_raros = {m: c for m, c in resultado["meses"].items() if m != 4}
    if meses_raros:
        resultado["alertas"].append(f"Meses distintos a abril: {meses_raros}")

    if not resultado["alertas"]:
        resultado["alertas"].append("OK")

    return resultado


def main():
    print("=" * 72)
    print(f"VERIFICACION FECHAS — Productividad / {AÑO} / {MES}")
    print("=" * 72)

    hay_problemas = False

    for cd, archivos in ARCHIVOS.items():
        carpeta = ONEDRIVE_BASE / cd / AÑO / MES
        print(f"\n[{cd}]")

        for archivo in archivos:
            ruta = carpeta / archivo
            alias = archivo.replace(".xlsx", "")

            if not ruta.exists():
                print(f"  ? {alias:<26} — ARCHIVO NO ENCONTRADO")
                continue

            try:
                df = leer_datos(ruta)
                res = verificar(df, alias)
            except Exception as exc:
                print(f"  ✗ {alias:<26} — ERROR: {exc}")
                hay_problemas = True
                continue

            alertas = res["alertas"]
            es_ok = alertas == ["OK"] or alertas == ["SIN DATOS"]
            if not es_ok:
                hay_problemas = True

            icono = "✓" if es_ok else "✗"
            filas = f"{res['total_filas']:>4} filas"
            rango = ""
            if res["fecha_min"] and res["fecha_max"]:
                rango = f" | {res['fecha_min']} → {res['fecha_max']}"
            meses_str = ""
            if res["meses"] and list(res["meses"].keys()) != [4]:
                meses_str = f" | meses={res['meses']}"

            print(f"  {icono} {alias:<26} {filas}{rango}{meses_str}")
            for a in alertas:
                if a not in ("OK", "SIN DATOS"):
                    print(f"      ⚠  {a}")
            if alertas == ["SIN DATOS"]:
                print(f"       — sin movimientos en abril")

    print("\n" + "=" * 72)
    if hay_problemas:
        print("RESULTADO: HAY PROBLEMAS — revisar alertas arriba")
    else:
        print("RESULTADO: TODOS LOS ARCHIVOS OK")
    print("=" * 72)


if __name__ == "__main__":
    main()
