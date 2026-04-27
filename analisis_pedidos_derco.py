import sys
sys.stdout.reconfigure(encoding="utf-8")
import pandas as pd
from pathlib import Path

OUT = Path("C:/ClaudeWork/analisis_out.txt")
DERCO = Path("C:/Users/Socrates Cabral/OneDrive - EGA KAT LOGISTICA SPA/datos para Dashboard EK/Productividad/CD QUILICURA/2026/04. Abril/MovDerco.xlsx")

try:
    # Leer sin asumir header — ver las primeras 15 filas raw
    raw = pd.read_excel(DERCO, header=None, nrows=15, engine="openpyxl")
    lines = ["=== PRIMERAS 15 FILAS RAW ==="]
    for i, row in raw.iterrows():
        lines.append(f"Fila {i}: {list(row)}")

    # Intentar leer con header en fila 9 (patron historico)
    df = pd.read_excel(DERCO, header=8, engine="openpyxl")
    lines.append(f"\n=== CON HEADER=9 ===")
    lines.append(f"Shape: {df.shape}")
    lines.append(f"Columnas: {list(df.columns)}")

    # Columnas de fecha
    date_cols = [c for c in df.columns if str(c).strip() in ("Fecha", "Hora")]
    lines.append(f"Cols fecha/hora: {date_cols}")

    if date_cols:
        col_fecha = date_cols[0]
        df[col_fecha] = pd.to_datetime(df[col_fecha], errors="coerce")
        lines.append(f"\nRango fechas: {df[col_fecha].min()} → {df[col_fecha].max()}")
        lines.append(f"Fechas únicas ({df[col_fecha].dt.date.nunique()}): {sorted(df[col_fecha].dt.date.dropna().unique())}")

    # Buscar columna comprobante/pedido
    comp_cols = [c for c in df.columns if str(c).strip() == "Comprobante"]
    lines.append(f"\nCols comprobante/pedido: {comp_cols}")

    if comp_cols and date_cols:
        col_comp = comp_cols[0]
        col_fecha = date_cols[0]
        # Pedidos que aparecen en más de un día
        pedidos_dias = df.groupby(col_comp)[col_fecha].apply(lambda x: x.dt.date.nunique())
        multi_dia = pedidos_dias[pedidos_dias > 1]
        lines.append(f"\nPedidos con movimientos en más de 1 día: {len(multi_dia)}")
        if len(multi_dia) > 0:
            lines.append(f"Top 10:")
            for comp, ndias in multi_dia.sort_values(ascending=False).head(10).items():
                fechas = sorted(df[df[col_comp] == comp][col_fecha].dt.date.dropna().unique())
                nlineas = len(df[df[col_comp] == comp])
                lines.append(f"  {comp}: {ndias} días, {nlineas} líneas — fechas: {fechas}")

    OUT.write_text("\n".join(lines), encoding="utf-8")
    print("OK")
except Exception as e:
    import traceback
    OUT.write_text(f"ERROR: {e}\n{traceback.format_exc()}", encoding="utf-8")
    print(f"ERROR: {e}")
