"""
charts.py — Gráficas Plotly reutilizables para el dashboard
"""
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd

TEAL    = "#14b8a6"
BG      = "#0c1422"
BG_CARD = "#0f1e30"
GRID    = "#1e3a5f"

_LAYOUT = dict(
    paper_bgcolor=BG, plot_bgcolor=BG_CARD,
    font=dict(color="#e2e8f0", size=12),
    margin=dict(l=40, r=20, t=40, b=40),
    xaxis=dict(gridcolor=GRID, zerolinecolor=GRID),
    yaxis=dict(gridcolor=GRID, zerolinecolor=GRID),
)


def grafico_distribucion_imc(df: pd.DataFrame) -> go.Figure:
    cats  = ["Bajo peso", "Normal", "Sobrepeso", "Obesidad I", "Obesidad II", "Obesidad III"]
    conta = df["Categoría IMC"].value_counts().reindex(cats, fill_value=0)
    colores = ["#38bdf8", "#22c55e", "#f59e0b", "#f97316", "#ef4444", "#7f1d1d"]

    fig = go.Figure(go.Bar(
        x=conta.index, y=conta.values,
        marker_color=colores[:len(conta)],
        text=conta.values, textposition="outside",
    ))
    fig.update_layout(**_LAYOUT, title="Distribución IMC", xaxis_title="Categoría", yaxis_title="Pacientes")
    return fig


def grafico_score_riesgo(df: pd.DataFrame) -> go.Figure:
    orden  = ["Bajo", "Moderado", "Alto", "Muy alto"]
    conta  = df["Nivel Riesgo"].value_counts().reindex(orden, fill_value=0)
    colores = ["#22c55e", "#f59e0b", "#ef4444", "#7f1d1d"]

    fig = go.Figure(go.Pie(
        labels=conta.index, values=conta.values,
        marker_colors=colores, hole=0.45,
        textinfo="label+percent",
    ))
    fig.update_layout(**_LAYOUT, title="Distribución Riesgo Metabólico",
                      paper_bgcolor=BG, plot_bgcolor=BG)
    return fig


def grafico_scatter_imc_glucosa(df: pd.DataFrame) -> go.Figure:
    COLORES_RIESGO = {"Bajo": "#22c55e", "Moderado": "#f59e0b", "Alto": "#ef4444", "Muy alto": "#7f1d1d"}
    fig = px.scatter(
        df, x="IMC", y="Glucosa", color="Nivel Riesgo",
        color_discrete_map=COLORES_RIESGO,
        hover_data=["Nombre", "Edad", "Sexo"],
        title="IMC vs Glucosa por Nivel de Riesgo",
    )
    fig.update_layout(**_LAYOUT)
    return fig


def grafico_radar_paciente(labels: list, valores: list, nombre: str) -> go.Figure:
    """Radar chart con indicadores metabólicos normalizados (0-1)."""
    fig = go.Figure(go.Scatterpolar(
        r=valores + [valores[0]],
        theta=labels + [labels[0]],
        fill="toself",
        line_color=TEAL,
        fillcolor="rgba(20,184,166,0.15)",
    ))
    fig.update_layout(
        **_LAYOUT,
        polar=dict(
            bgcolor=BG_CARD,
            radialaxis=dict(visible=True, range=[0, 1], gridcolor=GRID),
            angularaxis=dict(gridcolor=GRID),
        ),
        title=f"Perfil metabólico — {nombre}",
    )
    return fig


def grafico_evolucion_peso(fechas: list, pesos: list, nombre: str) -> go.Figure:
    fig = go.Figure(go.Scatter(
        x=fechas, y=pesos, mode="lines+markers",
        line=dict(color=TEAL, width=2),
        marker=dict(color=TEAL, size=8),
        name="Peso (kg)",
    ))
    fig.update_layout(**_LAYOUT, title=f"Evolución de peso — {nombre}",
                      xaxis_title="Fecha", yaxis_title="kg")
    return fig
