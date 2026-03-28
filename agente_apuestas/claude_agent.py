import sys
sys.stdout.reconfigure(encoding="utf-8")

"""
claude_agent.py
Genera el análisis narrativo de cada partido usando Claude API,
y produce el reporte HTML diario del agente de apuestas.

Claude model: claude-haiku-4-5-20251001 (rápido y económico para uso diario)
Fallback: análisis template si ANTHROPIC_API_KEY no está disponible.

Output: output/reporte_YYYY-MM-DD.html
"""

import json
import os
from datetime import datetime
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent))
from dotenv import load_dotenv
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

# ─── SDK flags (importados una vez para no repetir try/except en cada llamada) ─
try:
    import anthropic as _anthropic_sdk
    _HAS_ANTHROPIC = True
except ImportError:
    _HAS_ANTHROPIC = False

try:
    from openai import OpenAI as _OpenAI
    _HAS_OPENAI = True
except ImportError:
    _HAS_OPENAI = False

try:
    from google import genai as _genai
    _HAS_GEMINI = True
except ImportError:
    _HAS_GEMINI = False

OUTPUT_DIR = Path(__file__).parent / "output"

# Colores dark theme (mismo que finanzas_personales)
C_BG      = "#0c1422"
C_CARD    = "#0f1c2e"
C_TEAL    = "#14b8a6"
C_VERDE   = "#10b981"
C_ROJO    = "#ef4444"
C_AMBER   = "#f59e0b"
C_TEXTO   = "#cbd5e1"
C_GRIS    = "#64748b"
C_BORDER  = "#1e2d3d"


# ─────────────────────────────────────────────────────────────────────────────
# LLM BACKENDS — Claude → OpenAI → Gemini → template
# ─────────────────────────────────────────────────────────────────────────────

def _try_claude(prompt: str) -> str | None:
    """Intenta análisis con Claude Haiku. Retorna texto o None si falla."""
    if not _HAS_ANTHROPIC:
        return None
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    try:
        client = _anthropic_sdk.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=180,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text.strip()
    except Exception as e:
        print(f"[AVISO] Claude API error: {e} — intentando OpenAI")
        return None


def _try_openai(prompt: str) -> str | None:
    """Intenta análisis con GPT-4o-mini. Retorna texto o None si falla."""
    if not _HAS_OPENAI:
        return None
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    try:
        client = _OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=180,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"[AVISO] OpenAI API error: {e} — intentando Gemini")
        return None


def _try_gemini(prompt: str) -> str | None:
    """Intenta análisis con Gemini 2.5 Flash. Retorna texto o None si falla."""
    if not _HAS_GEMINI:
        return None
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return None
    try:
        client = _genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model="models/gemini-2.5-flash",
            contents=prompt,
        )
        return response.text.strip()
    except Exception as e:
        print(f"[AVISO] Gemini API error: {e} — usando template")
        return None


def _build_prompt(partido_data: dict) -> str:
    """Construye el prompt de análisis a partir de los datos del partido."""
    fixture = partido_data["fixture"]
    stats   = partido_data.get("stats", {})
    pred    = partido_data.get("prediccion", {})
    recs    = partido_data.get("recomendaciones", [])

    home = fixture.get("home_nombre", "?")
    away = fixture.get("away_nombre", "?")
    liga = fixture.get("liga_nombre", "?")
    h2h  = stats.get("resumen_h2h", {})
    sh   = stats.get("stats_home", {})
    sa   = stats.get("stats_away", {})

    recs_texto = "; ".join(
        f"{r['tipo_apuesta']} {r['seleccion']} @ {r['cuota']} "
        f"(value {r['value']:+.1%}, confianza {r['confianza']}/100)"
        for r in recs
    ) or "ninguna"

    return (
        f"Analiza este partido deportivo para apuestas. Responde en español, máximo 3 frases concisas.\n"
        f"Estructura: [señal más fuerte] → [riesgo principal] → [veredicto].\n\n"
        f"Partido: {home} vs {away} | {liga}\n"
        f"H2H ({h2h.get('total', 0)} partidos): {home} ganó {h2h.get('home_wins', 0)}, "
        f"empates {h2h.get('draws', 0)}, {away} ganó {h2h.get('away_wins', 0)}\n"
        f"Forma {home}: {sh.get('forma', 'N/A')} | Forma {away}: {sa.get('forma', 'N/A')}\n"
        f"Consejos API-Sports: {pred.get('advice') or 'no disponible'}\n"
        f"Value bets detectadas: {recs_texto}"
    )


def analizar_con_claude(partido_data: dict) -> str:
    """
    Genera análisis narrativo de un partido en 2-3 frases.
    Orden de intento: Claude Haiku → GPT-4o-mini → Gemini 2.5 Flash → template.
    """
    prompt = _build_prompt(partido_data)

    resultado = _try_claude(prompt)
    if resultado:
        return resultado

    resultado = _try_openai(prompt)
    if resultado:
        return resultado

    resultado = _try_gemini(prompt)
    if resultado:
        return resultado

    return _analisis_template(partido_data)


def _analisis_template(partido_data: dict) -> str:
    """Análisis automático sin API cuando Claude no está disponible."""
    recs   = partido_data.get("recomendaciones", [])
    stats  = partido_data.get("stats", {})
    h2h    = stats.get("resumen_h2h", {})
    pred   = partido_data.get("prediccion", {})

    partes = []

    if h2h.get("total", 0) >= 3:
        ganador_h2h = ("local" if h2h.get("home_wins", 0) > h2h.get("away_wins", 0)
                       else "visitante" if h2h.get("away_wins", 0) > h2h.get("home_wins", 0)
                       else "sin dominancia clara")
        partes.append(f"H2H ({h2h['total']} partidos) favorece al {ganador_h2h}.")

    if pred.get("advice"):
        partes.append(pred["advice"])

    if recs:
        top = recs[0]
        partes.append(
            f"Mejor apuesta detectada: {top['tipo_apuesta']} {top['seleccion']} "
            f"@ {top['cuota']} con {top['value']:+.1%} de value y confianza {top['confianza']}/100."
        )
    else:
        partes.append("No se detectaron value bets en este partido.")

    return " ".join(partes) if partes else "Análisis no disponible."


# ─────────────────────────────────────────────────────────────────────────────
# GENERACIÓN HTML
# ─────────────────────────────────────────────────────────────────────────────

def _badge_confianza(score: int, nivel: str) -> str:
    color = C_VERDE if score >= 70 else C_AMBER if score >= 55 else C_ROJO
    return (f'<span style="background:{color}22;color:{color};padding:3px 10px;'
            f'border-radius:12px;font-size:11px;font-weight:600">{nivel} {score}/100</span>')


def _badge_value(value: float) -> str:
    color = C_VERDE if value >= 0.10 else C_TEAL if value >= 0.05 else C_AMBER
    return (f'<span style="background:{color}22;color:{color};padding:3px 8px;'
            f'border-radius:8px;font-size:11px">VALUE {value:+.1%}</span>')


def _card_partido(partido_data: dict, narrativa: str) -> str:
    """Genera el HTML de una card de partido."""
    f      = partido_data["fixture"]
    stats  = partido_data.get("stats", {})
    pred   = partido_data.get("prediccion", {})
    cuotas = partido_data.get("cuotas", {})
    lineup = partido_data.get("lineup", {})
    recs   = partido_data.get("recomendaciones", [])
    bets_v = [b for b in partido_data.get("value_bets", []) if b.get("tiene_value")]

    home = f.get("home_nombre", "?")
    away = f.get("away_nombre", "?")
    liga = f.get("liga_nombre", "?")
    hora = f.get("fecha", "")
    if hora:
        try:
            hora = datetime.fromisoformat(hora.replace("Z", "+00:00")).strftime("%H:%M")
        except Exception:
            hora = hora[:16]

    h2h  = stats.get("resumen_h2h", {})
    sh   = stats.get("stats_home", {})
    sa   = stats.get("stats_away", {})

    # Cuotas 1X2 display
    h2h_c = (cuotas or {}).get("h2h", {})
    cuota_home = h2h_c.get("home", "—")
    cuota_draw = h2h_c.get("draw", "—")
    cuota_away = h2h_c.get("away", "—")

    # Recomendaciones HTML
    recs_html = ""
    if recs:
        for r in recs:
            badge_c = _badge_confianza(r["confianza"], r["confianza_nivel"])
            badge_v = _badge_value(r["value"])
            recs_html += f"""
            <div style="background:{C_BG};border:1px solid {C_BORDER};border-radius:8px;
                        padding:12px 16px;margin-bottom:10px;">
              <div style="display:flex;justify-content:space-between;align-items:center;
                          flex-wrap:wrap;gap:8px">
                <div>
                  <span style="color:{C_TEAL};font-weight:700;font-size:1rem">
                    {r['tipo_apuesta']} → {r['seleccion']}
                  </span>
                  <span style="color:{C_TEXTO};font-size:0.9rem;margin-left:12px">
                    @ <strong style="color:white">{r['cuota']}</strong>
                  </span>
                </div>
                <div style="display:flex;gap:8px;flex-wrap:wrap">
                  {badge_v}
                  {badge_c}
                </div>
              </div>
              <div style="color:{C_GRIS};font-size:0.8rem;margin-top:6px">
                Modelo: {r['prob_modelo']:.1%} vs implícita: {r['prob_implicita'] or 0:.1%}
                &nbsp;·&nbsp; Score final: {r['score_final']:.4f}
              </div>
            </div>"""
    else:
        recs_html = f'<p style="color:{C_GRIS};font-style:italic">Sin value bets con confianza suficiente.</p>'

    # Stat pills
    def pill(label, val, color=C_GRIS):
        return (f'<span style="background:{color}22;color:{color};border-radius:6px;'
                f'padding:2px 8px;font-size:0.75rem;margin-right:4px">{label}: {val}</span>')

    pct_h = pred.get("pct_home", "—")
    pct_d = pred.get("pct_draw", "—")
    pct_a = pred.get("pct_away", "—")
    uo    = pred.get("under_over", "—")
    goles = (f"{pred.get('goles_esperados_home', '?')}-{pred.get('goles_esperados_away', '?')}"
             if pred else "—")

    lineup_txt = ""
    if lineup:
        conf = "✅ Confirmado" if lineup.get("lineup_confirmado") else "⏳ Pendiente"
        bh   = len(lineup.get("home", {}).get("bajas", []))
        ba   = len(lineup.get("away", {}).get("bajas", []))
        lineup_txt = f'<div style="color:{C_GRIS};font-size:0.8rem;margin-top:4px">Lineup: {conf} &nbsp;·&nbsp; Bajas: {home} {bh} / {away} {ba}</div>'

    return f"""
    <div style="background:{C_CARD};border:1px solid {C_BORDER};border-radius:12px;
                padding:20px;margin-bottom:20px;">

      <!-- Header partido -->
      <div style="display:flex;justify-content:space-between;align-items:flex-start;
                  flex-wrap:wrap;gap:8px;margin-bottom:16px">
        <div>
          <div style="font-size:1.2rem;font-weight:700;color:white">
            {home} <span style="color:{C_GRIS}">vs</span> {away}
          </div>
          <div style="color:{C_GRIS};font-size:0.85rem;margin-top:2px">
            {liga} &nbsp;·&nbsp; {hora} UTC
          </div>
          {lineup_txt}
        </div>
        <div style="text-align:right">
          <div style="color:{C_GRIS};font-size:0.75rem">Cuotas mercado</div>
          <div style="font-size:0.9rem;color:{C_TEXTO}">
            <span style="color:{C_TEAL}">{cuota_home}</span>
            &nbsp;/&nbsp; {cuota_draw}
            &nbsp;/&nbsp; <span style="color:{C_AMBER}">{cuota_away}</span>
          </div>
        </div>
      </div>

      <!-- Stats rápidas -->
      <div style="margin-bottom:14px;display:flex;flex-wrap:wrap;gap:4px">
        {pill(f'H2H', f"{h2h.get('home_wins',0)}-{h2h.get('draws',0)}-{h2h.get('away_wins',0)}", C_TEAL)}
        {pill('Pred H/D/A', f'{pct_h}/{pct_d}/{pct_a}')}
        {pill('U/O', uo)}
        {pill('Goles esp.', goles)}
        {pill(f'Forma {home[:6]}', sh.get('forma','?'))}
        {pill(f'Forma {away[:6]}', sa.get('forma','?'))}
      </div>

      <!-- Recomendaciones -->
      <div style="margin-bottom:14px">
        <div style="color:{C_GRIS};font-size:0.75rem;text-transform:uppercase;
                    letter-spacing:0.05em;margin-bottom:8px">Recomendaciones</div>
        {recs_html}
      </div>

      <!-- Narrativa Claude -->
      <div style="border-top:1px solid {C_BORDER};padding-top:12px;
                  color:{C_TEXTO};font-size:0.88rem;line-height:1.6;
                  font-style:italic">
        {narrativa}
      </div>
    </div>"""


def _bloque_riesgo_html(riesgo: dict) -> str:
    """Genera el bloque HTML de estado del bankroll y control de riesgo."""
    if not riesgo:
        return ""

    color_map = {"verde": C_VERDE, "amarillo": C_AMBER, "rojo": C_ROJO}
    estado_color = riesgo.get("estado_color", "verde")
    color_hex = color_map.get(estado_color, C_VERDE)
    bloqueado = riesgo.get("bloqueado", False)

    bankroll      = riesgo.get("bankroll_actual", 0)
    expo_hoy      = riesgo.get("exposicion_hoy", 0)
    apuestas_hoy  = riesgo.get("apuestas_hoy", 0)
    kelly_factor  = riesgo.get("kelly_factor", 1.0)

    alertas_html = ""
    for alerta in riesgo.get("alertas", []):
        alertas_html += (
            f'<div style="color:{C_AMBER};font-size:0.8rem;margin-top:6px">{alerta}</div>'
        )

    bloqueo_html = ""
    if bloqueado:
        motivo = riesgo.get("motivo", "")
        bloqueo_html = f"""
        <div style="background:{C_ROJO}22;border:1px solid {C_ROJO};border-radius:8px;
                    padding:12px 16px;margin-top:12px;color:{C_ROJO};font-size:0.85rem">
          🚫 <strong>SISTEMA BLOQUEADO:</strong> {motivo}
        </div>"""

    kelly_txt = (f"Kelly ×{kelly_factor}"
                 if kelly_factor < 1.0
                 else "Kelly normal")
    expo_pct  = (expo_hoy / bankroll * 100) if bankroll else 0

    return f"""
<div style="background:{C_CARD};border:1px solid {color_hex}44;border-radius:12px;
            padding:16px 20px;margin-bottom:20px">
  <div style="display:flex;align-items:center;gap:10px;margin-bottom:12px">
    <div style="width:10px;height:10px;border-radius:50%;background:{color_hex}"></div>
    <span style="font-weight:600;font-size:0.95rem">Estado del Bankroll
      — <span style="color:{color_hex}">{estado_color.upper()}</span>
    </span>
  </div>
  <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:10px">
    <div>
      <div style="color:{C_GRIS};font-size:0.7rem;text-transform:uppercase">Bankroll actual</div>
      <div style="font-size:1.2rem;font-weight:700;color:{C_TEAL}">${bankroll:,.0f} CLP</div>
    </div>
    <div>
      <div style="color:{C_GRIS};font-size:0.7rem;text-transform:uppercase">Exposición hoy</div>
      <div style="font-size:1.2rem;font-weight:700;color:{C_TEXTO}">${expo_hoy:,.0f}
        <span style="font-size:0.75rem;color:{C_GRIS}">({expo_pct:.1f}%)</span>
      </div>
    </div>
    <div>
      <div style="color:{C_GRIS};font-size:0.7rem;text-transform:uppercase">Apuestas hoy</div>
      <div style="font-size:1.2rem;font-weight:700;color:{C_TEXTO}">{apuestas_hoy}/5</div>
    </div>
    <div>
      <div style="color:{C_GRIS};font-size:0.7rem;text-transform:uppercase">Kelly</div>
      <div style="font-size:1.2rem;font-weight:700;
                  color:{'#ef4444' if kelly_factor < 1 else C_VERDE}">{kelly_txt}</div>
    </div>
  </div>
  {alertas_html}
  {bloqueo_html}
</div>"""


def generar_reporte_html(
    partidos_analizados: list[dict],
    fecha: str = None,
    riesgo: dict = None,
) -> Path:
    """
    Genera el HTML completo del reporte diario.

    Args:
        partidos_analizados: lista de dicts (output de run_agent.py)
        fecha:  string YYYY-MM-DD — default hoy
        riesgo: dict de verificar_limites_riesgo() — muestra bloque bankroll

    Returns:
        Path del HTML generado.
    """
    if fecha is None:
        fecha = datetime.now().strftime("%Y-%m-%d")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    reporte_path = OUTPUT_DIR / f"reporte_{fecha}.html"

    total_partidos = len(partidos_analizados)
    total_recs     = sum(len(p.get("recomendaciones", [])) for p in partidos_analizados)
    fecha_display  = datetime.now().strftime("%d/%m/%Y %H:%M")

    # Bloque de estado de riesgo/bankroll
    riesgo_html = _bloque_riesgo_html(riesgo) if riesgo else ""

    # Tarjetas de partidos (con narrativa Claude)
    cards_html = ""
    if partidos_analizados:
        for pd in partidos_analizados:
            narrativa  = analizar_con_claude(pd)
            cards_html += _card_partido(pd, narrativa)
    else:
        cards_html = f"""
        <div style="text-align:center;padding:60px 20px;color:{C_GRIS}">
          <div style="font-size:3rem;margin-bottom:16px">🎯</div>
          <div style="font-size:1.1rem">No hay partidos con value bets para hoy.</div>
          <div style="font-size:0.85rem;margin-top:8px">
            Verifica que las APIs están configuradas y hay partidos en las ligas activas.
          </div>
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Agente Apuestas — {fecha}</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background: {C_BG};
      color: {C_TEXTO};
      font-family: 'Segoe UI', system-ui, sans-serif;
      padding: 24px;
      max-width: 900px;
      margin: 0 auto;
    }}
    h1 {{ color: {C_TEAL}; font-size: 1.5rem; }}
    .subtitle {{ color: {C_GRIS}; font-size: 0.85rem; margin-bottom: 24px; margin-top: 4px; }}
    .kpi-row {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
      gap: 12px;
      margin-bottom: 24px;
    }}
    .kpi {{
      background: {C_CARD};
      border: 1px solid {C_BORDER};
      border-radius: 10px;
      padding: 14px 16px;
    }}
    .kpi-label {{ color: {C_GRIS}; font-size: 0.72rem; text-transform: uppercase;
                  letter-spacing: 0.05em; margin-bottom: 6px; }}
    .kpi-val   {{ font-size: 1.6rem; font-weight: 700; color: {C_TEAL}; }}
  </style>
</head>
<body>

<h1>⚽ Agente de Apuestas Deportivas</h1>
<div class="subtitle">Reporte del {fecha} &nbsp;·&nbsp; Generado: {fecha_display}</div>

{riesgo_html}

<div class="kpi-row">
  <div class="kpi">
    <div class="kpi-label">Partidos analizados</div>
    <div class="kpi-val">{total_partidos}</div>
  </div>
  <div class="kpi">
    <div class="kpi-label">Recomendaciones</div>
    <div class="kpi-val">{total_recs}</div>
  </div>
  <div class="kpi">
    <div class="kpi-label">Fecha</div>
    <div class="kpi-val" style="font-size:1rem;padding-top:4px">{fecha}</div>
  </div>
</div>

{cards_html}

</body>
</html>"""

    reporte_path.write_text(html, encoding="utf-8")
    print(f"[OK] Reporte HTML generado: {reporte_path}")
    return reporte_path
