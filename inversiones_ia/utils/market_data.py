"""
market_data.py — Capa de acceso a datos de mercado via yfinance.
Todas las llamadas a yfinance pasan por esta clase.
"""

import yfinance as yf
import pandas as pd
import numpy as np
import streamlit as st
from typing import Optional


class MarketData:

    @st.cache_data(ttl=300)
    def get_stock_info(_self, ticker: str) -> dict:
        """Retorna métricas clave de una acción. Nunca crashea."""
        try:
            t = yf.Ticker(ticker)
            info = t.info
            if not info or info.get("regularMarketPrice") is None and info.get("currentPrice") is None:
                return {"error": f"No se encontraron datos para {ticker}", "ticker": ticker}

            price = info.get("currentPrice") or info.get("regularMarketPrice") or info.get("previousClose")
            return {
                "ticker": ticker.upper(),
                "nombre": info.get("longName", ticker),
                "sector": info.get("sector", "N/D"),
                "industria": info.get("industry", "N/D"),
                "precio_actual": price,
                "moneda": info.get("currency", "USD"),
                "pe_ratio": info.get("trailingPE"),
                "pe_forward": info.get("forwardPE"),
                "eps": info.get("trailingEps"),
                "market_cap": info.get("marketCap"),
                "dividend_yield": info.get("dividendYield"),
                "beta": info.get("beta"),
                "52w_high": info.get("fiftyTwoWeekHigh"),
                "52w_low": info.get("fiftyTwoWeekLow"),
                "avg_volume": info.get("averageVolume"),
                "pb_ratio": info.get("priceToBook"),
                "ps_ratio": info.get("priceToSalesTrailing12Months"),
                "deuda_capital": info.get("debtToEquity"),
                "roe": info.get("returnOnEquity"),
                "roa": info.get("returnOnAssets"),
                "margen_bruto": info.get("grossMargins"),
                "margen_operativo": info.get("operatingMargins"),
                "margen_neto": info.get("profitMargins"),
                "descripcion": info.get("longBusinessSummary", "")[:500],
                "error": None,
            }
        except Exception as e:
            return {"error": f"Error obteniendo datos de {ticker}: {str(e)}", "ticker": ticker}

    @st.cache_data(ttl=300)
    def get_price_history(_self, ticker: str, period: str = "1y") -> pd.DataFrame:
        """Retorna DataFrame OHLCV. Retorna DataFrame vacío si falla."""
        try:
            t = yf.Ticker(ticker)
            hist = t.history(period=period)
            if hist.empty:
                return pd.DataFrame()
            return hist
        except Exception:
            return pd.DataFrame()

    @st.cache_data(ttl=300)
    def get_financials(_self, ticker: str) -> dict:
        """Retorna datos financieros históricos (ingresos, márgenes, deuda)."""
        try:
            t = yf.Ticker(ticker)
            result = {}

            # Income statement
            try:
                inc = t.financials
                if inc is not None and not inc.empty:
                    rev_row = None
                    for label in ["Total Revenue", "Revenue"]:
                        if label in inc.index:
                            rev_row = inc.loc[label]
                            break
                    op_row = None
                    for label in ["Operating Income", "EBIT"]:
                        if label in inc.index:
                            op_row = inc.loc[label]
                            break
                    net_row = None
                    for label in ["Net Income", "Net Income Common Stockholders"]:
                        if label in inc.index:
                            net_row = inc.loc[label]
                            break

                    cols = inc.columns[:4]
                    result["ingresos"] = {str(c.year): float(rev_row[c]) if rev_row is not None and c in rev_row.index and pd.notna(rev_row[c]) else None for c in cols}
                    result["ingreso_operativo"] = {str(c.year): float(op_row[c]) if op_row is not None and c in op_row.index and pd.notna(op_row[c]) else None for c in cols}
                    result["ingreso_neto"] = {str(c.year): float(net_row[c]) if net_row is not None and c in net_row.index and pd.notna(net_row[c]) else None for c in cols}
            except Exception:
                result["ingresos"] = {}

            # Balance sheet
            try:
                bs = t.balance_sheet
                if bs is not None and not bs.empty:
                    cols = bs.columns[:4]
                    deuda_row = None
                    for label in ["Total Debt", "Long Term Debt"]:
                        if label in bs.index:
                            deuda_row = bs.loc[label]
                            break
                    equity_row = None
                    for label in ["Stockholders Equity", "Total Stockholders Equity", "Common Stock Equity"]:
                        if label in bs.index:
                            equity_row = bs.loc[label]
                            break
                    result["deuda_total"] = {str(c.year): float(deuda_row[c]) if deuda_row is not None and c in deuda_row.index and pd.notna(deuda_row[c]) else None for c in cols}
                    result["patrimonio"] = {str(c.year): float(equity_row[c]) if equity_row is not None and c in equity_row.index and pd.notna(equity_row[c]) else None for c in cols}
            except Exception:
                result["deuda_total"] = {}

            # Cash flow
            try:
                cf = t.cashflow
                if cf is not None and not cf.empty:
                    cols = cf.columns[:4]
                    fcf_row = None
                    for label in ["Free Cash Flow"]:
                        if label in cf.index:
                            fcf_row = cf.loc[label]
                            break
                    result["flujo_caja_libre"] = {str(c.year): float(fcf_row[c]) if fcf_row is not None and c in fcf_row.index and pd.notna(fcf_row[c]) else None for c in cols}
            except Exception:
                result["flujo_caja_libre"] = {}

            result["error"] = None
            return result
        except Exception as e:
            return {"error": f"Error obteniendo financieros de {ticker}: {str(e)}"}

    @st.cache_data(ttl=300)
    def get_technical_indicators(_self, ticker: str, period: str = "1y") -> dict:
        """Calcula indicadores técnicos sobre datos reales de yfinance."""
        try:
            t = yf.Ticker(ticker)
            hist = t.history(period=period)

            if hist.empty or len(hist) < 30:
                return {"error": f"Datos insuficientes para calcular indicadores de {ticker}"}

            close = hist["Close"]
            high = hist["High"]
            low = hist["Low"]
            volume = hist["Volume"]

            # SMA
            sma50 = close.rolling(50).mean().iloc[-1] if len(close) >= 50 else None
            sma100 = close.rolling(100).mean().iloc[-1] if len(close) >= 100 else None
            sma200 = close.rolling(200).mean().iloc[-1] if len(close) >= 200 else None

            # RSI(14)
            delta = close.diff()
            gain = delta.clip(lower=0).rolling(14).mean()
            loss = (-delta.clip(upper=0)).rolling(14).mean()
            rs = gain / loss.replace(0, np.nan)
            rsi = (100 - (100 / (1 + rs))).iloc[-1]

            # MACD(12,26,9)
            ema12 = close.ewm(span=12, adjust=False).mean()
            ema26 = close.ewm(span=26, adjust=False).mean()
            macd_line = ema12 - ema26
            signal_line = macd_line.ewm(span=9, adjust=False).mean()
            macd_hist = macd_line - signal_line

            # Bollinger Bands(20,2)
            sma20 = close.rolling(20).mean()
            std20 = close.rolling(20).std()
            bb_upper = (sma20 + 2 * std20).iloc[-1]
            bb_lower = (sma20 - 2 * std20).iloc[-1]
            bb_mid = sma20.iloc[-1]

            # Soporte y resistencia (52w)
            precio_actual = float(close.iloc[-1])
            max_52w = float(high.rolling(252).max().iloc[-1]) if len(high) >= 252 else float(high.max())
            min_52w = float(low.rolling(252).min().iloc[-1]) if len(low) >= 252 else float(low.min())

            # Volumen promedio 20d
            vol_avg_20 = float(volume.rolling(20).mean().iloc[-1])
            vol_actual = float(volume.iloc[-1])

            # Pivots recientes (últimos 20 días)
            recent_high = float(high.iloc[-20:].max())
            recent_low = float(low.iloc[-20:].min())

            return {
                "ticker": ticker.upper(),
                "precio_actual": round(precio_actual, 2),
                "sma50": round(float(sma50), 2) if sma50 is not None and not np.isnan(sma50) else None,
                "sma100": round(float(sma100), 2) if sma100 is not None and not np.isnan(sma100) else None,
                "sma200": round(float(sma200), 2) if sma200 is not None and not np.isnan(sma200) else None,
                "rsi14": round(float(rsi), 2) if rsi is not None and not np.isnan(rsi) else None,
                "macd_line": round(float(macd_line.iloc[-1]), 4),
                "macd_signal": round(float(signal_line.iloc[-1]), 4),
                "macd_histogram": round(float(macd_hist.iloc[-1]), 4),
                "bb_upper": round(float(bb_upper), 2),
                "bb_mid": round(float(bb_mid), 2),
                "bb_lower": round(float(bb_lower), 2),
                "max_52w": round(max_52w, 2),
                "min_52w": round(min_52w, 2),
                "soporte_reciente": round(recent_low, 2),
                "resistencia_reciente": round(recent_high, 2),
                "volumen_actual": int(vol_actual),
                "volumen_promedio_20d": int(vol_avg_20),
                "volumen_vs_promedio_pct": round((vol_actual / vol_avg_20 - 1) * 100, 1) if vol_avg_20 > 0 else 0,
                "precio_vs_sma50_pct": round((precio_actual / float(sma50) - 1) * 100, 2) if sma50 and not np.isnan(sma50) else None,
                "precio_vs_sma200_pct": round((precio_actual / float(sma200) - 1) * 100, 2) if sma200 and not np.isnan(sma200) else None,
                "error": None,
                # Series para gráfico
                "_hist_close": close,
                "_hist_sma50": close.rolling(50).mean(),
                "_hist_sma200": close.rolling(200).mean(),
                "_hist_bb_upper": sma20 + 2 * std20,
                "_hist_bb_lower": sma20 - 2 * std20,
                "_hist_dates": hist.index,
            }
        except Exception as e:
            return {"error": f"Error calculando indicadores para {ticker}: {str(e)}"}

    def validate_ticker(self, ticker: str) -> bool:
        """Verifica que el ticker existe en yfinance."""
        try:
            t = yf.Ticker(ticker)
            info = t.info
            return bool(info and (info.get("regularMarketPrice") or info.get("currentPrice") or info.get("previousClose")))
        except Exception:
            return False

    def format_number(self, value, suffix="", prefix="$") -> str:
        """Formatea números grandes de manera legible."""
        if value is None:
            return "N/D"
        try:
            value = float(value)
            if abs(value) >= 1e12:
                return f"{prefix}{value/1e12:.2f}T{suffix}"
            elif abs(value) >= 1e9:
                return f"{prefix}{value/1e9:.2f}B{suffix}"
            elif abs(value) >= 1e6:
                return f"{prefix}{value/1e6:.2f}M{suffix}"
            else:
                return f"{prefix}{value:,.2f}{suffix}"
        except Exception:
            return "N/D"
