import sys
if sys.stdout:
    sys.stdout.reconfigure(encoding="utf-8")

"""
dashboard_apuestas.py — Sprint 13
Dashboard Streamlit del Agente de Apuestas Deportivas.
Visualiza bankroll, ROI, historial y rendimiento por liga.

Uso:
  py -m streamlit run agente_apuestas\\dashboard_apuestas.py --server.port 8504
  (o doble clic en Iniciar_Dashboard.bat)
"""

import json
from pathlib import Path
from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

BASE_DIR       = Path(__file__).parent
HISTORICO_PATH = BASE_DIR / "backtesting" / "historico_apuestas.json"
BANKROLL_INI   = 100_000  # CLP

# ── Config página ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Agente Apuestas",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS mínimo ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
[data-testid="stMetric"] { background: #1F2937; border-radius: 8px; padding: 12px; }
</style>
""", unsafe_allow_html=True)


# ── Carga de datos ─────────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def cargar_datos() -> pd.DataFrame:
    if not HISTORICO_PATH.exists():
        return pd.DataFrame()
    with open(HISTORICO_PATH, encoding="utf-8") as f:
        data = json.load(f)
    if not data:
        return pd.DataFrame()
    df = pd.DataFrame(data)
    df["fecha_partido"]  = pd.to_datetime(df.get("fecha_partido"),  errors="coerce")
    df["fecha_registro"] = pd.to_datetime(df.get("fecha_registro"), errors="coerce")
    return df


def bankroll_actual(df: pd.DataFrame) -> float:
    resueltas = df[df["ganado"].notna()] if not df.empty else df
    return BANKROLL_INI + (resueltas["retorno"].sum() if not resueltas.empty else 0)


def roi_pct(df: pd.DataFrame) -> float:
    resueltas = df[df["ganado"].notna()] if not df.empty else df
    if resueltas.empty:
        return 0.0
    inv = resueltas["monto_apostado"].sum()
    return (resueltas["retorno"].sum() / inv * 100) if inv > 0 else 0.0


def win_rate(df: pd.DataFrame) -> float:
    resueltas = df[df["ganado"].notna()] if not df.empty else df
    if resueltas.empty:
        return 0.0
    return resueltas["ganado"].mean() * 100


def calcular_evolucion(df: pd.DataFrame) -> pd.DataFrame:
    resueltas = df[df["ganado"].notna()].sort_values("fecha_partido").copy()
    if resueltas.empty:
        return pd.DataFrame(columns=["fecha", "bankroll"])
    bankroll = BANKROLL_INI
    rows = [{"fecha": resueltas.iloc[0]["fecha_partido"], "bankroll": bankroll}]
    for _, row in resueltas.iterrows():
        bankroll += row.get("retorno", 0) or 0
        rows.append({"fecha": row["fecha_partido"], "bankroll": bankroll})
    return pd.DataFrame(rows)


# ── UI ─────────────────────────────────────────────────────────────────────────
st.title("⚽ Agente Apuestas — Dashboard")
st.caption(f"Actualizado: {datetime.now().strftime('%d/%m/%Y %H:%M')} · "
           f"Datos: {HISTORICO_PATH.name}")

df = cargar_datos()

if df.empty:
    st.info("📭 Sin datos en historico_apuestas.json todavía.")
    st.markdown(
        "El agente registrará apuestas cuando detecte value bets. "
        "Normalmente ocurre el primer fin de semana con partidos de Serie A."
    )
    if st.button("🔄 Refrescar"):
        st.cache_data.clear()
        st.rerun()
    st.stop()

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Filtros")
    ligas_disp = sorted(df["liga"].dropna().unique().tolist()) if "liga" in df.columns else []
    ligas_sel  = st.multiselect("Liga", ligas_disp, default=ligas_disp)
    solo_res   = st.checkbox("Solo resueltas", value=False)
    st.divider()
    if st.button("🔄 Refrescar datos"):
        st.cache_data.clear()
        st.rerun()
    st.caption(f"Bankroll inicial: ${BANKROLL_INI:,.0f} CLP")

# Filtrar
df_f = df[df["liga"].isin(ligas_sel)] if ligas_sel else df
if solo_res:
    df_f = df_f[df_f["ganado"].notna()]

resueltas = df_f[df_f["ganado"].notna()] if not df_f.empty else pd.DataFrame()

# ── KPIs ───────────────────────────────────────────────────────────────────────
bk       = bankroll_actual(df_f)
bk_delta = bk - BANKROLL_INI
roi      = roi_pct(df_f)
wr       = win_rate(df_f)
n_pend   = int(df_f["ganado"].isna().sum()) if not df_f.empty else 0
n_res    = len(resueltas)

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("💰 Bankroll",      f"${bk:,.0f}",  f"${bk_delta:+,.0f}")
c2.metric("📈 ROI",           f"{roi:+.1f}%")
c3.metric("🎯 Win Rate",      f"{wr:.1f}%")
c4.metric("✅ Resueltas",     str(n_res))
c5.metric("⏳ Pendientes",    str(n_pend))

st.divider()

# ── Gráfico bankroll + tabla ligas ────────────────────────────────────────────
col_g, col_t = st.columns([3, 2])

with col_g:
    st.subheader("📈 Evolución del bankroll")
    ev = calcular_evolucion(df_f)
    if not ev.empty:
        color_line = "#22C55E" if bk_delta >= 0 else "#EF4444"
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=ev["fecha"], y=ev["bankroll"],
            mode="lines+markers",
            line=dict(color=color_line, width=2),
            marker=dict(size=6),
            name="Bankroll",
        ))
        fig.add_hline(y=BANKROLL_INI, line_dash="dot", line_color="#6B7280",
                      annotation_text="Inicio", annotation_position="bottom right")
        fig.update_layout(
            paper_bgcolor="#0E1117", plot_bgcolor="#0E1117",
            font_color="#CBD5E1",
            xaxis=dict(showgrid=False, title=""),
            yaxis=dict(gridcolor="#1F2937", title="CLP"),
            height=300,
            margin=dict(l=0, r=0, t=10, b=0),
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Sin apuestas resueltas aún.")

with col_t:
    st.subheader("🏆 Por liga")
    if not resueltas.empty and "liga" in resueltas.columns:
        rows_liga = []
        for liga, grp in resueltas.groupby("liga"):
            inv  = grp["monto_apostado"].sum()
            ret  = grp["retorno"].sum()
            wr_  = grp["ganado"].mean() * 100
            rows_liga.append({
                "Liga":    liga,
                "n":       len(grp),
                "WR%":     round(wr_, 1),
                "ROI%":    round(ret / inv * 100 if inv > 0 else 0, 1),
                "Retorno": f"${ret:+,.0f}",
            })
        df_liga = pd.DataFrame(rows_liga).sort_values("ROI%", ascending=False)
        st.dataframe(df_liga, use_container_width=True, hide_index=True)
    else:
        st.info("Sin apuestas resueltas aún.")

st.divider()

# ── Historial completo ─────────────────────────────────────────────────────────
st.subheader("📋 Historial de apuestas")

cols_show = [c for c in ["fecha_partido", "liga", "home", "away", "seleccion",
                          "cuota", "value", "monto_apostado", "ganado", "retorno"]
             if c in df_f.columns]

df_show = df_f[cols_show].sort_values("fecha_partido", ascending=False).copy()

if "fecha_partido" in df_show.columns:
    df_show["fecha_partido"] = df_show["fecha_partido"].dt.strftime("%d/%m/%Y")
if "value" in df_show.columns:
    df_show["value"] = df_show["value"].apply(
        lambda x: f"{x*100:.1f}%" if pd.notna(x) else ""
    )
if "monto_apostado" in df_show.columns:
    df_show["monto_apostado"] = df_show["monto_apostado"].apply(
        lambda x: f"${x:,.0f}" if pd.notna(x) else ""
    )
if "ganado" in df_show.columns:
    df_show["ganado"] = df_show["ganado"].map(
        {True: "✅ Ganada", False: "❌ Perdida"}
    ).fillna("⏳ Pendiente")
if "retorno" in df_show.columns:
    df_show["retorno"] = df_show["retorno"].apply(
        lambda x: f"${x:+,.0f}" if pd.notna(x) else "–"
    )

st.dataframe(df_show, use_container_width=True, hide_index=True)
