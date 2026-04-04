"""
03_Registro.py — Registro por texto, foto IA y código de barras
Sprints S4, S5, S6 · i18n S13
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

import streamlit as st
from src.db.queries import insertar_alimento, get_o_crear_usuario_activo, get_totales_dia, get_objetivo
from src.db.schema import inicializar_db
from src.alimentacion.openfoodfacts import buscar_por_texto, buscar_por_barcode, ajustar_por_porcion
from src.alimentacion.vision_ia import analizar_foto, resultado_a_registro
from src.utils.helpers import hoy
from src.utils.i18n import t, selector_idioma_sidebar
from src.utils.styles import inject_styles
from src.utils.auth_guard import auth_badge

st.set_page_config(page_title="Registro · Hackea", page_icon="🍽️", layout="wide")
inject_styles()

selector_idioma_sidebar()
auth_badge()

inicializar_db()
uid      = get_o_crear_usuario_activo()
objetivo = get_objetivo(uid)
totales  = get_totales_dia(uid)

kcal_obj = objetivo["kcal_objetivo"] if objetivo else 2000
kcal_hoy = totales["kcal"] or 0
restante = max(0, kcal_obj - kcal_hoy)

st.title(t("reg.title"))
st.caption(t("reg.caption", kcal_hoy=kcal_hoy, restante=restante))
st.divider()

MOMENTOS = ["desayuno","media_mañana","almuerzo","merienda","cena","extra"]
momento  = st.selectbox(t("reg.momento"), MOMENTOS,
                        format_func=lambda x: t(f"momento.{x}"), index=2)
fecha    = st.date_input(t("reg.fecha"), value=__import__("datetime").date.today())

tab_texto, tab_foto, tab_barcode, tab_manual = st.tabs([
    t("reg.tab_texto"), t("reg.tab_foto"), t("reg.tab_barcode"), t("reg.tab_manual")
])

# ── Tab Texto (Open Food Facts) ───────────────────────────────
with tab_texto:
    query = st.text_input("", placeholder=t("reg.buscar_placeholder"))
    if query and st.button(t("reg.buscar_btn"), key="btn_buscar"):
        with st.spinner(t("reg.buscando")):
            resultados = buscar_por_texto(query)
        if not resultados:
            st.warning(t("reg.sin_resultados"))
        else:
            st.success(t("reg.resultados", n=len(resultados)))
            for i, r in enumerate(resultados):
                marca_txt = f" · {r['marca']}" if r.get('marca') else ''
                with st.expander(f"**{r['alimento']}**{marca_txt} — {r['kcal']} kcal/100g"):
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric(t("macro.kcal")+"/100g", r["kcal"])
                    c2.metric(t("macro.proteina"), f"{r['proteina_g']}g")
                    c3.metric(t("macro.carbs"),    f"{r['cho_g']}g")
                    c4.metric(t("macro.grasa"),    f"{r['grasa_g']}g")
                    gramos = st.number_input(t("reg.gramos"), 10.0, 1000.0, 100.0, 10.0, key=f"g_{i}")
                    if st.button(t("reg.agregar"), key=f"add_{i}"):
                        ajustado = ajustar_por_porcion(r, gramos)
                        insertar_alimento(uid, {**ajustado, "momento": momento,
                                                "fecha": fecha.strftime("%Y-%m-%d")})
                        st.success(t("reg.agregado", alimento=ajustado['alimento'], kcal=ajustado['kcal']))
                        st.rerun()

# ── Tab Foto IA ───────────────────────────────────────────────
with tab_foto:
    col_info, col_upload = st.columns([1, 1])
    with col_info:
        st.markdown("#### 🤖 Claude Vision")
        st.markdown(t("reg.foto_sub"))
        st.caption(t("reg.foto_warning"))
        st.markdown("""
        **Cómo funciona:**
        1. Sube foto de tu plato
        2. Claude Vision detecta alimentos y estima macros
        3. Ve el impacto en tu plan calórico
        4. Ajusta si necesitas y guarda
        """)
    with col_upload:
        foto = st.file_uploader(t("reg.foto_upload"), type=["jpg","jpeg","png","webp"])
        if foto:
            st.image(foto, caption="Tu plato", use_container_width=True)

    if foto:
        if st.button(t("reg.analizar"), use_container_width=True):
            with st.spinner(t("reg.analizando")):
                foto.seek(0)
                resultado = analizar_foto(foto.read(), f"image/{foto.type.split('/')[-1]}")
            st.session_state["vision_resultado"] = resultado

    resultado = st.session_state.get("vision_resultado")
    if resultado:
        st.divider()
        kcal_media = (resultado["kcal_estimadas_min"] + resultado["kcal_estimadas_max"]) / 2
        confianza  = resultado.get("confianza", "—")
        color_conf = {"alta":"#22c55e","media":"#f59e0b","baja":"#ef4444","demo":"#a78bfa"}.get(confianza,"#94a3b8")

        # ── Cabecera resultado ─────────────────────────────────
        proveedor = resultado.get("_proveedor", "")
        prov_txt  = f" · via {proveedor}" if proveedor and proveedor != "Demo" else ""
        cab_col, kcal_col = st.columns([3, 1])
        with cab_col:
            st.markdown(f"""
            <div style="background:#0d1f3c;border:1px solid #1e3a5f;border-radius:12px;padding:16px 20px;">
              <div style="font-size:1.1rem;font-weight:700;color:#e2e8f0;">🍽️ {', '.join(resultado.get('alimentos',[]))}</div>
              <div style="color:#94a3b8;font-size:0.82rem;margin-top:6px;">
                Rango: <b style="color:#0f9d7a">{resultado['kcal_estimadas_min']}–{resultado['kcal_estimadas_max']} kcal</b>
                &nbsp;·&nbsp;
                Confianza: <b style="color:{color_conf}">{confianza.upper()}</b>
                <span style="color:#64748b;">{prov_txt}</span>
              </div>
            </div>
            """, unsafe_allow_html=True)
        with kcal_col:
            st.metric("kcal estimadas", f"{kcal_media:.0f}")

        # ── Macros detectados ─────────────────────────────────
        mc1, mc2, mc3 = st.columns(3)
        mc1.metric(t("macro.proteina"), f"{resultado.get('proteina_g',0):.0f} g")
        mc2.metric(t("macro.carbs"),    f"{resultado.get('carbohidrato_g',0):.0f} g")
        mc3.metric(t("macro.grasa"),    f"{resultado.get('grasa_g',0):.0f} g")

        # ── Impacto en el plan del día ────────────────────────
        st.markdown("#### 📊 Impacto en tu plan de hoy")
        kcal_nueva  = kcal_hoy + kcal_media
        resta_kcal  = kcal_obj - kcal_nueva
        pct_tras    = min(kcal_nueva / kcal_obj * 100, 150) if kcal_obj else 0
        color_imp   = "#22c55e" if pct_tras <= 100 else "#ef4444"

        ic1, ic2, ic3 = st.columns(3)
        ic1.metric("Kcal antes", f"{kcal_hoy:.0f}")
        ic2.metric("Kcal tras añadir", f"{kcal_nueva:.0f}", delta=f"+{kcal_media:.0f}")
        ic3.metric("Restante del día", f"{max(0, resta_kcal):.0f}",
                   delta=f"{resta_kcal:+.0f}", delta_color="normal" if resta_kcal > 0 else "inverse")

        st.markdown(f"""
        <div style="background:#1e3a5f;border-radius:8px;height:16px;margin:8px 0;">
          <div style="background:{color_imp};width:{min(pct_tras,100):.0f}%;height:16px;border-radius:8px;
                      display:flex;align-items:center;padding-left:8px;">
            <span style="color:#fff;font-size:0.72rem;font-weight:700;">{pct_tras:.0f}% del objetivo</span>
          </div>
        </div>
        """, unsafe_allow_html=True)

        if pct_tras > 100:
            st.warning(f"⚠️ Esta comida supera tu objetivo diario en {kcal_nueva - kcal_obj:.0f} kcal.")
        elif resta_kcal < 200:
            st.info(f"ℹ️ Solo quedan {resta_kcal:.0f} kcal para el resto del día. Elige opciones ligeras.")
        else:
            st.success(f"✅ Quedan {resta_kcal:.0f} kcal disponibles. Vas bien.")

        if resultado.get("notas"):
            st.caption(f"📝 {resultado['notas']}")

        # ── Ajustar y confirmar ───────────────────────────────
        st.divider()
        st.markdown(t("reg.ajustar"))
        col_adj1, col_adj2 = st.columns(2)
        with col_adj1:
            kcal_conf = st.number_input(t("macro.kcal"), value=float(kcal_media), step=10.0)
        with col_adj2:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button(t("reg.confirmar"), use_container_width=True):
                reg = resultado_a_registro(resultado, momento)
                reg["kcal"]  = kcal_conf
                reg["fecha"] = fecha.strftime("%Y-%m-%d")
                insertar_alimento(uid, reg)
                st.session_state.pop("vision_resultado", None)
                st.success(t("reg.guardado"))
                st.rerun()

# ── Tab Barcode ───────────────────────────────────────────────
with tab_barcode:
    st.markdown(t("reg.barcode_sub"))
    barcode = st.text_input(t("reg.barcode_input"), placeholder="Ej: 7613035416000")
    if barcode and st.button(t("reg.barcode_buscar")):
        with st.spinner(t("reg.buscando")):
            prod = buscar_por_barcode(barcode)
        if prod:
            st.success(f"**{prod['alimento']}** encontrado.")

            # Valores por 100g
            st.caption("Valores por 100g:")
            c1,c2,c3,c4 = st.columns(4)
            c1.metric(t("macro.kcal")+"/100g", prod["kcal"])
            c2.metric(t("macro.proteina"),     f"{prod['proteina_g']}g")
            c3.metric(t("macro.carbs"),        f"{prod['cho_g']}g")
            c4.metric(t("macro.grasa"),        f"{prod['grasa_g']}g")

            # Porción sugerida del envase
            porcion_sugerida = float(prod.get("porcion_g") or 100.0)
            porcion_str      = prod.get("porcion_str", "")
            if porcion_str:
                st.info(f"📦 Porción del envase: **{porcion_str}** ({porcion_sugerida:.0f} g)")

            gramos = st.number_input(
                t("reg.gramos"), 5.0, 2000.0,
                value=porcion_sugerida, step=5.0, key="g_bc"
            )

            # Vista previa ajustada
            if gramos != 100.0:
                ajuste_prev = ajustar_por_porcion(prod, gramos)
                st.caption(f"Para {gramos:.0f}g: **{ajuste_prev['kcal']} kcal** · "
                           f"{ajuste_prev['proteina_g']}g prot · "
                           f"{ajuste_prev['cho_g']}g carbs · "
                           f"{ajuste_prev['grasa_g']}g grasa")

            if st.button(t("reg.barcode_agregar")):
                ajustado = ajustar_por_porcion(prod, gramos)
                insertar_alimento(uid, {**ajustado, "momento": momento,
                                        "fecha": fecha.strftime("%Y-%m-%d")})
                st.success(t("reg.agregado", alimento=ajustado['alimento'], kcal=ajustado['kcal']))
                st.rerun()
        else:
            st.warning(t("reg.barcode_nf"))

# ── Tab Manual ────────────────────────────────────────────────
with tab_manual:
    st.markdown(t("reg.manual_sub"))
    with st.form("manual"):
        nombre_alim = st.text_input(t("reg.nombre_alim"))
        c1,c2,c3,c4 = st.columns(4)
        with c1: kcal_m  = st.number_input(t("macro.kcal"),     0.0, 5000.0, 0.0, 10.0)
        with c2: prot_m  = st.number_input(t("macro.proteina"), 0.0,  200.0, 0.0,  1.0)
        with c3: cho_m   = st.number_input(t("macro.carbs"),    0.0,  400.0, 0.0,  1.0)
        with c4: grasa_m = st.number_input(t("macro.grasa"),    0.0,  150.0, 0.0,  0.5)
        guardar_m = st.form_submit_button(t("reg.guardar_manual"), use_container_width=True)

    if guardar_m and nombre_alim:
        nombre_sanitizado = nombre_alim.strip()[:120]  # max 120 chars, sin espacios extremos
        if not nombre_sanitizado:
            st.warning("El nombre del alimento no puede estar vacío.")
        elif kcal_m == 0 and prot_m == 0 and cho_m == 0 and grasa_m == 0:
            st.warning("Ingresa al menos un valor nutricional antes de guardar.")
        else:
            insertar_alimento(uid, {
                "alimento": nombre_sanitizado, "kcal": kcal_m,
                "proteina_g": prot_m, "cho_g": cho_m, "grasa_g": grasa_m,
                "momento": momento, "fecha": fecha.strftime("%Y-%m-%d"), "fuente": "manual",
            })
            st.success(t("reg.agregado", alimento=nombre_sanitizado, kcal=int(kcal_m)))
