"""
00_Login.py — Autenticación con Supabase Auth
Sprint S12
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
import sys as _sys
if _sys.platform == "win32" and hasattr(_sys.stdout, "reconfigure"):
    _sys.stdout.reconfigure(encoding="utf-8")

import streamlit as st
from src.db.supabase_client import iniciar_sesion, registrar_usuario, recuperar_password
from src.db.queries import get_o_crear_usuario_por_email, get_usuario
from src.utils.i18n import t, selector_idioma_sidebar
from src.utils.styles import inject_styles

st.set_page_config(page_title="Login · Hackea", page_icon="🔐", layout="centered")
inject_styles()

selector_idioma_sidebar()

# Si ya hay sesión activa, redirigir
if st.session_state.get("auth_user"):
    st.success(f"✅ Ya estás autenticado como **{st.session_state['auth_user']['email']}**")
    st.info("Usa el menú lateral para navegar a cualquier módulo.")
    if st.button("🚪 Cerrar sesión"):
        try:
            from src.db.supabase_client import cerrar_sesion
            cerrar_sesion()
        except Exception:
            pass
        st.session_state.pop("auth_user", None)
        st.session_state.pop("auth_email", None)
        st.rerun()
    st.stop()

st.title("🔐 Hackea tu Metabolismo")
st.markdown("Inicia sesión o crea tu cuenta para comenzar.")
st.divider()

tab_login, tab_registro, tab_recuperar = st.tabs(["🔑 Iniciar sesión", "📝 Crear cuenta", "🔒 Recuperar contraseña"])

# ── Login ──────────────────────────────────────────────────────
with tab_login:
    with st.form("form_login"):
        email    = st.text_input("Email", placeholder="tu@email.com")
        password = st.text_input("Contraseña", type="password")
        submit   = st.form_submit_button("🔑 Entrar", use_container_width=True)

    if submit:
        if not email or not password:
            st.warning("Completa email y contraseña.")
        else:
            with st.spinner("Verificando..."):
                try:
                    resultado = iniciar_sesion(email, password)
                    user = resultado["user"]
                    if user:
                        uid = get_o_crear_usuario_por_email(user.email)
                        perfil = get_usuario(uid)
                        nombre = perfil["nombre"] if perfil else user.email.split("@")[0]
                        st.session_state["auth_user"]   = {"id": user.id, "email": user.email}
                        st.session_state["auth_email"]  = user.email
                        st.session_state["auth_uid"]    = uid
                        st.session_state["auth_nombre"] = nombre
                        st.success(f"✅ Bienvenido, **{nombre}**")
                        st.rerun()
                    else:
                        st.error("Credenciales incorrectas.")
                except Exception as e:
                    msg = str(e).lower()
                    if "invalid" in msg or "credentials" in msg:
                        st.error("❌ Email o contraseña incorrectos.")
                    elif "email not confirmed" in msg:
                        st.warning("📧 Revisa tu email y confirma tu cuenta antes de iniciar sesión.")
                    else:
                        st.error(f"Error: {e}")

# ── Registro ───────────────────────────────────────────────────
with tab_registro:
    with st.form("form_registro"):
        email_r  = st.text_input("Email", placeholder="tu@email.com", key="reg_email")
        pass_r   = st.text_input("Contraseña", type="password", key="reg_pass",
                                  help="Mínimo 6 caracteres")
        pass_r2  = st.text_input("Confirmar contraseña", type="password", key="reg_pass2")
        submit_r = st.form_submit_button("📝 Crear cuenta", use_container_width=True)

    if submit_r:
        if not email_r or not pass_r:
            st.warning("Completa todos los campos.")
        elif pass_r != pass_r2:
            st.error("❌ Las contraseñas no coinciden.")
        elif len(pass_r) < 6:
            st.error("❌ La contraseña debe tener al menos 6 caracteres.")
        else:
            with st.spinner("Creando cuenta..."):
                try:
                    resultado = registrar_usuario(email_r, pass_r)
                    user = resultado["user"]
                    if user:
                        st.success("✅ Cuenta creada. Revisa tu email para confirmarla y luego inicia sesión.")
                    else:
                        st.error("No se pudo crear la cuenta.")
                except Exception as e:
                    msg = str(e).lower()
                    if "already registered" in msg or "already exists" in msg:
                        st.warning("⚠️ Ese email ya tiene una cuenta. Ve a **Iniciar sesión**.")
                    else:
                        st.error(f"Error: {e}")

# ── Recuperar contraseña ───────────────────────────────────────
with tab_recuperar:
    with st.form("form_recuperar"):
        email_rec = st.text_input("Email de tu cuenta", placeholder="tu@email.com", key="rec_email")
        submit_rec = st.form_submit_button("📧 Enviar enlace de recuperación", use_container_width=True)

    if submit_rec:
        if not email_rec:
            st.warning("Ingresa tu email.")
        else:
            with st.spinner("Enviando..."):
                try:
                    recuperar_password(email_rec)
                    st.success("✅ Si el email existe, recibirás un enlace para restablecer tu contraseña.")
                except Exception as e:
                    st.error(f"Error: {e}")

st.divider()
st.caption("🔒 Autenticación segura con Supabase · Tus datos están cifrados")
