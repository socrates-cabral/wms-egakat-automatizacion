"""
05_Reportes.py — Generación automática de reportes Excel / HTML
Sprint 6
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

import streamlit as st
from datetime import datetime
from src.reportes.generar_reporte import pipeline_reporte, construir_df_reporte
from dashboard.components.kpi_cards import kpi_card, alerta_box

st.set_page_config(page_title="Reportes · NutriMetab", page_icon="📊", layout="wide")
st.markdown("""<style>
    .stApp { background-color: #0c1422; }
    section[data-testid="stSidebar"] { background-color: #080E1A; }
    h1,h2,h3 { color: #14b8a6; }
</style>""", unsafe_allow_html=True)

st.title("📊 Reportes")
st.markdown("Generación automática de reportes Excel y HTML.")
st.divider()

# ── Vista previa de datos ──────────────────────────────────────
st.markdown("#### Vista previa del reporte")
try:
    df_prev = construir_df_reporte()
    if df_prev.empty:
        st.warning("Sin datos para reportar. Ejecuta el pipeline de ingesta primero.")
        st.stop()

    c1, c2, c3, c4 = st.columns(4)
    with c1: kpi_card("Pacientes", len(df_prev))
    with c2: kpi_card("Riesgo Alto+", len(df_prev[df_prev["Nivel Riesgo"].isin(["Alto","Muy alto"])]), color="#ef4444")
    with c3: kpi_card("IMC promedio", round(df_prev["IMC"].mean(), 1))
    with c4: kpi_card("Score prom.", round(df_prev["Score Riesgo"].mean(), 1))

    st.dataframe(df_prev, use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"Error preparando datos: {e}")
    st.stop()

st.divider()

# ── Generación ────────────────────────────────────────────────
st.markdown("#### Generar reportes")
col_xl, col_html = st.columns(2)

with col_xl:
    st.markdown("**Excel** — con formato condicional de riesgo")
    if st.button("📥 Generar Excel", use_container_width=True):
        with st.spinner("Generando Excel..."):
            try:
                res = pipeline_reporte()
                alerta_box(f"Excel generado: `{res['excel']}`", "success")
                with open(res["excel"], "rb") as f:
                    st.download_button(
                        "⬇️ Descargar Excel",
                        data=f,
                        file_name=Path(res["excel"]).name,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True,
                    )
            except Exception as e:
                st.error(f"Error: {e}")

with col_html:
    st.markdown("**HTML** — reporte web con KPIs y tabla")
    if st.button("📄 Generar HTML", use_container_width=True):
        with st.spinner("Generando HTML..."):
            try:
                res = pipeline_reporte()
                html_path = Path(res["html"])
                alerta_box(f"HTML generado: `{res['html']}`", "success")
                with open(html_path, "r", encoding="utf-8") as f:
                    html_content = f.read()
                st.download_button(
                    "⬇️ Descargar HTML",
                    data=html_content,
                    file_name=html_path.name,
                    mime="text/html",
                    use_container_width=True,
                )
            except Exception as e:
                st.error(f"Error: {e}")

# ── Historial de reportes ──────────────────────────────────────
st.divider()
st.markdown("#### Reportes generados")
exports_dir = Path(__file__).parent.parent.parent / "data" / "exports"
exports = sorted(exports_dir.glob("reporte_nutrimetab_*"), reverse=True) if exports_dir.exists() else []

if exports:
    for archivo in exports[:10]:
        icono = "📗" if archivo.suffix == ".xlsx" else "📄"
        fecha_arch = datetime.fromtimestamp(archivo.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
        st.markdown(f"{icono} `{archivo.name}` — {fecha_arch}")
else:
    st.caption("Sin reportes generados aún.")
