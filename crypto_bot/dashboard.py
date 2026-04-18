import sys
sys.stdout.reconfigure(encoding="utf-8")

from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
import time
import os
import requests
from datetime import datetime, timezone

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

BASE_DIR       = Path(__file__).parent
ESTADO_PATH    = BASE_DIR / "estado_grid.json"
HISTORICO_PATH = BASE_DIR / "data" / "historico_operaciones.json"
BACKTEST_PATH  = BASE_DIR / "data" / "backtest_results.json"
PAR            = "BTC_USDT"

st.set_page_config(
    page_title="Crypto Bot — Grid Trading",
    page_icon="📈",
    layout="wide",
)

REFRESH_SEC = 30


# ── fuente de datos (Supabase en cloud, JSON local en dev) ────────────────────

def _supabase_client():
    url = os.getenv("SUPABASE_URL") or st.secrets.get("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_KEY") or st.secrets.get("SUPABASE_KEY", "")
    if not url or not key:
        return None
    try:
        from supabase import create_client
        return create_client(url, key)
    except Exception:
        return None


@st.cache_data(ttl=REFRESH_SEC)
def get_btc_price() -> float:
    try:
        resp = requests.get(
            "https://api.crypto.com/exchange/v1/public/get-tickers",
            params={"instrument_name": "BTC_USDT"},
            timeout=10,
        )
        data = resp.json()
        return float(data["result"]["data"][0].get("last") or 0)
    except Exception:
        return 0.0


@st.cache_data(ttl=REFRESH_SEC)
def load_estado() -> dict:
    client = _supabase_client()
    if client:
        try:
            resp = client.table("crypto_grid_state").select("estado").eq("par", PAR).single().execute()
            if resp.data:
                return resp.data["estado"]
        except Exception:
            pass
    # fallback local
    if ESTADO_PATH.exists():
        with open(ESTADO_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {}


@st.cache_data(ttl=REFRESH_SEC)
def load_historico() -> list[dict]:
    client = _supabase_client()
    if client:
        try:
            resp = (
                client.table("crypto_operaciones")
                .select("tipo, precio, qty, pnl, order_id, timestamp")
                .eq("par", PAR)
                .order("timestamp", desc=False)
                .limit(500)
                .execute()
            )
            return resp.data or []
        except Exception:
            pass
    # fallback local
    if HISTORICO_PATH.exists():
        with open(HISTORICO_PATH, encoding="utf-8") as f:
            return json.load(f)
    return []


@st.cache_data(ttl=3600)
def load_backtest() -> dict:
    if not BACKTEST_PATH.exists():
        return {}
    with open(BACKTEST_PATH, encoding="utf-8") as f:
        return json.load(f)


# ── layout ───────────────────────────────────────────────────────────────────

st.title("📈 Crypto Bot — Grid Trading BTC/USDT")
st.caption(f"Modo: **PAPER TRADING** | Auto-refresh cada {REFRESH_SEC}s")

estado   = load_estado()
historico = load_historico()
precio_live = get_btc_price() or estado.get("precio_ultimo", 0)

if not estado:
    st.warning("estado_grid.json no encontrado. ¿El bot ha corrido alguna vez?")
    st.stop()

niveles   = estado.get("niveles", [])
pnl_total = estado.get("pnl_realizado_usdt", 0)
capital   = estado.get("capital_usdt", 1000)
grid_lower = estado.get("grid_lower", 0)
grid_upper = estado.get("grid_upper", 0)
open_niveles = [n for n in niveles if n["estado"] != "idle"]
ultima_act = estado.get("ultima_actualizacion", "")

# ── métricas principales ──────────────────────────────────────────────────────

col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.metric("BTC Precio", f"${precio_live:,.0f}")

with col2:
    delta_color = "normal"
    st.metric("PnL Realizado", f"{pnl_total:+.4f} USDT",
              delta=f"{(pnl_total/capital)*100:+.2f}% ROI")

with col3:
    total_sells = sum(1 for t in historico if t["tipo"] == "SELL")
    total_buys  = sum(1 for t in historico if t["tipo"] == "BUY")
    st.metric("Trades", f"{len(historico)}", delta=f"B:{total_buys} / S:{total_sells}")

with col4:
    st.metric("Niveles Abiertos", f"{len(open_niveles)} / {estado.get('grid_levels', 0)}")

with col5:
    dentro = grid_lower <= precio_live <= grid_upper
    st.metric("Rango Grid", f"${grid_lower//1000}K–${grid_upper//1000}K",
              delta="✅ Dentro" if dentro else "⚠️ FUERA DEL GRID",
              delta_color="normal" if dentro else "inverse")

st.divider()

# ── gráfico precio vs grid ────────────────────────────────────────────────────

col_chart, col_tabla = st.columns([3, 2])

with col_chart:
    st.subheader("Precio vs Niveles Grid")

    precios_nivel = [n["precio"] for n in niveles]
    estados_nivel = [n["estado"] for n in niveles]
    colores_nivel = ["#ef4444" if e == "buy_open" else "#e2e8f0" for e in estados_nivel]

    fig = go.Figure()

    # Líneas horizontales de cada nivel
    for precio, estado_n, color in zip(precios_nivel, estados_nivel, colores_nivel):
        fig.add_hline(
            y=precio,
            line_color=color,
            line_width=1.5 if estado_n == "buy_open" else 0.8,
            line_dash="solid" if estado_n == "buy_open" else "dot",
            annotation_text=f"${precio:,.0f}" if estado_n == "buy_open" else "",
            annotation_position="right",
        )

    # Banda del grid
    fig.add_hrect(y0=grid_lower, y1=grid_upper, fillcolor="rgba(59,130,246,0.05)",
                  line_width=0)

    # Precio actual
    fig.add_hline(y=precio_live, line_color="#22c55e", line_width=2,
                  annotation_text=f"  BTC ${precio_live:,.0f}", annotation_position="right")

    fig.update_layout(
        height=420,
        margin=dict(l=10, r=120, t=20, b=20),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        yaxis=dict(
            range=[grid_lower * 0.97, grid_upper * 1.03],
            gridcolor="rgba(255,255,255,0.05)",
            tickformat="$,.0f",
        ),
        xaxis=dict(visible=False),
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)

    if ultima_act:
        try:
            dt = datetime.fromisoformat(ultima_act)
            st.caption(f"Última actualización bot: {dt.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        except Exception:
            pass

# ── tabla niveles abiertos ────────────────────────────────────────────────────

with col_tabla:
    st.subheader("Posiciones Abiertas")
    if open_niveles:
        rows = []
        for n in sorted(open_niveles, key=lambda x: x["precio"], reverse=True):
            pnl_no_realizado = (precio_live - n["precio"]) * n["btc_qty"]
            rows.append({
                "Precio entrada": f"${n['precio']:,.0f}",
                "BTC qty": f"{n['btc_qty']:.8f}",
                "PnL no real.": f"{pnl_no_realizado:+.4f} USDT",
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        total_unrealized = sum(
            (precio_live - n["precio"]) * n["btc_qty"] for n in open_niveles
        )
        st.metric("PnL no realizado total", f"{total_unrealized:+.4f} USDT")
    else:
        st.info("Sin posiciones abiertas")

    st.divider()
    st.subheader("Config Grid")
    cfg_rows = [
        {"Parámetro": "Par",      "Valor": estado.get("par", "—")},
        {"Parámetro": "Capital",  "Valor": f"${capital:,.0f} USDT"},
        {"Parámetro": "Niveles",  "Valor": estado.get("grid_levels", "—")},
        {"Parámetro": "Step",     "Valor": f"${estado.get('nivel_step', 0):,.0f}"},
        {"Parámetro": "Cap/nivel","Valor": f"${estado.get('capital_por_nivel', 0):.2f}"},
    ]
    st.dataframe(pd.DataFrame(cfg_rows), use_container_width=True, hide_index=True)

st.divider()

# ── historial de operaciones ──────────────────────────────────────────────────

st.subheader("Historial de Operaciones")

if historico:
    df = pd.DataFrame(historico)
    df["timestamp"] = pd.to_datetime(df["timestamp"]).dt.strftime("%Y-%m-%d %H:%M:%S")
    df["precio"] = df["precio"].apply(lambda x: f"${x:,.0f}")
    df["qty"]    = df["qty"].apply(lambda x: f"{x:.8f}")
    df["pnl"]    = df.get("pnl", pd.Series([None]*len(df))).apply(
        lambda x: f"{x:+.4f} USDT" if pd.notna(x) else "—"
    )
    df = df.rename(columns={
        "tipo": "Tipo", "precio": "Precio", "qty": "BTC Qty",
        "pnl": "PnL", "timestamp": "Fecha UTC",
    })
    cols_mostrar = ["Fecha UTC", "Tipo", "Precio", "BTC Qty", "PnL"]
    st.dataframe(
        df[[c for c in cols_mostrar if c in df.columns]].iloc[::-1].reset_index(drop=True),
        use_container_width=True, hide_index=True,
    )
else:
    st.info("Sin operaciones registradas aún.")

# ── backtesting results ───────────────────────────────────────────────────────

bt = load_backtest()
if bt:
    st.divider()
    st.subheader("Backtesting — Comparativa de Configuraciones")

    col_b1, col_b2 = st.columns([1, 2])
    with col_b1:
        mejor = bt.get("mejor_config", {})
        actual_bt = bt.get("config_actual", {})
        st.metric("Mejor config (backtest)",
                  f"${mejor.get('grid_lower',0)//1000}K–${mejor.get('grid_upper',0)//1000}K / {mejor.get('grid_levels')} niveles",
                  delta=f"{mejor.get('roi_pct',0):+.2f}% ROI")
        st.metric("Config actual (backtest)",
                  f"${actual_bt.get('grid_lower',0)//1000}K–${actual_bt.get('grid_upper',0)//1000}K / {actual_bt.get('grid_levels')} niveles",
                  delta=f"{actual_bt.get('roi_pct',0):+.2f}% ROI")
        periodo = bt.get("periodo_inicio", "")[:10]
        st.caption(f"Periodo: {periodo} → {bt.get('periodo_fin','')[:10]}")

    with col_b2:
        resultados = bt.get("resultados_ordenados_roi", [])
        if resultados:
            df_bt = pd.DataFrame(resultados)
            df_bt["Rango"] = df_bt.apply(
                lambda r: f"${r['grid_lower']//1000}K–${r['grid_upper']//1000}K", axis=1)
            df_bt = df_bt.rename(columns={
                "grid_levels": "Niveles", "step": "Step",
                "pnl_usdt": "PnL USDT", "roi_pct": "ROI %",
                "total_trades": "Trades", "fees_usdt": "Fees USDT",
            })
            cols_bt = ["Rango", "Niveles", "Step", "PnL USDT", "ROI %", "Trades", "Fees USDT"]
            st.dataframe(
                df_bt[[c for c in cols_bt if c in df_bt.columns]],
                use_container_width=True, hide_index=True,
            )

# ── auto-refresh ──────────────────────────────────────────────────────────────

time.sleep(0.1)
st.caption(f"⟳ Dashboard se refresca automáticamente cada {REFRESH_SEC}s")
st_autorefresh = st.empty()
with st_autorefresh:
    st.markdown(
        f"<meta http-equiv='refresh' content='{REFRESH_SEC}'>",
        unsafe_allow_html=True,
    )
