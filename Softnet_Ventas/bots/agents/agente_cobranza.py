import sys
sys.stdout.reconfigure(encoding="utf-8")

from pathlib import Path
from datetime import date, timedelta
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from claude_agent import llamar_claude
from sp_reader import leer_todos_meses_abiertos_consolidado
from db_manager import get_historial, guardar_mensaje

SISTEMA = """Eres el analista de cobranza de Egakat SPA, empresa 3PL chilena.
Tienes acceso a los datos actualizados del Libro de Ventas.

Puedes responder sobre:
- Estado de cuentas por cobrar (pendientes, vencidas, pagadas)
- Proyección de cobros futuros por semana o mes
- Clientes con mayor exposición o riesgo
- Pagos recientes aplicados

FORMATO OBLIGATORIO (Telegram HTML):
- Títulos: <b>TÍTULO</b>
- Listas: líneas con guion (- item), NO tablas Markdown
- Montos: formato chileno $1.234.567
- Énfasis: <b>texto importante</b>
- NUNCA uses: ** ## | --- ni sintaxis Markdown ni tablas
- Emojis solo para estados: ✅ pagado, 🔴 crítico, ⚠️ alerta, 📅 proyección
- Máximo 400 palabras
- Si no tienes el dato exacto, di lo que tienes y lo que no
- Nunca inventes datos

Datos del Libro de Ventas (meses abiertos):
{datos}"""

_PLAZOS = [90, 60, 45, 30, 15]


def _detectar_plazo(forma_pago: str) -> int | None:
    texto = str(forma_pago).upper()
    for d in _PLAZOS:
        if str(d) in texto:
            return d
    return None


def _col_razon(df: pd.DataFrame) -> str:
    for c in ("Razon Social", "Razón Social"):
        if c in df.columns:
            return c
    return df.columns[0]


def _preparar_resumen_datos(df: pd.DataFrame) -> str:
    if df.empty:
        return "Sin datos disponibles."

    col = _col_razon(df)
    no_pagadas = df[df["Estado"] == "NO Pagado"]
    pagadas = df[df["Estado"] == "Pagado"]
    lineas = []

    lineas.append("=== RESUMEN GENERAL ===")
    lineas.append(f"Total documentos: {len(df)}")
    lineas.append(f"Facturación total: ${df['Total'].sum():,.0f}".replace(",", "."))
    lineas.append(f"Pendiente de cobro: ${no_pagadas['Total'].sum():,.0f}".replace(",", "."))
    lineas.append(f"Facturas pagadas: {len(pagadas)} | Sin pagar: {len(no_pagadas)}")

    if not pagadas.empty and "dias_cobro" in pagadas.columns:
        dso = pagadas["dias_cobro"].dropna()
        if not dso.empty:
            lineas.append(f"DSO promedio: {dso.mean():.1f} días")

    if not no_pagadas.empty:
        top = (no_pagadas.groupby(col)["Total"]
               .sum().sort_values(ascending=False).head(10))
        lineas.append("\n=== TOP CLIENTES CON SALDO PENDIENTE ===")
        for cliente, monto in top.items():
            lineas.append(f"- {cliente}: ${monto:,.0f}".replace(",", "."))

    # Vencidas según plazo contractual
    hoy = date.today()
    vencidas = []
    for _, row in no_pagadas.iterrows():
        if pd.isna(row["Fecha"]):
            continue
        plazo = _detectar_plazo(row.get("Forma de Pago", ""))
        if plazo is None:
            continue
        fv = row["Fecha"].date() + timedelta(days=plazo)
        dias = (hoy - fv).days
        if dias >= 1:
            vencidas.append((row.get(col, "—"), row["doc_id"], row["Total"], dias))

    if vencidas:
        lineas.append("\n=== FACTURAS VENCIDAS (sin pagar) ===")
        for cliente, doc, monto, dias in sorted(vencidas, key=lambda x: -x[3])[:15]:
            lineas.append(f"- {cliente} | {doc} | ${monto:,.0f} | {dias} días vencida".replace(",", "."))

    return "\n".join(lineas)


def _preparar_proyeccion_caja(df: pd.DataFrame) -> str:
    """Proyección de cobros futuros agrupada en buckets semanales."""
    if df.empty:
        return ""

    hoy = date.today()
    _SEMANAS = [
        ("Esta semana (próx 7 días)",  0,  6),
        ("Semana 2 (8-14 días)",       7,  13),
        ("Semana 3 (15-21 días)",      14, 20),
        ("Semana 4 (22-28 días)",      21, 27),
        ("Posterior (> 28 días)",      28, 999999),
    ]
    col = _col_razon(df)
    buckets: dict[str, list] = {nombre: [] for nombre, _, _ in _SEMANAS}

    for _, row in df[df["Estado"] != "Pagado"].iterrows():
        if pd.isna(row.get("Fecha")):
            continue
        plazo = _detectar_plazo(row.get("Forma de Pago", ""))
        if plazo is None:
            continue
        fv = row["Fecha"].date() + timedelta(days=plazo)
        if fv < hoy:
            continue
        dias = (fv - hoy).days
        monto = int(pd.to_numeric(row.get("Total", 0), errors="coerce") or 0)
        entry = (monto, f"- {row.get(col, '—')} | {row.get('doc_id','')} | "
                        f"${monto:,.0f} | vence {fv.strftime('%d/%m')}".replace(",", "."))
        for nombre, d0, d1 in _SEMANAS:
            if d0 <= dias <= d1:
                buckets[nombre].append(entry)
                break

    lineas = ["\n=== PROYECCIÓN DE COBROS FUTUROS ==="]
    for nombre, _, _ in _SEMANAS:
        items = sorted(buckets[nombre], key=lambda x: -x[0])
        total = sum(m for m, _ in items)
        if total > 0:
            lineas.append(f"\n{nombre}: ${total:,.0f} ({len(items)} docs)".replace(",", "."))
            for _, txt in items[:5]:
                lineas.append(txt)
    return "\n".join(lineas)


def responder(chat_id: int, mensaje: str, bot: str = "interno") -> str:
    """Genera respuesta con contexto del historial SQLite."""
    df = leer_todos_meses_abiertos_consolidado()
    datos_str = _preparar_resumen_datos(df) + _preparar_proyeccion_caja(df)
    sistema = SISTEMA.format(datos=datos_str)

    historial = get_historial(chat_id, bot, n=8)
    historial.append({"role": "user", "content": mensaje})

    respuesta = llamar_claude(sistema, historial, max_tokens=600)

    guardar_mensaje(chat_id, bot, "user", mensaje)
    guardar_mensaje(chat_id, bot, "assistant", respuesta)

    return respuesta
