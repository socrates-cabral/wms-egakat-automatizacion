import sys
sys.stdout.reconfigure(encoding="utf-8")

# charts.py — Gráficos Plotly reutilizables para Chiquito Finanzas
# Paleta consistente con la app HTML original

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

# ─── Colores (consistentes con ChiquitoFinanzas.html) ─────────────────────────
COLOR_VERDE  = '#3fb950'
COLOR_ROJO   = '#f85149'
COLOR_AMBAR  = '#d29922'
COLOR_AZUL   = '#58a6ff'
COLOR_FONDO  = '#0d1117'
COLOR_PANEL  = '#161b22'
COLOR_BORDE  = '#30363d'
COLOR_TEXTO  = '#e6edf3'
COLOR_TEXTO2 = '#8b949e'

_LAYOUT_BASE = dict(
    paper_bgcolor=COLOR_FONDO,
    plot_bgcolor=COLOR_PANEL,
    font=dict(color=COLOR_TEXTO, family='monospace'),
    margin=dict(l=20, r=20, t=40, b=20),
    legend=dict(bgcolor=COLOR_PANEL, bordercolor=COLOR_BORDE, borderwidth=1),
)


def chart_ingresos_gastos(df_resumen: pd.DataFrame) -> go.Figure:
    """
    Gráfico de barras agrupadas: Ingresos vs Gastos por mes.
    df_resumen: columnas [mes, ingresos, gastos]
    """
    fig = go.Figure()

    fig.add_trace(go.Bar(
        name='Ingresos',
        x=df_resumen['mes'],
        y=df_resumen['ingresos'],
        marker_color=COLOR_VERDE,
        text=[f'${v:,.0f}' for v in df_resumen['ingresos']],
        textposition='outside',
        textfont=dict(size=10),
    ))

    fig.add_trace(go.Bar(
        name='Gastos',
        x=df_resumen['mes'],
        y=df_resumen['gastos'],
        marker_color=COLOR_ROJO,
        text=[f'${v:,.0f}' for v in df_resumen['gastos']],
        textposition='outside',
        textfont=dict(size=10),
    ))

    fig.update_layout(
        **_LAYOUT_BASE,
        title='Ingresos vs Gastos por mes',
        barmode='group',
        xaxis=dict(gridcolor=COLOR_BORDE),
        yaxis=dict(gridcolor=COLOR_BORDE, tickprefix='$', tickformat=',.0f'),
        height=380,
    )
    return fig


def chart_resultado_mensual(df_resumen: pd.DataFrame) -> go.Figure:
    """
    Gráfico de línea con el resultado neto mensual (verde/rojo según signo).
    """
    colores = [COLOR_VERDE if r >= 0 else COLOR_ROJO for r in df_resumen['resultado']]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name='Resultado neto',
        x=df_resumen['mes'],
        y=df_resumen['resultado'],
        marker_color=colores,
        text=[f'${v:+,.0f}' for v in df_resumen['resultado']],
        textposition='outside',
        textfont=dict(size=10),
    ))
    fig.add_hline(y=0, line_color=COLOR_TEXTO2, line_dash='dash', line_width=1)

    fig.update_layout(
        **_LAYOUT_BASE,
        title='Resultado neto mensual',
        xaxis=dict(gridcolor=COLOR_BORDE),
        yaxis=dict(gridcolor=COLOR_BORDE, tickprefix='$', tickformat=',.0f'),
        height=320,
    )
    return fig


def chart_costos_dona(costos_fijos: dict, cuotas_bancarias: float = 0) -> go.Figure:
    """
    Gráfico de dona: composición de costos fijos + cuotas bancarias.
    """
    etiquetas = list(costos_fijos.keys())
    valores   = list(costos_fijos.values())

    if cuotas_bancarias > 0:
        etiquetas.append('Cuotas bancarias')
        valores.append(cuotas_bancarias)

    # Reemplazar claves técnicas con nombres legibles
    nombres_legibles = {
        'alquiler_taller':  'Alquiler taller',
        'telefono':         'Teléfono',
        'internet':         'Internet',
        'luz_agua':         'Luz + agua',
        'mercadopago':      'MercadoPago',
        'gasolina':         'Gasolina',
        'gastos_varios':    'Gastos varios',
        'Cuotas bancarias': 'Cuotas bancarias',
    }
    etiquetas = [nombres_legibles.get(e, e) for e in etiquetas]

    fig = go.Figure(go.Pie(
        labels=etiquetas,
        values=valores,
        hole=0.55,
        textinfo='percent+label',
        marker=dict(colors=[
            COLOR_AZUL, COLOR_AMBAR, COLOR_VERDE, COLOR_ROJO,
            '#a5d6ff', '#ffa657', '#7ee787', '#ff7b72',
        ]),
        textfont=dict(size=11),
    ))

    total = sum(valores)
    fig.add_annotation(
        text=f'${total:,.0f}',
        x=0.5, y=0.5, showarrow=False,
        font=dict(size=16, color=COLOR_TEXTO),
    )

    fig.update_layout(
        **_LAYOUT_BASE,
        title='Composición de costos fijos',
        height=350,
        showlegend=True,
    )
    return fig


def chart_amortizacion(tabla: list) -> go.Figure:
    """
    Gráfico de área apilada: evolución del saldo + desglose cuota/interés/principal.
    tabla: lista de dicts con {mes, cuota, interes, principal, saldo}
    """
    meses      = [f"M{r['mes']}" for r in tabla]
    intereses  = [r['interes']   for r in tabla]
    principales = [r['principal'] for r in tabla]
    saldos     = [r['saldo']     for r in tabla]

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    fig.add_trace(go.Bar(
        name='Interés',
        x=meses, y=intereses,
        marker_color=COLOR_ROJO,
    ), secondary_y=False)

    fig.add_trace(go.Bar(
        name='Principal',
        x=meses, y=principales,
        marker_color=COLOR_VERDE,
    ), secondary_y=False)

    fig.add_trace(go.Scatter(
        name='Saldo',
        x=meses, y=saldos,
        mode='lines+markers',
        line=dict(color=COLOR_AZUL, width=2),
        marker=dict(size=5),
    ), secondary_y=True)

    fig.update_layout(
        **_LAYOUT_BASE,
        title='Tabla de amortización BCI',
        barmode='stack',
        xaxis=dict(gridcolor=COLOR_BORDE),
        yaxis=dict(gridcolor=COLOR_BORDE, title='Cuota ($)', tickprefix='$', tickformat=',.0f'),
        yaxis2=dict(title='Saldo ($)', tickprefix='$', tickformat=',.0f'),
        height=380,
    )
    return fig


def chart_proyeccion_12m(proyeccion: list) -> go.Figure:
    """
    Proyección 12 meses: ventas, costos y resultado.
    proyeccion: lista de dicts con {mes, ventas, costo_total, resultado}
    """
    meses      = [f"M{r['mes']}" for r in proyeccion]
    ventas     = [r['ventas']     for r in proyeccion]
    costos     = [r['costo_total'] for r in proyeccion]
    resultado  = [r['resultado']  for r in proyeccion]
    colores_r  = [COLOR_VERDE if r >= 0 else COLOR_ROJO for r in resultado]

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.1,
                        subplot_titles=('Ventas vs Costos', 'Resultado mensual'))

    fig.add_trace(go.Scatter(
        name='Ventas', x=meses, y=ventas,
        mode='lines+markers', line=dict(color=COLOR_VERDE, width=2),
    ), row=1, col=1)

    fig.add_trace(go.Scatter(
        name='Costos', x=meses, y=costos,
        mode='lines+markers', line=dict(color=COLOR_ROJO, width=2),
    ), row=1, col=1)

    fig.add_trace(go.Bar(
        name='Resultado', x=meses, y=resultado,
        marker_color=colores_r, showlegend=False,
    ), row=2, col=1)

    fig.add_hline(y=0, line_color=COLOR_TEXTO2, line_dash='dash', row=2, col=1)

    fig.update_layout(
        **_LAYOUT_BASE,
        title='Proyección 12 meses',
        height=480,
    )
    fig.update_yaxes(tickprefix='$', tickformat=',.0f', gridcolor=COLOR_BORDE)
    return fig


def chart_deuda_barras(df_deuda: pd.DataFrame) -> go.Figure:
    """
    Barras horizontales ordenadas por saldo de deuda.
    df_deuda: columnas [acreedor, saldo, cuota, tasa, tipo]
    """
    df = df_deuda[df_deuda['saldo'] > 0].sort_values('saldo', ascending=True)
    if df.empty:
        fig = go.Figure()
        fig.update_layout(**_LAYOUT_BASE, title='Sin deudas activas')
        return fig

    col_acreedor = 'acreedor' if 'acreedor' in df.columns else df.columns[0]
    col_saldo    = 'saldo'    if 'saldo'    in df.columns else df.columns[1]

    fig = go.Figure(go.Bar(
        orientation='h',
        x=df[col_saldo],
        y=df[col_acreedor],
        marker_color=COLOR_ROJO,
        text=[f'${v:,.0f}' for v in df[col_saldo]],
        textposition='outside',
        textfont=dict(size=10),
    ))

    fig.update_layout(
        **_LAYOUT_BASE,
        title='Deuda por instrumento (mayor a menor)',
        xaxis=dict(gridcolor=COLOR_BORDE, tickprefix='$', tickformat=',.0f'),
        yaxis=dict(gridcolor=COLOR_BORDE),
        height=350,
    )
    return fig
