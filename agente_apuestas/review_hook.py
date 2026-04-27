"""
Hook SessionStart — inyecta resumen diario del agente de apuestas.
Salida: JSON con systemMessage para Claude Code.
"""
import sys
import json
from datetime import datetime
from pathlib import Path

HISTORICO = Path(__file__).parent / "backtesting" / "historico_apuestas.json"

def main():
    try:
        with open(HISTORICO, encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(json.dumps({"systemMessage": f"[Agente Apuestas] Error leyendo historico: {e}"}))
        return

    cr = [x for x in data if x.get("ganado") is not None]
    if not cr:
        print(json.dumps({"systemMessage": "[Agente Apuestas] Sin resultados registrados aun."}))
        return

    g = [x for x in cr if x["ganado"]]
    r = sum(x.get("retorno", 0) or 0 for x in cr)
    m = sum(x.get("monto_apostado", 0) or 0 for x in cr)
    roi = round(r / m * 100, 2) if m else 0
    wr = round(len(g) / len(cr) * 100, 1)

    # Ultimas 5
    ultimas = []
    for x in cr[-5:]:
        emoji = "✅" if x["ganado"] else "❌"
        fecha = x.get("fecha_partido", "")[:10]
        ultimas.append(f"  {emoji} {fecha} | {x.get('liga','?'):5s} | {x.get('seleccion','?')} | {x.get('cuota','?')} | {x.get('retorno',0):+,.0f}")

    # ROI status
    if roi >= 20 and len(cr) >= 20:
        status = "🟢 UMBRAL ALCANZADO — evaluar salir de paper trading"
    elif roi > 0:
        status = f"🟡 ROI positivo ({roi}%) — necesita n≥20 sostenido"
    else:
        status = f"🔴 ROI negativo ({roi}%) — n={len(cr)}/20 para evaluar"

    msg = (
        f"📊 AGENTE APUESTAS — {datetime.now().strftime('%Y-%m-%d')}\n"
        f"{'─'*45}\n"
        f"  Total resueltos : {len(cr)} | Ganadas: {len(g)} | WR: {wr}%\n"
        f"  ROI acumulado   : {roi}% | P&L: {r:+,.0f}\n"
        f"  {status}\n"
        f"{'─'*45}\n"
        f"Últimas 5:\n" + "\n".join(ultimas) + "\n"
        f"{'─'*45}\n"
        f"💡 Recordatorio: revisar predicciones de hoy y actualizar resultados pendientes."
    )

    print(json.dumps({"systemMessage": msg}))


if __name__ == "__main__":
    main()
