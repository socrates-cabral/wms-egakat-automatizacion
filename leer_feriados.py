import sys
sys.stdout.reconfigure(encoding="utf-8")
import pandas as pd
from pathlib import Path

OUT = Path("C:/ClaudeWork/feriados_out.txt")
F = Path("C:/Users/Socrates Cabral/OneDrive - EGA KAT LOGISTICA SPA/Datos para Dashboard - Productividad/Tabla Feriados.xlsx")

try:
    # Leer todas las hojas
    xl = pd.ExcelFile(F, engine="openpyxl")
    lines = [f"Hojas: {xl.sheet_names}"]
    for sheet in xl.sheet_names:
        df = pd.read_excel(F, sheet_name=sheet, engine="openpyxl")
        lines.append(f"\n=== {sheet} === shape={df.shape}")
        lines.append(str(df.head(20).to_string()))
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print("OK")
except Exception as e:
    import traceback
    OUT.write_text(f"ERROR: {e}\n{traceback.format_exc()}", encoding="utf-8")
    print(f"ERROR: {e}")
