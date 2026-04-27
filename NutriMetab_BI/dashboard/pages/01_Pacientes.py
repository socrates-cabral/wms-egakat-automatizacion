"""
01_Pacientes.py — Registro, historial y perfil nutricional
Sprint 3
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

import streamlit as st
import pandas as pd
from src.utils.helpers import get_db_connection
from src.procesamiento.calculos_nutri import (
    evaluar_paciente, Sexo, NivelActividad, clasificar_imc,
)
from src.procesamiento.calculos_metabol import aplicar_protocolo_40plus
from dashboard.components.kpi_cards import kpi_card, badge_riesgo, alerta_box

st.set_page_config(page_title="Pacientes · NutriMetab", page_icon="👤", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #0c1422; }
    section[data-testid="stSidebar"] { background-color: #080E1A; }
    h1,h2,h3 { color: #14b8a6; }
</style>
""", unsafe_allow_html=True)

st.title("👤 Pacientes")
st.markdown("Registro, historial y evaluación nutricional individual.")
st.divider()

# ── Carga de datos ─────────────────────────────────────────────
@st.cache_data(ttl=60)
def cargar_pacientes() -> pd.DataFrame:
    with get_db_connection() as conn:
        return pd.read_sql_query("SELECT * FROM pacientes ORDER BY nombre", conn)

df = cargar_pacientes()

if df.empty:
    st.warning("Sin pacientes en la base de datos. Ejecuta el pipeline de ingesta.")
    st.stop()

# ── Filtros ────────────────────────────────────────────────────
col_f1, col_f2, col_f3 = st.columns(3)
with col_f1:
    busqueda = st.text_input("🔍 Buscar por nombre o ID", "")
with col_f2:
    filtro_sexo = st.selectbox("Sexo", ["Todos", "M", "F"])
with col_f3:
    filtro_nivel = st.selectbox("Nivel actividad", ["Todos"] + sorted(df["nivel_actividad"].dropna().unique().tolist()))

df_filtrado = df.copy()
if busqueda:
    df_filtrado = df_filtrado[
        df_filtrado["nombre"].str.contains(busqueda, case=False, na=False) |
        df_filtrado["id"].str.contains(busqueda, case=False, na=False)
    ]
if filtro_sexo != "Todos":
    df_filtrado = df_filtrado[df_filtrado["sexo"] == filtro_sexo]
if filtro_nivel != "Todos":
    df_filtrado = df_filtrado[df_filtrado["nivel_actividad"] == filtro_nivel]

st.markdown(f"**{len(df_filtrado)}** pacientes encontrados.")
st.divider()

# ── Tabla resumen ──────────────────────────────────────────────
cols_tabla = ["id", "nombre", "edad", "sexo", "peso_kg", "talla_m", "nivel_actividad", "fecha_registro"]
st.dataframe(
    df_filtrado[[c for c in cols_tabla if c in df_filtrado.columns]],
    use_container_width=True, hide_index=True,
)

st.divider()

# ── Evaluación individual ──────────────────────────────────────
st.markdown("### 🔬 Evaluación nutricional individual")
opciones = df["nombre"].tolist()
seleccionado = st.selectbox("Seleccionar paciente", opciones)

if seleccionado:
    pac = df[df["nombre"] == seleccionado].iloc[0]

    try:
        sexo_e = Sexo.MASCULINO if str(pac.get("sexo", "M")).upper() == "M" else Sexo.FEMENINO
        nivel_e = NivelActividad(str(pac.get("nivel_actividad", "moderado")).lower())
        resultado = evaluar_paciente(
            peso_kg=float(pac["peso_kg"]),
            talla_m=float(pac["talla_m"]),
            edad=int(pac["edad"]),
            sexo=sexo_e,
            nivel_actividad=nivel_e,
        )

        st.markdown(f"#### {pac['nombre']} · {int(pac['edad'])} años · {pac['sexo']}")

        c1, c2, c3, c4, c5 = st.columns(5)
        with c1: kpi_card("IMC", resultado.imc)
        with c2: kpi_card("Categoría IMC", resultado.categoria_imc)
        with c3: kpi_card("TMB (kcal)", resultado.tmb_kcal)
        with c4: kpi_card("GET (kcal)", resultado.get_kcal)
        with c5: kpi_card("Proteína (g/día)", resultado.proteina_g)

        st.markdown("**Distribución de macros:**")
        mc1, mc2, mc3 = st.columns(3)
        with mc1: kpi_card("Proteína (g)", resultado.proteina_g, color="#38bdf8")
        with mc2: kpi_card("Carbohidratos (g)", resultado.carbohidrato_g, color="#f59e0b")
        with mc3: kpi_card("Grasa (g)", resultado.grasa_g, color="#a78bfa")

        # Protocolo +40
        if int(pac["edad"]) >= 40:
            st.divider()
            st.markdown("#### 🔬 Protocolo +40 activado")
            p40 = aplicar_protocolo_40plus(
                edad=int(pac["edad"]),
                peso_kg=float(pac["peso_kg"]),
                tdee_base=resultado.get_kcal,
            )
            pa1, pa2, pa3 = st.columns(3)
            with pa1: kpi_card("TDEE ajustado (kcal)", p40.tdee_ajustado, color="#f97316")
            with pa2: kpi_card("Proteína mín. (g)", p40.proteina_min_g, color="#f97316")
            with pa3: kpi_card("Proteína máx. (g)", p40.proteina_max_g, color="#f97316")
            for alerta in p40.alertas_40plus:
                alerta_box(alerta["mensaje"], alerta["severidad"])

        if pac.get("notas"):
            st.info(f"📝 Notas: {pac['notas']}")

    except Exception as e:
        st.error(f"Error evaluando paciente: {e}")
