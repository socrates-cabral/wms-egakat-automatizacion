import sys
sys.stdout.reconfigure(encoding="utf-8")

"""
reporte_performance.py
Genera un dashboard HTML con las métricas de performance del modelo de apuestas.

Métricas calculadas:
  - Precisión por tipo de apuesta (1X2, BTTS, OVER_UNDER, DOUBLE_CHANCE)
  - ROI por tipo y global
  - Yield (ganancia % por apuesta)
  - Evolución del bankroll virtual en el tiempo
  - Calibración del modelo (¿cuando digo X%, ocurre X% de las veces?)
  - Value bet hit rate
  - Rachas (mejor/peor racha consecutiva)
  - Comparativa flat vs Kelly (si hay ambas estrategias)

Output: backtesting/reporte_performance.html
"""

import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path

BACKTESTING_DIR = Path(__file__).parent
HISTORICO_PATH  = BACKTESTING_DIR / "historico_apuestas.json"
OUTPUT_DIR      = BACKTESTING_DIR.parent / "output"

# ── Colores (mismo dark theme que finanzas_personales) ───────────────────────
COLOR_BG       = "#0c1422"
COLOR_CARD     = "#0f1c2e"
COLOR_TEAL     = "#14b8a6"
COLOR_VERDE    = "#10b981"
COLOR_ROJO     = "#ef4444"
COLOR_AMARILLO = "#f59e0b"
COLOR_TEXTO    = "#cbd5e1"
COLOR_GRIS     = "#64748b"


# ─────────────────────────────────────────────────────────────────────────────
# CARGA Y FILTRADO
# ─────────────────────────────────────────────────────────────────────────────

def leer_historico() -> list[dict]:
    if not HISTORICO_PATH.exists():
        return []
    with open(HISTORICO_PATH, encoding="utf-8") as f:
        return json.load(f)


def filtrar_resueltas(apuestas: list[dict]) -> list[dict]:
    """Solo apuestas con resultado definitivo (ganado != None)."""
    return [a for a in apuestas if a.get("ganado") is not None]


# ─────────────────────────────────────────────────────────────────────────────
# CÁLCULO DE MÉTRICAS
# ─────────────────────────────────────────────────────────────────────────────

def calcular_metricas(apuestas: list[dict]) -> dict:
    """
    Calcula todas las métricas de performance a partir de las apuestas resueltas.
    """
    resueltas = filtrar_resueltas(apuestas)
    total     = len(resueltas)

    if total == 0:
        return {"sin_datos": True, "total": 0}

    ganadas     = [a for a in resueltas if a["ganado"] is True]
    perdidas    = [a for a in resueltas if a["ganado"] is False]
    total_apostado = sum(a["monto_apostado"] for a in resueltas)
    total_retorno  = sum(a.get("retorno", 0) for a in resueltas)

    # ── Por tipo de apuesta ───────────────────────────────────────────────────
    por_tipo = defaultdict(lambda: {"total": 0, "ganadas": 0, "apostado": 0, "retorno": 0})
    for a in resueltas:
        tipo = a["tipo_apuesta"]
        por_tipo[tipo]["total"]    += 1
        por_tipo[tipo]["apostado"] += a["monto_apostado"]
        por_tipo[tipo]["retorno"]  += a.get("retorno", 0)
        if a["ganado"]:
            por_tipo[tipo]["ganadas"] += 1

    tipos_stats = {}
    for tipo, d in por_tipo.items():
        precision = d["ganadas"] / d["total"] * 100 if d["total"] else 0
        roi       = d["retorno"] / d["apostado"] * 100 if d["apostado"] else 0
        yield_pct = d["retorno"] / d["total"] / (d["apostado"] / d["total"]) * 100 if d["total"] else 0
        tipos_stats[tipo] = {
            "total":     d["total"],
            "ganadas":   d["ganadas"],
            "precision": round(precision, 1),
            "roi":       round(roi, 1),
            "yield_pct": round(yield_pct, 1),
        }

    # ── Evolución bankroll ────────────────────────────────────────────────────
    from backtesting.simulador import BANKROLL_INICIAL

    bankroll_evo = []
    bankroll_cur = BANKROLL_INICIAL
    for a in sorted(resueltas, key=lambda x: x.get("fecha_registro", "")):
        bankroll_cur += a.get("retorno", 0)
        bankroll_evo.append({
            "fecha":    a.get("fecha_registro", "")[:10],
            "partido":  f"{a['home']} vs {a['away']}",
            "bankroll": round(bankroll_cur, 0),
            "ganado":   a["ganado"],
        })

    # ── Rachas ────────────────────────────────────────────────────────────────
    mejor_racha = peor_racha = racha_actual = 0
    racha_temp_pos = racha_temp_neg = 0
    for a in sorted(resueltas, key=lambda x: x.get("fecha_registro", "")):
        if a["ganado"]:
            racha_temp_pos += 1
            racha_temp_neg  = 0
            mejor_racha     = max(mejor_racha, racha_temp_pos)
            racha_actual    = racha_temp_pos
        else:
            racha_temp_neg += 1
            racha_temp_pos  = 0
            peor_racha      = max(peor_racha, racha_temp_neg)
            racha_actual    = -racha_temp_neg

    # ── Calibración del modelo ────────────────────────────────────────────────
    # Agrupar por decil de probabilidad predicha
    calibracion = defaultdict(lambda: {"total": 0, "ganadas": 0})
    for a in resueltas:
        decil = round(a["prob_modelo"] * 10) * 10   # 50, 60, 70, etc.
        calibracion[decil]["total"]  += 1
        if a["ganado"]:
            calibracion[decil]["ganadas"] += 1

    calibracion_lista = []
    for decil in sorted(calibracion):
        d = calibracion[decil]
        real_pct = d["ganadas"] / d["total"] * 100 if d["total"] else 0
        calibracion_lista.append({
            "predicho": decil,
            "real":     round(real_pct, 1),
            "n":        d["total"],
        })

    # ── Value bet hit rate ────────────────────────────────────────────────────
    value_bets = [a for a in resueltas if a.get("value", 0) > 0.05]
    vb_ganadas = [a for a in value_bets if a["ganado"]]
    vb_hit_rate = len(vb_ganadas) / len(value_bets) * 100 if value_bets else 0

    return {
        "sin_datos":       False,
        "total":           total,
        "ganadas":         len(ganadas),
        "perdidas":        len(perdidas),
        "precision_global": round(len(ganadas) / total * 100, 1),
        "total_apostado":  total_apostado,
        "total_retorno":   total_retorno,
        "roi_global":      round(total_retorno / total_apostado * 100, 1) if total_apostado else 0,
        "yield_global":    round(total_retorno / total * 100 / (total_apostado / total), 1) if total else 0,
        "bankroll_actual": bankroll_evo[-1]["bankroll"] if bankroll_evo else BANKROLL_INICIAL,
        "bankroll_inicial": BANKROLL_INICIAL,
        "bankroll_evo":    bankroll_evo,
        "mejor_racha":     mejor_racha,
        "peor_racha":      peor_racha,
        "racha_actual":    racha_actual,
        "por_tipo":        tipos_stats,
        "calibracion":     calibracion_lista,
        "value_bets_total": len(value_bets),
        "value_bets_hit":   round(vb_hit_rate, 1),
    }


# ─────────────────────────────────────────────────────────────────────────────
# GENERACIÓN HTML
# ─────────────────────────────────────────────────────────────────────────────

def _color_roi(roi: float) -> str:
    if roi > 5:   return COLOR_VERDE
    if roi > 0:   return COLOR_TEAL
    if roi > -5:  return COLOR_AMARILLO
    return COLOR_ROJO


def _semaforo(roi: float) -> str:
    if roi > 5:   return "✅"
    if roi > 0:   return "🟡"
    if roi > -5:  return "⚠️"
    return "❌"


def generar_html(metricas: dict) -> str:
    """Genera el HTML completo del reporte de performance."""

    if metricas.get("sin_datos"):
        return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<style>body{{background:{COLOR_BG};color:{COLOR_TEXTO};font-family:monospace;
text-align:center;padding:80px}}</style></head>
<body><h1 style="color:{COLOR_TEAL}">Sin datos aún</h1>
<p>No hay apuestas resueltas en historico_apuestas.json.<br>
Registra apuestas con simulador.py y verifica resultados con resultado_checker.py.</p>
</body></html>"""

    # Datos clave
    bankroll_delta = metricas["bankroll_actual"] - metricas["bankroll_inicial"]
    bankroll_pct   = bankroll_delta / metricas["bankroll_inicial"] * 100
    b_color        = COLOR_VERDE if bankroll_delta >= 0 else COLOR_ROJO

    # Filas tabla por tipo
    filas_tipos = ""
    for tipo, s in metricas["por_tipo"].items():
        roi_color = _color_roi(s["roi"])
        semaforo  = _semaforo(s["roi"])
        filas_tipos += f"""
        <tr>
          <td style="color:{COLOR_TEAL}">{tipo}</td>
          <td>{s['total']}</td>
          <td>{s['ganadas']}</td>
          <td>{s['precision']}%</td>
          <td style="color:{roi_color}">{s['roi']:+.1f}% {semaforo}</td>
        </tr>"""

    # Datos evolución bankroll para Plotly
    evo_fechas   = [e["fecha"]    for e in metricas["bankroll_evo"]]
    evo_bankroll = [e["bankroll"] for e in metricas["bankroll_evo"]]
    evo_colores  = [COLOR_VERDE if e["ganado"] else COLOR_ROJO
                    for e in metricas["bankroll_evo"]]
    evo_textos   = [e["partido"]  for e in metricas["bankroll_evo"]]

    # Datos calibración para Plotly
    cal_x        = [c["predicho"] for c in metricas["calibracion"]]
    cal_real     = [c["real"]     for c in metricas["calibracion"]]
    cal_n        = [c["n"]        for c in metricas["calibracion"]]

    racha_actual = metricas["racha_actual"]
    racha_texto  = (f"+{racha_actual} ganadas seguidas" if racha_actual > 0
                    else f"{abs(racha_actual)} perdidas seguidas" if racha_actual < 0
                    else "Sin racha activa")
    racha_color  = COLOR_VERDE if racha_actual > 0 else (COLOR_ROJO if racha_actual < 0 else COLOR_GRIS)

    fecha_reporte = datetime.now().strftime("%d/%m/%Y %H:%M")

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Performance Modelo Apuestas</title>
  <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background: {COLOR_BG};
      color: {COLOR_TEXTO};
      font-family: 'Segoe UI', system-ui, sans-serif;
      padding: 24px;
    }}
    h1 {{ color: {COLOR_TEAL}; font-size: 1.6rem; margin-bottom: 4px; }}
    .subtitle {{ color: {COLOR_GRIS}; font-size: 0.85rem; margin-bottom: 24px; }}
    .grid-4 {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 16px;
      margin-bottom: 24px;
    }}
    .card {{
      background: {COLOR_CARD};
      border-radius: 10px;
      padding: 20px;
      border: 1px solid #1e2d3d;
    }}
    .card-label {{ color: {COLOR_GRIS}; font-size: 0.75rem; text-transform: uppercase;
                   letter-spacing: 0.05em; margin-bottom: 8px; }}
    .card-value {{ font-size: 1.8rem; font-weight: 700; }}
    .card-sub   {{ font-size: 0.8rem; color: {COLOR_GRIS}; margin-top: 4px; }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 0.9rem;
    }}
    th {{
      color: {COLOR_GRIS};
      text-align: left;
      padding: 8px 12px;
      border-bottom: 1px solid #1e2d3d;
      font-size: 0.75rem;
      text-transform: uppercase;
    }}
    td {{ padding: 10px 12px; border-bottom: 1px solid #1a2535; }}
    tr:hover td {{ background: #12202f; }}
    .chart-container {{ margin-bottom: 24px; }}
    .grid-2 {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 16px;
      margin-bottom: 24px;
    }}
    @media (max-width: 700px) {{ .grid-2 {{ grid-template-columns: 1fr; }} }}
  </style>
</head>
<body>

<h1>⚽ Performance del Modelo de Apuestas</h1>
<div class="subtitle">Última actualización: {fecha_reporte} · {metricas['total']} apuestas resueltas</div>

<!-- KPIs principales -->
<div class="grid-4">
  <div class="card">
    <div class="card-label">Precisión global</div>
    <div class="card-value" style="color:{COLOR_TEAL}">{metricas['precision_global']}%</div>
    <div class="card-sub">{metricas['ganadas']}G / {metricas['perdidas']}P</div>
  </div>
  <div class="card">
    <div class="card-label">ROI global</div>
    <div class="card-value" style="color:{_color_roi(metricas['roi_global'])}">{metricas['roi_global']:+.1f}%</div>
    <div class="card-sub">Yield: {metricas['yield_global']:+.1f}%</div>
  </div>
  <div class="card">
    <div class="card-label">Bankroll actual</div>
    <div class="card-value" style="color:{b_color}">${metricas['bankroll_actual']:,.0f}</div>
    <div class="card-sub" style="color:{b_color}">{bankroll_pct:+.1f}% vs inicial</div>
  </div>
  <div class="card">
    <div class="card-label">Racha actual</div>
    <div class="card-value" style="color:{racha_color};font-size:1.2rem">{racha_texto}</div>
    <div class="card-sub">Mejor: +{metricas['mejor_racha']} · Peor: -{metricas['peor_racha']}</div>
  </div>
</div>

<!-- Value bets -->
<div class="grid-4" style="margin-bottom:24px">
  <div class="card">
    <div class="card-label">Value bets (>5%)</div>
    <div class="card-value" style="color:{COLOR_TEAL}">{metricas['value_bets_hit']}%</div>
    <div class="card-sub">{metricas['value_bets_total']} apuestas con value</div>
  </div>
  <div class="card">
    <div class="card-label">Total apostado</div>
    <div class="card-value">${metricas['total_apostado']:,.0f}</div>
    <div class="card-sub">CLP simulados</div>
  </div>
  <div class="card">
    <div class="card-label">Retorno neto</div>
    <div class="card-value" style="color:{b_color}">${metricas['total_retorno']:+,.0f}</div>
    <div class="card-sub">CLP</div>
  </div>
</div>

<!-- Evolución bankroll -->
<div class="card chart-container">
  <div class="card-label" style="margin-bottom:12px">Evolución del Bankroll</div>
  <div id="chart-bankroll"></div>
</div>

<!-- Por tipo + Calibración -->
<div class="grid-2">
  <div class="card">
    <div class="card-label" style="margin-bottom:12px">Performance por tipo de apuesta</div>
    <table>
      <tr><th>Tipo</th><th>PJ</th><th>G</th><th>Precisión</th><th>ROI</th></tr>
      {filas_tipos}
    </table>
  </div>
  <div class="card">
    <div class="card-label" style="margin-bottom:12px">Calibración del modelo</div>
    <div id="chart-calibracion"></div>
    <div class="card-sub" style="margin-top:8px">
      Ideal: la línea real sigue la línea diagonal (predicho = real)
    </div>
  </div>
</div>

<script>
// ── Gráfico evolución bankroll ────────────────────────────────────────────
var evo_fechas   = {json.dumps(evo_fechas)};
var evo_bankroll = {json.dumps(evo_bankroll)};
var evo_colores  = {json.dumps(evo_colores)};
var evo_textos   = {json.dumps(evo_textos)};

Plotly.newPlot('chart-bankroll', [
  {{
    x: evo_fechas,
    y: evo_bankroll,
    type: 'scatter',
    mode: 'lines+markers',
    line:   {{ color: '{COLOR_TEAL}', width: 2 }},
    marker: {{ color: evo_colores, size: 8 }},
    text:   evo_textos,
    hovertemplate: '%{{text}}<br>Bankroll: $%{{y:,.0f}}<extra></extra>',
    name: 'Bankroll',
  }}
], {{
  paper_bgcolor: '{COLOR_CARD}',
  plot_bgcolor:  '{COLOR_CARD}',
  font:          {{ color: '{COLOR_TEXTO}', size: 12 }},
  xaxis:         {{ gridcolor: '#1e2d3d', showgrid: true }},
  yaxis:         {{ gridcolor: '#1e2d3d', showgrid: true, tickformat: '$,.0f' }},
  margin:        {{ t: 10, r: 10, b: 40, l: 70 }},
  height:        280,
  showlegend:    false,
}}, {{ responsive: true, displayModeBar: false }});

// ── Gráfico calibración ───────────────────────────────────────────────────
var cal_x    = {json.dumps(cal_x)};
var cal_real = {json.dumps(cal_real)};
var cal_n    = {json.dumps(cal_n)};

Plotly.newPlot('chart-calibracion', [
  {{
    x: cal_x,
    y: cal_real,
    type: 'bar',
    marker: {{ color: '{COLOR_TEAL}', opacity: 0.8 }},
    text:  cal_n.map(n => 'n=' + n),
    textposition: 'outside',
    hovertemplate: 'Predicho: %{{x}}%<br>Real: %{{y:.1f}}%<br>%{{text}}<extra></extra>',
    name: 'Real',
  }},
  {{
    x: [40, 50, 60, 70, 80, 90, 100],
    y: [40, 50, 60, 70, 80, 90, 100],
    type: 'scatter',
    mode: 'lines',
    line: {{ color: '{COLOR_AMARILLO}', width: 1, dash: 'dash' }},
    name: 'Ideal',
    hoverinfo: 'skip',
  }}
], {{
  paper_bgcolor: '{COLOR_CARD}',
  plot_bgcolor:  '{COLOR_CARD}',
  font:  {{ color: '{COLOR_TEXTO}', size: 11 }},
  xaxis: {{ gridcolor: '#1e2d3d', title: 'Prob. predicha (%)', range: [35, 105] }},
  yaxis: {{ gridcolor: '#1e2d3d', title: 'Prob. real (%)',     range: [0, 110] }},
  margin: {{ t: 10, r: 10, b: 50, l: 55 }},
  height: 240,
  legend: {{ orientation: 'h', y: -0.25 }},
}}, {{ responsive: true, displayModeBar: false }});
</script>

</body>
</html>"""

    return html


# ─────────────────────────────────────────────────────────────────────────────
# PUNTO DE ENTRADA
# ─────────────────────────────────────────────────────────────────────────────

def generar_reporte() -> Path:
    """Calcula métricas, genera HTML y guarda el archivo en output/."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    fecha       = datetime.now().strftime("%Y-%m-%d")
    reporte_path = OUTPUT_DIR / f"performance_{fecha}.html"

    apuestas = leer_historico()
    metricas = calcular_metricas(apuestas)

    html = generar_html(metricas)
    reporte_path.write_text(html, encoding="utf-8")

    print(f"[OK] Reporte generado: {reporte_path}")

    if not metricas.get("sin_datos"):
        print(f"     Apuestas: {metricas['total']} | "
              f"Precisión: {metricas['precision_global']}% | "
              f"ROI: {metricas['roi_global']:+.1f}% | "
              f"Bankroll: ${metricas['bankroll_actual']:,.0f}")

    return reporte_path


if __name__ == "__main__":
    print("=" * 60)
    print("REPORTE PERFORMANCE — generando HTML...")
    print("=" * 60)
    print()
    ruta = generar_reporte()
    print(f"\nAbrir en navegador: {ruta}")
