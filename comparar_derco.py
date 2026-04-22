import sys
sys.stdout.reconfigure(encoding="utf-8")
import pandas as pd

DESCARGAS = r"C:\Users\Socrates Cabral\Downloads"
wms = pd.read_excel(f"{DESCARGAS}\\MovxDocBase2242026170326.xlsx", header=0).dropna(how="all")
sp  = pd.read_excel(f"{DESCARGAS}\\MovDerco.xlsx", header=8).dropna(how="all")

print(f"WMS cargado     : {len(wms):,} filas | {len(wms.columns)} columnas")
print(f"MovDerco cargado: {len(sp):,} filas | {len(sp.columns)} columnas")

# Construir datetime completo combinando Fecha + Hora
for df in [wms, sp]:
    df["Fecha"] = pd.to_datetime(df["Fecha"], dayfirst=True, errors="coerce")
    df["_dt"]   = pd.to_datetime(
        df["Fecha"].dt.strftime("%Y-%m-%d") + " " + df["Hora"].astype(str),
        errors="coerce"
    )

# Verificar rango real de WMS
print(f"\nWMS rango real  : {wms['_dt'].min()} → {wms['_dt'].max()}")
print(f"SP  rango real  : {sp['_dt'].min()} → {sp['_dt'].max()}")

# Filtrar rango exacto en ambos
DESDE = pd.Timestamp("2026-04-21 08:00:00")
HASTA = pd.Timestamp("2026-04-22 06:00:00")

wms_r = wms[(wms["_dt"] >= DESDE) & (wms["_dt"] <= HASTA)].copy()
sp_r  = sp[(sp["_dt"]  >= DESDE) & (sp["_dt"]  <= HASTA)].copy()

print(f"\n{'='*55}")
print(f"Rango: {DESDE}  →  {HASTA}")
print(f"{'='*55}")
print(f"WMS manual      : {len(wms_r):,} filas")
print(f"MovDerco SP     : {len(sp_r):,} filas")
diff = len(sp_r) - len(wms_r)
print(f"Diferencia      : {diff:+,} filas")
if diff == 0:
    print("✅ COINCIDEN exactamente en ese rango")
else:
    print("⚠️  No coinciden — analizando...")

# Duplicados reales (filas idénticas)
wms_r2 = wms_r.drop(columns=["_dt"])
sp_r2  = sp_r.drop(columns=["_dt"])
dup_wms = wms_r2.duplicated().sum()
dup_sp  = sp_r2.duplicated().sum()
print(f"\nDuplicados reales WMS : {dup_wms:,}")
print(f"Duplicados reales SP  : {dup_sp:,}")

# Comprobantes únicos en el rango
KEY = "Comprobante"
w = set(wms_r[KEY].astype(str).str.strip())
s = set(sp_r[KEY].astype(str).str.strip())
print(f"\nComprobantes solo WMS : {len(w-s):,}")
print(f"Comprobantes solo SP  : {len(s-w):,}")
print(f"Comprobantes en ambos : {len(w&s):,}")

if w - s:
    print(f"\nEjemplos solo en WMS (primeros 10): {sorted(w-s)[:10]}")
if s - w:
    print(f"\nEjemplos solo en SP  (primeros 10): {sorted(s-w)[:10]}")
    ej = sp_r[sp_r[KEY].astype(str).str.strip().isin(s-w)][["Comprobante","Fecha","Hora"]].head(10)
    print(ej.to_string(index=False))
