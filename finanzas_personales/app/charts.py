import sys
sys.stdout.reconfigure(encoding="utf-8")

from typing import Dict, List
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

# ── Paleta Dark Premium Fintech ───────────────────────────────────────────────
COLOR_BRAND    = "#10B981"   # teal-green — ingresos, positivo, marca
COLOR_POSITIVO = "#34D399"   # emerald — deltas positivos
COLOR_NEGATIVO = "#F43F5E"   # rose — gastos, deudas, negativo
COLOR_ALERTA   = "#F59E0B"   # amber — advertencias, presupuesto límite
COLOR_INVERSION= "#EAB308"   # gold — AFP, inversiones, patrimonio
COLOR_SECUNDARIO="#6366F1"   # indigo — gráficos secundarios, selección
COLOR_AHORRO   = "#38BDF8"   # sky blue — ahorro, metas, liquidez
COLOR_MUTED    = "#64748B"   # slate — elementos secundarios

COLORES_GRUPOS = [
    "#10B981", "#6366F1", "#38BDF8", "#F59E0B",
    "#EAB308", "#F43F5E", "#94A3B8", "#34D399",
    "#818CF8", "#FCD34D", "#FB7185", "#67E8F9",
]

_BG_CARD  = "#1E293B"
_BG_BASE  = "#0F172A"
_GRID_CLR = "#293548"
_FONT_CLR = "#94A3B8"
_TITLE_CLR= "#CBD5E1"

_LAYOUT_BASE = dict(
    font=dict(family="Inter, Segoe UI, Arial, sans-serif", size=13, color=_FONT_CLR),
    paper_bgcolor="#1E293B",
    plot_bgcolor="#1E293B",
    margin=dict(l=20, r=20, t=48, b=20),
    colorway=COLORES_GRUPOS,
    separators=",.",
    legend=dict(
        bgcolor="rgba(0,0,0,0)",
        font=dict(color=_FONT_CLR, size=11),
        orientation="h",
        yanchor="bottom", y=1.02,
        xanchor="right", x=1,
    ),
    hoverlabel=dict(
        bgcolor="#0F172A",
        font=dict(family="Inter, Segoe UI, Arial", size=12, color="#E2E8F0"),
        bordercolor="#334155",
    ),
    xaxis=dict(
        gridcolor="#1a2535",
        tickfont=dict(color=_FONT_CLR, size=11),
        linecolor="#334155",
        zerolinecolor="#334155",
    ),
    yaxis=dict(
        gridcolor="#1a2535",
        tickfont=dict(color=_FONT_CLR, size=11),
        linecolor="#334155",
        zerolinecolor="#334155",
        tickformat=",.0f",
    ),
)


def fmt_clp(v: float) -> str:
    return f"${v:,.0f}".replace(",", ".")


def chart_barras_gastos_mes(df_mes: pd.DataFrame) -> go.Figure:
    """Barras horizontales top 10 grupos del mes."""
    if df_mes.empty:
        fig = go.Figure()
        fig.update_layout(title="Sin datos", **_LAYOUT_BASE)
        return fig
    top = (
        df_mes.groupby("grupo")["importe"]
        .sum()
        .sort_values(ascending=False)
        .head(10)
        .reset_index()
    )
    top = top.sort_values("importe", ascending=True)
    fig = go.Figure(
        go.Bar(
            x=top["importe"],
            y=top["grupo"],
            orientation="h",
            marker=dict(
                color=top["importe"],
                colorscale=[[0, "#6366F1"], [1, "#14b8a6"]],
                line=dict(width=0),
            ),
            text=[fmt_clp(v) for v in top["importe"]],
            textposition="outside",
            hovertemplate="%{y}: %{text}<extra></extra>",
        )
    )
    fig.update_layout(
        title=dict(text="Top 10 Grupos de Gasto", font=dict(color=_TITLE_CLR, size=14)),
        xaxis_title="",
        yaxis_title="",
        **_LAYOUT_BASE,
    )
    return fig


def chart_dona_tipos(por_tipo: dict) -> go.Figure:
    """Dona Fijo / Variable / Prescindible."""
    colores = {
        "Fijo":        COLOR_NEGATIVO,
        "Variable":    COLOR_ALERTA,
        "Prescindible":COLOR_MUTED,
    }
    labels = [k for k, v in por_tipo.items() if v > 0]
    values = [v for v in por_tipo.values() if v > 0]
    colors = [colores.get(l, COLOR_MUTED) for l in labels]
    if not labels:
        fig = go.Figure()
        fig.update_layout(title="Sin datos", **_LAYOUT_BASE)
        return fig
    fig = go.Figure(
        go.Pie(
            labels=labels,
            values=values,
            hole=0.45,
            marker_colors=colors,
            textinfo="label+percent",
            hovertemplate="%{label}: $%{value:,.0f}<extra></extra>",
        )
    )
    fig.update_layout(
        title="Distribución por Tipo",
        **_LAYOUT_BASE,
    )
    return fig


def chart_evolucion_mensual(df: pd.DataFrame) -> go.Figure:
    """Línea de gastos totales por mes."""
    if df.empty:
        fig = go.Figure()
        fig.update_layout(title="Sin datos", **_LAYOUT_BASE)
        return fig
    evol = df.groupby(["mes", "mes_nombre"])["importe"].sum().reset_index()
    evol = evol.sort_values("mes")
    fig = go.Figure(
        go.Scatter(
            x=evol["mes_nombre"],
            y=evol["importe"],
            mode="lines+markers+text",
            line=dict(color="#14b8a6", width=3),
            marker=dict(size=8),
            fill="tozeroy",
            fillcolor="rgba(20,184,166,0.08)",
            text=[fmt_clp(v) for v in evol["importe"]],
            textposition="top center",
            hovertemplate="%{x}: %{text}<extra></extra>",
        )
    )
    fig.update_layout(
        title="Evolución de Gastos Mensual",
        xaxis_title="",
        yaxis_title="CLP",
        **_LAYOUT_BASE,
    )
    return fig


def chart_50_30_20(regla_dict: dict) -> go.Figure:
    """Barras comparación real vs ideal (regla 50/30/20)."""
    categorias = ["Necesidades (50%)", "Deseos (30%)", "Ahorro/Deudas (20%)"]
    real = [
        regla_dict.get("necesidades", 0),
        regla_dict.get("deseos", 0),
        regla_dict.get("ahorro_deudas", 0),
    ]
    ideal = [
        regla_dict.get("ideal_necesidades", 0),
        regla_dict.get("ideal_deseos", 0),
        regla_dict.get("ideal_ahorro", 0),
    ]
    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Real",
        x=categorias,
        y=real,
        marker_color=COLOR_SECUNDARIO,
        text=[fmt_clp(v) for v in real],
        textposition="outside",
        hovertemplate="%{x}<br>Real: %{text}<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        name="Ideal",
        x=categorias,
        y=ideal,
        marker_color=COLOR_BRAND,
        opacity=0.7,
        text=[fmt_clp(v) for v in ideal],
        textposition="outside",
        hovertemplate="%{x}<br>Ideal: %{text}<extra></extra>",
    ))
    fig.update_layout(
        title="Regla 50/30/20",
        barmode="group",
        bargap=0.3,
        **_LAYOUT_BASE,
    )
    return fig


def chart_patrimonio_waterfall(activos: dict, pasivos: dict) -> go.Figure:
    """Waterfall: activos → pasivos → patrimonio neto."""
    names = []
    values = []
    measures = []
    colors = []
    for nombre, val in activos.items():
        if val and val > 0:
            names.append(nombre)
            values.append(val)
            measures.append("relative")
            colors.append(COLOR_BRAND)
    for nombre, val in pasivos.items():
        if val and val > 0:
            names.append(nombre)
            values.append(-val)
            measures.append("relative")
            colors.append(COLOR_NEGATIVO)
    names.append("Patrimonio Neto")
    values.append(0)
    measures.append("total")
    colors.append(COLOR_INVERSION)
    fig = go.Figure(
        go.Waterfall(
            name="Patrimonio",
            orientation="v",
            measure=measures,
            x=names,
            y=values,
            connector=dict(line=dict(color=_GRID_CLR, width=1)),
            decreasing=dict(marker_color=COLOR_NEGATIVO),
            increasing=dict(marker_color=COLOR_BRAND),
            totals=dict(marker_color=COLOR_INVERSION),
            text=[fmt_clp(abs(v)) if v != 0 else "" for v in values],
            textposition="outside",
        )
    )
    fig.update_layout(
        title="Waterfall Patrimonio Neto",
        **_LAYOUT_BASE,
    )
    return fig


def chart_afp_proyeccion(saldos_listas: List[List[float]], anos_lista: List[int], etiquetas: List[str]) -> go.Figure:
    """Área con 3 escenarios de proyección AFP."""
    colores_esc = [COLOR_NEGATIVO, COLOR_SECUNDARIO, COLOR_BRAND]
    fig = go.Figure()
    for i, (saldos, etiqueta) in enumerate(zip(saldos_listas, etiquetas)):
        anos = list(range(len(saldos)))
        fig.add_trace(go.Scatter(
            x=anos,
            y=saldos,
            mode="lines",
            name=etiqueta,
            line=dict(color=colores_esc[i % len(colores_esc)], width=2.5),
            fill="tozeroy" if i == 0 else "tonexty",
            fillcolor=f"rgba({','.join(str(int(c*255)) for c in px.colors.hex_to_rgb(colores_esc[i % len(colores_esc)].lstrip('#'))[:3])}, 0.1)",
            hovertemplate=f"{etiqueta} - Año %{{x}}: %{{y:,.0f}}<extra></extra>",
        ))
    fig.update_layout(
        title="Proyección AFP — 3 Escenarios",
        xaxis_title="Años desde hoy",
        yaxis_title="Saldo CLP",
        **_LAYOUT_BASE,
    )
    return fig


def chart_ingresos_vs_gastos(
    ingresos_lista: List[float],
    gastos_lista: List[float],
    meses_lista: List[str],
) -> go.Figure:
    """Barras agrupadas ingresos vs gastos por mes."""
    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Ingresos",
        x=meses_lista,
        y=ingresos_lista,
        marker_color="#14b8a6",
        text=[fmt_clp(v) for v in ingresos_lista],
        textposition="outside",
    ))
    fig.add_trace(go.Bar(
        name="Gastos",
        x=meses_lista,
        y=gastos_lista,
        marker_color="#F43F5E",
        text=[fmt_clp(v) for v in gastos_lista],
        textposition="outside",
    ))
    fig.update_layout(
        title="Ingresos vs Gastos por Mes",
        barmode="group",
        bargap=0.25,
        **_LAYOUT_BASE,
    )
    return fig


def chart_barras_apiladas_grupos(df: pd.DataFrame) -> go.Figure:
    """Barras apiladas por grupo × mes."""
    if df.empty:
        fig = go.Figure()
        fig.update_layout(title="Sin datos", **_LAYOUT_BASE)
        return fig
    pivot = df.pivot_table(
        index="mes_nombre", columns="grupo", values="importe", aggfunc="sum", fill_value=0
    )
    orden_meses = ["Enero","Febrero","Marzo","Abril","Mayo","Junio",
                   "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]
    pivot = pivot.reindex([m for m in orden_meses if m in pivot.index])
    fig = go.Figure()
    for i, grupo in enumerate(pivot.columns):
        fig.add_trace(go.Bar(
            name=grupo,
            x=pivot.index,
            y=pivot[grupo],
            marker_color=COLORES_GRUPOS[i % len(COLORES_GRUPOS)],
            hovertemplate=f"{grupo}<br>%{{x}}: $%{{y:,.0f}}<extra></extra>",
        ))
    fig.update_layout(
        title="Gastos por Grupo y Mes",
        barmode="stack",
        bargap=0.2,
        **_LAYOUT_BASE,
    )
    return fig
