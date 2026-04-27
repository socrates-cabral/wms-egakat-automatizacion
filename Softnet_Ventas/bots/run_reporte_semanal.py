"""
Reporte semanal de cobranza — ejecuta lunes 08:00.
py C:\\ClaudeWork\\Softnet_Ventas\\bots\\run_reporte_semanal.py
"""
import sys
sys.stdout.reconfigure(encoding="utf-8")

from pathlib import Path
from datetime import date, timedelta
from dotenv import load_dotenv
import pandas as pd

_BASE = Path(__file__).resolve().parent.parent
load_dotenv(_BASE / ".env")
load_dotenv(_BASE.parent / ".env")

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sp_reader import leer_todos_meses_abiertos_consolidado
from claude_agent import llamar_claude
from telegram_utils import enviar_grupo_interno

SISTEMA_REPORTE = """Eres el analista de cobranza de Egakat SPA, empresa 3PL chilena.
Genera un briefing ejecutivo semanal de cobranza basado en los datos del Libro de Ventas.

Estructura EXACTA (respeta este orden):
1. Estado de cartera (total facturado, pendiente, % cobrado)
2. DSO de la semana
3. Gestión urgente (clientes vencidos > 30 días que requieren acción)
4. Pagos destacados (los 3 mayores pagos de la semana si los hay)
5. Próximos vencimientos (facturas que vencen esta semana)

FORMATO OBLIGATORIO (Telegram HTML):
- Títulos de sección: <b>1. TÍTULO</b>
- Listas con guion: - item
- Montos en formato chileno: $1.234.567
- Emojis solo para estados: ✅🔴⚠️
- NUNCA uses ** ## | --- ni tablas Markdown
- Máximo 400 palabras
- Fecha de hoy: {fecha}

Datos disponibles:
{datos}"""

_PLAZOS = [90, 60, 45, 30, 15]


def _detectar_plazo(forma_pago: str) -> int | None:
    texto = str(forma_pago).upper()
    for d in _PLAZOS:
        if str(d) in texto:
            return d
    return None


def _resumen_datos_reporte(df: pd.DataFrame) -> str:
    if df.empty:
        return "Sin datos disponibles."

    col = next((c for c in ("Razon Social", "Razón Social") if c in df.columns), df.columns[0])
    no_pagadas = df[df["Estado"] == "NO Pagado"]
    pagadas = df[df["Estado"] == "Pagado"]
    hoy = date.today()
    lineas = []

    lineas.append(f"Total documentos: {len(df)}")
    lineas.append(f"Facturación total: ${df['Total'].sum():,.0f}".replace(",", "."))
    lineas.append(f"Pendiente total: ${no_pagadas['Total'].sum():,.0f}".replace(",", "."))
    lineas.append(f"Cobrado total: ${pagadas['Total'].sum():,.0f}".replace(",", "."))
    pct = pagadas['Total'].sum() / df['Total'].sum() * 100 if df['Total'].sum() > 0 else 0
    lineas.append(f"% cobrado: {pct:.1f}%")

    if not pagadas.empty and "dias_cobro" in pagadas.columns:
        dso = pagadas["dias_cobro"].dropna()
        if not dso.empty:
            lineas.append(f"DSO promedio: {dso.mean():.1f} días")

    # Clientes vencidos > 30 días
    vencidos_30 = []
    for _, row in no_pagadas.iterrows():
        if pd.isna(row["Fecha"]):
            continue
        plazo = _detectar_plazo(row.get("Forma de Pago", ""))
        if plazo is None:
            continue
        fv = row["Fecha"].date() + timedelta(days=plazo)
        dias = (hoy - fv).days
        if dias > 30:
            vencidos_30.append((row.get(col, "—"), row["Total"], dias))

    if vencidos_30:
        lineas.append("\n--- VENCIDOS MÁS DE 30 DÍAS ---")
        from itertools import groupby
        clientes: dict = {}
        for cliente, monto, dias in vencidos_30:
            if cliente not in clientes:
                clientes[cliente] = {"total": 0, "max_dias": 0}
            clientes[cliente]["total"] += monto
            clientes[cliente]["max_dias"] = max(clientes[cliente]["max_dias"], dias)
        for cliente, datos in sorted(clientes.items(), key=lambda x: -x[1]["total"])[:8]:
            lineas.append(f"{cliente}: ${datos['total']:,.0f} | max {datos['max_dias']} días".replace(",", "."))

    # Pagos de la última semana
    hace_7 = hoy - timedelta(days=7)
    pagadas_semana = pagadas[pagadas["Fecha Ultimo pago"].dt.date >= hace_7] if not pagadas.empty else pd.DataFrame()
    if not pagadas_semana.empty:
        lineas.append("\n--- PAGOS ÚLTIMA SEMANA ---")
        top_pagos = pagadas_semana.nlargest(3, "Total")
        for _, row in top_pagos.iterrows():
            lineas.append(f"{row.get(col,'—')}: ${row['Total']:,.0f}".replace(",", "."))

    # Vencen esta semana
    proximos = []
    for _, row in no_pagadas.iterrows():
        if pd.isna(row["Fecha"]):
            continue
        plazo = _detectar_plazo(row.get("Forma de Pago", ""))
        if plazo is None:
            continue
        fv = row["Fecha"].date() + timedelta(days=plazo)
        if 0 <= (fv - hoy).days <= 7:
            proximos.append((row.get(col, "—"), row["Total"], fv))
    if proximos:
        lineas.append("\n--- VENCEN ESTA SEMANA ---")
        for cliente, monto, fv in sorted(proximos, key=lambda x: x[2]):
            lineas.append(f"{cliente}: ${monto:,.0f} — vence {fv.strftime('%d/%m')}".replace(",", "."))

    return "\n".join(lineas)


def run_reporte_semanal():
    print("[INFO] Generando reporte semanal de cobranza...")
    df = leer_todos_meses_abiertos_consolidado()
    datos_str = _resumen_datos_reporte(df)
    sistema = SISTEMA_REPORTE.format(
        fecha=date.today().strftime("%d/%m/%Y"),
        datos=datos_str,
    )
    historial = [{"role": "user", "content": "Genera el briefing semanal de cobranza con los datos disponibles."}]
    reporte = llamar_claude(sistema, historial, max_tokens=700)

    encabezado = f"📊 <b>COBRANZA — Semana {date.today().strftime('%d/%m/%Y')}</b>\n\n"
    enviar_grupo_interno(encabezado + reporte)
    print("[OK] Reporte semanal enviado al grupo Egakat Intel")


if __name__ == "__main__":
    run_reporte_semanal()
