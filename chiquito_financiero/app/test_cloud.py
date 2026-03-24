import sys
print(f"[TEST] Python {sys.version}", flush=True)

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

st.title("Test Chiquito Finanzas")
st.write(f"Python: {sys.version}")
st.write("pandas OK:", pd.__version__)
st.write("plotly OK:", go.__version__)

try:
    from calculators import COSTOS_FIJOS_BASE
    st.success("calculators OK")
except Exception as e:
    st.error(f"calculators FALLO: {e}")

try:
    from data_loader import load_caja
    df = load_caja()
    st.success(f"data_loader OK — {len(df)} filas")
except Exception as e:
    st.error(f"data_loader FALLO: {e}")

try:
    from charts import chart_costos_dona
    st.success("charts OK")
except Exception as e:
    st.error(f"charts FALLO: {e}")
