import sys
sys.stdout.reconfigure(encoding="utf-8")

"""
ai_insights.py — Integración del Agente Financiero finanzas.py v2.0 con la app.

Toma datos reales del usuario (liquidaciones, Excel, saldos) y genera
análisis narrativos inteligentes usando Claude API + memoria evolutiva.

Roles usados:
  tesoreria  → saldo, flujo de caja, proyección liquidez
  fpa        → presupuesto vs real, varianza por grupo, forecast
  cartera    → ahorro, inversiones, asignación patrimonio
  consulta   → preguntas libres del usuario sobre su situación
"""

import os
import sys
from pathlib import Path
from datetime import datetime

import streamlit as st
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent.parent / ".env")

# ── Path al agente financiero ─────────────────────────────────────────────────
_AI_AGENT_DIR = Path(__file__).parent.parent.parent / "AI_Agent"
if str(_AI_AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(_AI_AGENT_DIR))

_agente_disponible = False
try:
    from agentes.finanzas import _claude, _mem, SYSTEM_ROLES
    _agente_disponible = True
except Exception as _err:
    print(f"[ai_insights] Agente no disponible: {_err}", file=sys.stderr)


# ── System prompt base para finanzas personales ───────────────────────────────
_SYSTEM_PERSONAL = """Eres un Asesor de Finanzas Personales Senior especializado en el mercado chileno.
Tu misión: analizar la situación financiera real del usuario con sus datos concretos,
entregar insights accionables, lenguaje técnico pero comprensible para cualquier audiencia.

Principios:
- Usa los datos exactos que te pasan — nunca inventes cifras.
- Personaliza: "tus gastos", "tu saldo", "tu situación" — no genérico.
- Cada análisis termina con 2-3 recomendaciones concretas y priorizadas.
- Usa el contexto del mercado chileno: UF, AFP, ISAPRE, CMF, BCI, BancoEstado, etc.
- Formato: párrafos cortos, sin bullets excesivos, lenguaje directo.
- Máximo 350 palabras salvo que se indique otro límite.
- Responde en español.
"""

_CONTEXTO_CHILE = """
Contexto mercado Chile (referencia):
- TPM Banco Central: 5.0% | UF: ~$39.841 | USD/CLP: ~$913
- AFP promedio rentabilidad real: 3-7% anual según fondo (A=mayor riesgo, E=menor)
- Regla general: deuda total no debe superar 35% del ingreso mensual
- Tasa de ahorro saludable: ≥15% del ingreso mensual neto
- Regla 50/30/20: 50% necesidades, 30% deseos, 20% ahorro+deudas
"""


# ── Helpers ───────────────────────────────────────────────────────────────────

def _fmt(n: float) -> str:
    """Formatea número como CLP: 1.234.567"""
    try:
        return f"${int(n):,}".replace(",", ".")
    except Exception:
        return str(n)


def _pct(n: float, total: float) -> str:
    if total <= 0:
        return "0%"
    return f"{n / total * 100:.1f}%"


def _claude_personal(prompt_usuario: str, nivel: str = "senior") -> str:
    """Llama al agente con el system prompt de finanzas personales."""
    if not _agente_disponible:
        return "_Agente no disponible. Verifica ANTHROPIC_API_KEY en .env_"
    try:
        return _claude(
            system=_SYSTEM_PERSONAL + _CONTEXTO_CHILE,
            user=prompt_usuario,
            nivel=nivel,
        )
    except Exception as e:
        return f"_Error al consultar el agente: {e}_"


# ══════════════════════════════════════════════════════════════════════════════
#  ANÁLISIS POR MÓDULO
# ══════════════════════════════════════════════════════════════════════════════

def analizar_resumen_mes(
    mes_nombre: str,
    ingresos: float,
    gastos: float,
    saldo_inicial: float,
    saldo_actual: float,
    por_grupo: dict,
    tasa_ahorro: float,
    indicadores: dict | None = None,
) -> str:
    """
    Análisis ejecutivo del mes: qué pasó, cómo comparar, qué hacer.
    Úsalo en el Dashboard como "Resumen inteligente del mes".
    """
    top_grupos = sorted(por_grupo.items(), key=lambda x: x[1], reverse=True)[:5]
    top_str = " | ".join(f"{g}: {_fmt(v)}" for g, v in top_grupos)

    uf = indicadores.get("uf", 39841) if indicadores else 39841
    dolar = indicadores.get("dolar", 913) if indicadores else 913

    prompt = f"""
Analiza el resumen financiero de {mes_nombre}:

INGRESOS: {_fmt(ingresos)}
GASTOS TOTALES: {_fmt(gastos)} ({_pct(gastos, ingresos)} de los ingresos)
SALDO INICIAL: {_fmt(saldo_inicial)}
SALDO ACTUAL: {_fmt(saldo_actual)}
VARIACIÓN SALDO: {_fmt(saldo_actual - saldo_inicial)} ({'+' if saldo_actual >= saldo_inicial else ''}{_pct(abs(saldo_actual - saldo_inicial), saldo_inicial)})
TASA DE AHORRO: {tasa_ahorro:.1f}%
TOP GASTOS: {top_str}
UF del mes: {uf} | USD/CLP: {dolar}

Entrega:
1) Diagnóstico del mes en 2 frases (positivo o preocupante, con datos concretos)
2) El gasto más relevante y si está dentro de parámetros sanos
3) 2 acciones concretas para mejorar o mantener el resultado
Máximo 200 palabras.
"""
    return _claude_personal(prompt)


def analizar_historial_ingresos(liquidaciones: list) -> str:
    """
    Analiza el historial de liquidaciones: evolución sueldo, descuentos, tendencias.
    Úsalo en la página "Mis Ingresos".
    """
    if not liquidaciones:
        return "_Sin historial de liquidaciones disponible._"

    # Construir tabla resumen
    lineas = ["Período | Sueldo Base | Bono | Líquido | AFP | Salud | Impuesto"]
    for l in liquidaciones[-12:]:  # últimos 12 meses
        lineas.append(
            f"{l.get('periodo','?')} | "
            f"{_fmt(l.get('sueldo_base') or 0)} | "
            f"{_fmt(l.get('bono') or 0)} | "
            f"{_fmt(l.get('liquido') or 0)} | "
            f"{_fmt(l.get('afp') or 0)} | "
            f"{_fmt(l.get('salud') or 0)} | "
            f"{_fmt(l.get('impuesto') or 0)}"
        )

    ultimo = liquidaciones[-1]
    anterior = liquidaciones[-2] if len(liquidaciones) >= 2 else None
    var_liquido = ""
    if anterior and ultimo.get("liquido") and anterior.get("liquido"):
        delta = (ultimo["liquido"] - anterior["liquido"]) / anterior["liquido"] * 100
        var_liquido = f"Variación líquido vs mes anterior: {delta:+.1f}%"

    prompt = f"""
Analiza el historial de remuneraciones con los datos reales:

{chr(10).join(lineas)}

{var_liquido}

Entrega:
1) Tendencia del sueldo base y bonos en el período (crecimiento, estabilidad, caídas)
2) Análisis de descuentos legales: AFP, salud e impuesto — ¿son proporcionales al ingreso? ¿hay oportunidades de optimización?
3) Comparación del líquido real vs el ingreso bruto total: ¿qué % se queda en descuentos?
4) 2 recomendaciones específicas (ej: cambio AFP, negociación sueldo, optimización tributaria)
Máximo 280 palabras.
"""
    return _claude_personal(prompt)


def analizar_presupuesto_vs_real(
    mes_nombre: str,
    ingresos: float,
    por_tipo: dict,
    por_grupo: dict,
    regla_5030_20: dict,
) -> str:
    """
    Análisis FP&A personal: varianza por categoría, adherencia a regla 50/30/20.
    Úsalo en "Mes Detalle".
    """
    necesidades = regla_5030_20.get("necesidades", 0)
    deseos = regla_5030_20.get("deseos", 0)
    ahorro_deudas = regla_5030_20.get("ahorro_deudas", 0)
    ideal_nec = regla_5030_20.get("ideal_necesidades", ingresos * 0.5)
    ideal_des = regla_5030_20.get("ideal_deseos", ingresos * 0.3)

    top_grupos = sorted(por_grupo.items(), key=lambda x: x[1], reverse=True)[:6]
    grupos_str = "\n".join(f"  {g}: {_fmt(v)} ({_pct(v, ingresos)} ingresos)" for g, v in top_grupos)

    prompt = f"""
Análisis FP&A personal — {mes_nombre}:

INGRESOS: {_fmt(ingresos)}

REGLA 50/30/20:
  Necesidades: {_fmt(necesidades)} (ideal {_fmt(ideal_nec)}, real {_pct(necesidades, ingresos)})
  Deseos: {_fmt(deseos)} (ideal {_fmt(ideal_des)}, real {_pct(deseos, ingresos)})
  Ahorro+Deudas: {_fmt(ahorro_deudas)} ({_pct(ahorro_deudas, ingresos)})

TOP GASTOS POR GRUPO:
{grupos_str}

Entrega:
1) ¿Está la distribución dentro de parámetros sanos? Identifica la desviación más importante.
2) El grupo de gasto más preocupante y por qué.
3) Oportunidades concretas de optimización sin afectar calidad de vida.
Máximo 220 palabras.
"""
    return _claude_personal(prompt)


def analizar_patrimonio(
    activos: dict,
    pasivos: dict,
    neto: float,
    ratio_endeudamiento: float,
    ingresos_mensuales: float,
    indicadores: dict | None = None,
) -> str:
    """
    Análisis del estado patrimonial: solidez, liquidez, riesgo de concentración.
    Úsalo en "Patrimonio Neto".
    """
    uf = indicadores.get("uf", 39841) if indicadores else 39841
    neto_uf = neto / uf if uf > 0 else 0
    activos_str = "\n".join(f"  {k}: {_fmt(v)}" for k, v in activos.items() if v > 0)
    pasivos_str = "\n".join(f"  {k}: {_fmt(v)}" for k, v in pasivos.items() if v > 0) or "  Sin pasivos registrados"

    meses_cubrir = (activos.get("Cta. Corriente/Vista", 0) + activos.get("Cta. Ahorro", 0)) / ingresos_mensuales if ingresos_mensuales > 0 else 0

    prompt = f"""
Análisis patrimonial:

ACTIVOS:
{activos_str}
TOTAL ACTIVOS: {_fmt(sum(v for v in activos.values() if v > 0))}

PASIVOS:
{pasivos_str}
TOTAL PASIVOS: {_fmt(sum(v for v in pasivos.values() if v > 0))}

PATRIMONIO NETO: {_fmt(neto)} ({neto_uf:.1f} UF)
RATIO ENDEUDAMIENTO: {ratio_endeudamiento:.1f}%
FONDO EMERGENCIA: {meses_cubrir:.1f} meses de ingresos en activos líquidos
INGRESOS MENSUALES: {_fmt(ingresos_mensuales)}
UF actual: {uf}

Entrega:
1) Diagnóstico de la solidez patrimonial (concentración, liquidez, endeudamiento)
2) ¿Es adecuado el fondo de emergencia? (recomendación estándar: 3-6 meses)
3) Principal riesgo patrimonial y cómo mitigarlo
4) Próximo hito de construcción patrimonial recomendado
Máximo 280 palabras.
"""
    return _claude_personal(prompt)


def analizar_afp(
    saldo_actual: float,
    aporte_mensual: float,
    edad_aprox: int,
    años_proyeccion: int,
    saldo_pesimista: float,
    saldo_base: float,
    saldo_optimista: float,
    indicadores: dict | None = None,
) -> str:
    """
    Análisis de la situación previsional: proyección, comisiones, estrategia.
    Úsalo en "AFP y Previsión".
    """
    uf = indicadores.get("uf", 39841) if indicadores else 39841
    saldo_uf = saldo_actual / uf

    prompt = f"""
Análisis previsional AFP:

SALDO ACTUAL: {_fmt(saldo_actual)} ({saldo_uf:.1f} UF)
APORTE MENSUAL NETO: {_fmt(aporte_mensual)}
AÑOS DE PROYECCIÓN: {años_proyeccion}
AFP ACTUAL: ProVida (comisión 1.45% — una de las más altas del mercado)

PROYECCIONES A {años_proyeccion} AÑOS:
  Pesimista (4% real): {_fmt(saldo_pesimista)}
  Base (6% real): {_fmt(saldo_base)}
  Optimista (8% real): {_fmt(saldo_optimista)}

Alternativas de menor comisión: Modelo (0.58%) | Uno AFP (0.49%)
UF actual: {uf}

Entrega:
1) ¿Es suficiente la proyección para una pensión digna? (referencia: pensión mínima ~$250.000 CLP 2026)
2) Impacto concreto de cambiar a una AFP de menor comisión (cálculo estimado del ahorro en {años_proyeccion} años)
3) 2 estrategias para acelerar el crecimiento previsional (APV, cambio de fondo, etc.)
Máximo 250 palabras.
"""
    return _claude_personal(prompt)


def consulta_libre(pregunta: str, contexto_usuario: dict | None = None) -> str:
    """
    Responde preguntas libres del usuario sobre su situación financiera.
    El contexto_usuario puede incluir saldos, ingresos, etc. (opcional).
    """
    ctx = ""
    if contexto_usuario:
        ctx = "\nContexto del usuario:\n" + "\n".join(
            f"  {k}: {v}" for k, v in contexto_usuario.items() if v
        ) + "\n\n"

    prompt = f"{ctx}Pregunta del usuario: {pregunta}\n\nResponde con precisión técnica y lenguaje accesible. Máximo 300 palabras."
    return _claude_personal(prompt)


# ══════════════════════════════════════════════════════════════════════════════
#  WIDGETS STREAMLIT
# ══════════════════════════════════════════════════════════════════════════════

def render_insight_card(titulo: str, contenido: str, tipo: str = "info"):
    """
    Renderiza un card de insight AI con estilo visual.
    tipo: "info" | "success" | "warning" | "error"
    """
    iconos = {"info": "🤖", "success": "✅", "warning": "⚠️", "error": "❌"}
    icono = iconos.get(tipo, "🤖")

    st.markdown(f"""
<div style="
    background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%);
    border-left: 4px solid {'#10B981' if tipo=='success' else '#6366F1' if tipo=='info' else '#F59E0B' if tipo=='warning' else '#F43F5E'};
    border-radius: 8px;
    padding: 16px 20px;
    margin: 12px 0;
    box-shadow: 0 2px 8px rgba(0,0,0,0.3);
">
<div style="color: #94A3B8; font-size: 0.75rem; font-weight: 600; letter-spacing: 0.05em; margin-bottom: 8px;">
    {icono} {titulo.upper()}
</div>
<div style="color: #E2E8F0; font-size: 0.875rem; line-height: 1.6;">
    {contenido.replace(chr(10), '<br>')}
</div>
</div>
""", unsafe_allow_html=True)


def render_insight_con_spinner(titulo: str, funcion, *args, cache_key: str = "", **kwargs) -> str:
    """
    Llama a una función de análisis AI con spinner de carga.
    Cachea el resultado en session_state para no re-llamar la API.

    Uso:
        resultado = render_insight_con_spinner(
            "Análisis del mes", analizar_resumen_mes, mes, ingresos, ...
        )
    """
    clave = f"ai_cache_{cache_key}" if cache_key else f"ai_cache_{titulo}_{id(funcion)}"

    if clave not in st.session_state:
        with st.spinner(f"🤖 Generando análisis: {titulo}..."):
            resultado = funcion(*args, **kwargs)
            st.session_state[clave] = resultado

    return st.session_state.get(clave, "")


def limpiar_cache_ai():
    """Limpia todos los análisis AI cacheados en session_state."""
    claves = [k for k in st.session_state if k.startswith("ai_cache_")]
    for k in claves:
        del st.session_state[k]


def agente_disponible() -> bool:
    """Retorna True si el agente está disponible y tiene API key."""
    return _agente_disponible and bool(os.getenv("ANTHROPIC_API_KEY"))
