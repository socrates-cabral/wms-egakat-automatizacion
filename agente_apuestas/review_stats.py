import sys
sys.stdout.reconfigure(encoding="utf-8")
import json
from datetime import datetime, timezone

with open("agente_apuestas/backtesting/historico_apuestas.json", encoding="utf-8") as f:
    data = json.load(f)

cr = [x for x in data if x.get("ganado") is not None]
g = [x for x in cr if x["ganado"]]
r = sum(x.get("retorno", 0) or 0 for x in cr)
m = sum(x.get("monto_apostado", 0) or 0 for x in cr)
roi = round(r / m * 100, 2) if m else 0
wr = round(len(g) / len(cr) * 100, 1) if cr else 0

print(f"=== AGENTE APUESTAS — {datetime.now().strftime('%Y-%m-%d')} ===")
print(f"Total registros  : {len(data)}")
print(f"Con resultado    : {len(cr)}")
print(f"Ganadas          : {len(g)}")
print(f"Win rate         : {wr}%")
print(f"ROI acumulado    : {roi}%")
print(f"P&L total        : {r:,.0f}")

# Ligas
ligas = {}
for x in cr:
    liga = x.get("liga", "?")
    if liga not in ligas:
        ligas[liga] = {"total": 0, "gan": 0, "retorno": 0, "monto": 0}
    ligas[liga]["total"] += 1
    if x["ganado"]:
        ligas[liga]["gan"] += 1
    ligas[liga]["retorno"] += x.get("retorno", 0) or 0
    ligas[liga]["monto"] += x.get("monto_apostado", 0) or 0

print("\n--- Por liga ---")
for liga, stats in sorted(ligas.items()):
    wr_l = round(stats["gan"] / stats["total"] * 100, 1) if stats["total"] else 0
    roi_l = round(stats["retorno"] / stats["monto"] * 100, 2) if stats["monto"] else 0
    print(f"  {liga:15s}: {stats['total']:3d} apuestas | WR {wr_l}% | ROI {roi_l}%")

# Ultimas 5
print("\n--- Ultimas 5 con resultado ---")
for x in cr[-5:]:
    emoji = "[V]" if x["ganado"] else "[X]"
    fecha = x.get("fecha_partido", "")[:10]
    print(f"  {emoji} {fecha} | {x.get('liga','?'):8s} | {x.get('seleccion','?'):20s} | cuota {x.get('cuota','?')} | retorno {x.get('retorno',0):+,.0f}")
