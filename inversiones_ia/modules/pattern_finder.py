"""
pattern_finder.py — Módulo 9: Buscador de patrones estadísticos estilo Renaissance Technologies.
"""

import streamlit as st
import pandas as pd
import numpy as np
from utils.market_data import MarketData
from utils.claude_client import ClaudeClient
from utils.history import save_analysis
from utils.pdf_exporter import export_analysis_to_pdf

PERIOD_MAP = {
    "2 años": "2y",
    "5 años": "5y",
    "10 años": "10y",
}


def _calculate_patterns(ticker: str, period: str, md: MarketData) -> str:
    """Calcula patrones estadísticos históricos."""
    import yfinance as yf
    lines = [f"=== PATRONES ESTADÍSTICOS DE {ticker.upper()} ({period}) ===\n"]

    hist = md.get_price_history(ticker, period=period)
    if hist.empty or len(hist) < 50:
        return f"Datos insuficientes para calcular patrones de {ticker}"

    hist = hist.copy()
    hist.index = pd.to_datetime(hist.index)
    hist["return"] = hist["Close"].pct_change() * 100

    # 1. Retorno promedio por mes
    lines.append("--- Estacionalidad: Retorno Promedio por Mes ---")
    monthly = hist["return"].groupby(hist.index.month).mean()
    meses = ["Ene","Feb","Mar","Abr","May","Jun","Jul","Ago","Sep","Oct","Nov","Dic"]
    for m, val in monthly.items():
        bar = "+" * int(abs(val)) if val > 0 else "-" * int(abs(val))
        signo = "+" if val >= 0 else ""
        mes_str = meses[int(m) - 1] if 1 <= int(m) <= 12 else str(m)
        lines.append(f"  {mes_str}: {signo}{val:.2f}%  {bar[:20]}")

    mejor_mes = monthly.idxmax()
    peor_mes = monthly.idxmin()
    mejor_str = meses[int(mejor_mes)-1] if 1 <= int(mejor_mes) <= 12 else str(mejor_mes)
    peor_str = meses[int(peor_mes)-1] if 1 <= int(peor_mes) <= 12 else str(peor_mes)
    lines.append(f"\n  -> Mejor mes histórico: {mejor_str} ({monthly[mejor_mes]:+.2f}%)")
    lines.append(f"  -> Peor mes histórico:  {peor_str} ({monthly[peor_mes]:+.2f}%)")

    # 2. Retorno promedio por día de la semana
    lines.append("\n--- Retorno Promedio por Día de la Semana ---")
    dias = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"]
    weekly = hist["return"].groupby(hist.index.dayofweek).mean()
    for d, val in weekly.items():
        if 0 <= int(d) < len(dias):
            signo = "+" if val >= 0 else ""
            lines.append(f"  {dias[int(d)]}: {signo}{val:.2f}%")

    # 3. Volatilidad por mes
    lines.append("\n--- Volatilidad Promedio por Mes (riesgo de fluctuación) ---")
    vol_monthly = hist["return"].abs().groupby(hist.index.month).mean()
    for m, val in vol_monthly.items():
        mes_str = meses[int(m) - 1] if 1 <= int(m) <= 12 else str(m)
        lines.append(f"  {mes_str}: {val:.2f}% movimiento diario promedio")

    # 4. Insider transactions
    lines.append("\n--- Transacciones de Insiders Recientes ---")
    try:
        t = yf.Ticker(ticker)
        ins = t.insider_transactions
        if ins is not None and not ins.empty:
            for _, row in ins.head(6).iterrows():
                name = str(row.get("Insider", "N/D"))[:20]
                trans = row.get("Transaction", "N/D")
                shares = row.get("Shares", "N/D")
                shares_str = f"{shares:,}" if isinstance(shares, (int, float)) else str(shares)
                lines.append(f"  {name}: {trans} {shares_str} acciones")
        else:
            lines.append("  No hay datos de insiders disponibles")
    except Exception:
        lines.append("  No se pudieron obtener datos de insiders")

    # 5. Institutional holders
    lines.append("\n--- Principales Inversores Institucionales ---")
    try:
        t = yf.Ticker(ticker)
        inst = t.institutional_holders
        if inst is not None and not inst.empty:
            for _, row in inst.head(5).iterrows():
                holder = str(row.get("Holder", "N/D"))[:30]
                pct = row.get("% Out", None)
                pct_str = f"{pct*100:.2f}%" if isinstance(pct, float) else "N/D"
                lines.append(f"  {holder}: {pct_str} del float")
        else:
            lines.append("  No hay datos institucionales disponibles")
    except Exception:
        lines.append("  No se pudieron obtener inversores institucionales")

    # 6. Short interest
    lines.append("\n--- Short Interest (apuestas bajistas) ---")
    try:
        t = yf.Ticker(ticker)
        info = t.info
        short_pct = info.get("shortPercentOfFloat")
        short_ratio = info.get("shortRatio")
        if short_pct:
            lines.append(f"  Short % del float: {short_pct*100:.1f}%")
            if short_pct > 0.20:
                lines.append("  -> ALTO short interest: >20% apostando a que baje (posible short squeeze)")
            elif short_pct > 0.10:
                lines.append("  -> Short interest moderado: 10-20%")
            else:
                lines.append("  -> Short interest bajo: <10% (señal neutral/positiva)")
        if short_ratio:
            lines.append(f"  Days to cover: {short_ratio:.1f} días")
        if not short_pct:
            lines.append("  Datos de short interest no disponibles")
    except Exception:
        lines.append("  No se pudieron obtener datos de short interest")

    # 7. Estadísticas generales
    lines.append("\n--- Estadísticas Generales del Período ---")
    total_return = ((hist["Close"].iloc[-1] / hist["Close"].iloc[0]) - 1) * 100
    volatilidad_anual = hist["return"].std() * (252 ** 0.5)
    lines.append(f"  Retorno total del período: {total_return:+.1f}%")
    lines.append(f"  Volatilidad anualizada: {volatilidad_anual:.1f}%")
    lines.append(f"  Días positivos: {(hist['return'] > 0).sum()} ({(hist['return'] > 0).mean()*100:.1f}%)")
    lines.append(f"  Días negativos: {(hist['return'] < 0).sum()} ({(hist['return'] < 0).mean()*100:.1f}%)")

    return "\n".join(lines)


def render():
    st.subheader("Buscador de Patrones — Estilo Renaissance Technologies")
    st.caption("Descubre ventajas estadísticas ocultas: ¿en qué meses sube más? ¿qué hacen los insiders?")

    md = MarketData()

    with st.form("pattern_form"):
        col1, col2 = st.columns(2)
        with col1:
            ticker_input = st.text_input(
                "Ticker",
                placeholder="Ej: AAPL, TSLA, SPY",
            ).strip().upper()
        with col2:
            periodo = st.selectbox("Período de análisis", list(PERIOD_MAP.keys()))

        submitted = st.form_submit_button("Buscar Patrones", use_container_width=True)

    if submitted:
        if not ticker_input:
            st.warning("Ingresa un ticker para analizar.")
            return

        with st.spinner(f"Calculando patrones estadísticos de {ticker_input}..."):
            yf_period = PERIOD_MAP[periodo]
            patterns_data = _calculate_patterns(ticker_input, periodo, md)

        if "Datos insuficientes" in patterns_data or "Error" in patterns_data:
            st.error(patterns_data)
            return

        system_prompt = (
            "Eres un investigador cuantitativo en Renaissance Technologies buscando "
            "ventajas estadísticas en el mercado. Explicas los patrones de forma "
            "clara para que inversores sin experiencia técnica puedan aprovecharlos."
        )

        user_prompt = (
            f"Con los siguientes datos estadísticos calculados para {ticker_input} "
            f"en los últimos {periodo}:\n\n"
            + patterns_data
            + "\n\nIdentifica y explica los patrones más relevantes:\n"
            "1. Estacionalidad: ¿en qué meses históricamente sube más? ¿y baja?\n"
            "   Comenta los meses más destacados con números exactos\n"
            "2. Patrones por día de la semana: ¿hay algún día consistentemente mejor?\n"
            "3. Movimientos de insiders: ¿los directivos están comprando o vendiendo?\n"
            "   (los insiders conocen mejor que nadie la salud de la empresa)\n"
            "4. Tendencia institucional: ¿los grandes fondos están entrando o saliendo?\n"
            "5. Short interest: ¿qué porcentaje está apostando a que baje?\n"
            "   ¿hay riesgo o potencial de 'short squeeze'?\n"
            "6. La ventaja estadística más clara: ¿qué patrón es más confiable?\n"
            "7. Cómo podría un inversor aprovechar estos patrones de forma práctica\n"
            "8. Advertencia: limitaciones de usar patrones históricos para predecir\n\n"
            "Explica cada concepto con analogías simples (sin jerga).\n"
            "Formato: memo Renaissance con tablas de datos y conclusión práctica accionable."
        )

        with st.spinner("Analizando con IA... puede tomar 20-30 segundos"):
            try:
                provider = st.session_state.get("ai_provider", "auto")
                client = ClaudeClient(provider=provider)
                resultado, usado = client.analyze(user_prompt, system_prompt, use_web_search=(provider in ("auto", "anthropic")))
                st.session_state["pattern_result"] = resultado
                st.session_state["pattern_provider_used"] = usado
                st.session_state["pattern_ticker"] = ticker_input
                st.session_state["pattern_periodo"] = periodo
            except ValueError as e:
                st.error(str(e))
                return
            except Exception as e:
                st.error(f"Error: {str(e)}")
                return

    if "pattern_result" in st.session_state:
        st.divider()
        used = st.session_state.get("pattern_provider_used", "")
        ticker_lbl = st.session_state.get("pattern_ticker", "")
        periodo_lbl = st.session_state.get("pattern_periodo", "")
        st.markdown(
            f"### Patrones Estadísticos — {ticker_lbl} ({periodo_lbl})"
            f"  <small style='color:#64748b;font-size:0.75rem'>via {used}</small>",
            unsafe_allow_html=True,
        )
        st.markdown(st.session_state["pattern_result"])

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            if st.button("Nuevo análisis", key="pattern_reset"):
                for k in ["pattern_result", "pattern_provider_used", "pattern_ticker", "pattern_periodo"]:
                    st.session_state.pop(k, None)
                st.rerun()
        with col2:
            st.download_button("Descargar .txt", data=st.session_state["pattern_result"],
                               file_name=f"patrones_{ticker_lbl}.txt", mime="text/plain", key="pattern_txt")
        with col3:
            if st.button("💾 Guardar", key="pattern_save"):
                save_analysis("Buscador de Patrones", ticker_lbl, st.session_state["pattern_result"])
                st.success("Guardado")
        with col4:
            try:
                pdf_bytes = export_analysis_to_pdf(
                    "Buscador de Patrones", "Pattern Finder", st.session_state["pattern_result"], ticker_lbl
                )
                st.download_button("📄 PDF", data=pdf_bytes, file_name=f"patrones_{ticker_lbl}.pdf",
                                   mime="application/pdf", key="pattern_pdf")
            except Exception:
                pass
