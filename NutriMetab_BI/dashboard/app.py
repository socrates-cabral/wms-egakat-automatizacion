"""
NutriMetab BI — Dashboard principal
Port: 8504
Tema: dark (#0c1422 / #080E1A), teal (#14b8a6)
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

import streamlit as st
import pandas as pd
from datetime import datetime
from src.utils.helpers import get_db_connection

st.set_page_config(
    page_title="NutriMetab BI",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    .stApp { background-color: #0c1422; }
    section[data-testid="stSidebar"] { background-color: #080E1A; }
    h1, h2, h3 { color: #14b8a6; }
    .metric-card {
        background-color: #0f1e30;
        border: 1px solid #14b8a6;
        border-radius: 8px;
        padding: 16px;
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)

st.title("🧬 NutriMetab BI")
st.markdown("**Sistema integrado de seguimiento metabólico y nutricional**")
st.divider()

# ── KPIs desde DB ─────────────────────────────────────────────
def cargar_kpis():
    try:
        with get_db_connection() as conn:
            df = pd.read_sql_query("SELECT * FROM pacientes", conn)
        total    = len(df)
        ultima   = df["cargado_en"].max() if "cargado_en" in df.columns else "—"
        if ultima and ultima != "—":
            try:
                ultima = datetime.strptime(ultima[:19], "%Y-%m-%d %H:%M:%S").strftime("%d/%m/%Y %H:%M")
            except Exception:
                pass
        return total, ultima, len(df)
    except Exception:
        return "—", "—", "—"

total, ultima, registros = cargar_kpis()

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Pacientes activos", total, help="Cargados desde base de datos")
with col2:
    st.metric("Última actualización", ultima, help="Fecha último procesamiento")
with col3:
    st.metric("Registros procesados", registros, help="Total registros en DB")
with col4:
    st.metric("Alertas metabólicas", "Ver →", help="Ir a página Metabolismo")

st.divider()

# ── Navegación ────────────────────────────────────────────────
st.markdown("### 📋 Módulos disponibles")

col_a, col_b = st.columns(2)
with col_a:
    st.info("**👤 Pacientes** — Registro, historial y perfil nutricional individual")
    st.info("**⚗️ Metabolismo** — Biomarcadores, WHtR, TMB, GET, TEF y score metabólico")
    st.info("**🥗 Nutrición** — Macros, planes, micronutrientes +40 y adherencia")
    st.info("**💪 Ejercicio** — Jerarquía +40, rutinas sin equipo, impacto en TDEE")
with col_b:
    st.info("**😴 Sueño** — Registro sueño, cortisol circadiano, higiene +40")
    st.info("**🤖 Modelos** — Clasificación ML de riesgo metabólico (RandomForest)")
    st.info("**📊 Reportes** — Generación automática Excel / HTML con descarga directa")

st.divider()
st.caption(f"NutriMetab BI v1.2 · Patch +40 · S1–S8b completos · {datetime.now().strftime('%d/%m/%Y')} · C:\\ClaudeWork\\NutriMetab_BI\\")
