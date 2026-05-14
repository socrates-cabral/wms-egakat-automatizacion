import sys
sys.stdout.reconfigure(encoding="utf-8")

"""
auth.py — Login contra Supabase Auth.

Sprint 5, paso 3. Pantalla de login antes de acceder a cualquier página.

Diseño:
- Backend: Supabase Auth (sign_in_with_password). Un solo almacén de
  usuarios — agregar a alguien = crear su cuenta en Supabase, nada más.
- La sesión autenticada entrega el UUID → se enchufa en supabase_repo
  vía set_authenticated_client(). RLS pasa a ser la barrera real porque
  el cliente usa la anon/publishable key + el JWT del usuario.
- El login SOLO se exige cuando DATA_SOURCE=supabase. En modo Excel la
  app sigue funcionando sin login (uso local personal).

Claves del .env:
    SUPABASE_FINANZAS_URL          (ya configurada)
    SUPABASE_FINANZAS_ANON_KEY     ← nueva — la "Publishable key" del panel
                                     Settings → API. NO la service_role.

Sin "remember me" por ahora: cada sesión de navegador pide login. Para
una app de finanzas familiar es aceptable; cookies persistentes pueden
agregarse después si se necesita.
"""

import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent.parent / ".env")

import supabase_repo
import data_source


# ── Credenciales ──────────────────────────────────────────────────────────────

def _anon_credentials() -> tuple[str, str]:
    """URL + anon/publishable key (para auth y para el cliente con RLS)."""
    url = os.getenv("SUPABASE_FINANZAS_URL", "")
    key = (
        os.getenv("SUPABASE_FINANZAS_ANON_KEY")
        or os.getenv("SUPABASE_FINANZAS_PUBLISHABLE_KEY")
        or ""
    )
    return url, key


def _auth_enabled() -> bool:
    """El login solo se exige cuando la fuente de datos es Supabase."""
    return data_source.USANDO_SUPABASE


# ── Sesión ────────────────────────────────────────────────────────────────────

def is_authenticated() -> bool:
    return bool(st.session_state.get("_auth_user_id"))


def current_email() -> str:
    return st.session_state.get("_auth_email", "")


def current_user_id() -> str:
    return st.session_state.get("_auth_user_id", "")


def login(email: str, password: str) -> tuple[bool, str]:
    """Autentica contra Supabase Auth. Retorna (ok, mensaje_error)."""
    url, key = _anon_credentials()
    if not url or not key:
        return False, ("Falta SUPABASE_FINANZAS_URL o SUPABASE_FINANZAS_ANON_KEY "
                       "en el .env (la 'Publishable key' del panel de Supabase).")

    email = (email or "").strip()
    if not email or not password:
        return False, "Ingresa email y contraseña."

    try:
        from supabase import create_client
        client = create_client(url, key)
        resp = client.auth.sign_in_with_password({"email": email, "password": password})
        user = getattr(resp, "user", None)
        if user is None:
            return False, "Credenciales inválidas."
    except Exception:
        # No exponer detalles del backend al usuario final
        return False, "Credenciales inválidas o error de conexión."

    # Sesión válida — guardar y enganchar el repo al cliente autenticado (JWT)
    st.session_state["_auth_user_id"] = user.id
    st.session_state["_auth_email"]   = getattr(user, "email", email)
    st.session_state["_auth_client"]  = client
    supabase_repo.set_authenticated_client(client, user.id)

    # El caché de st.cache_data no distingue usuarios — limpiarlo en cada
    # login evita que datos de una sesión previa se sirvan a otra cuenta.
    st.cache_data.clear()
    return True, ""


def logout():
    """Cierra la sesión y limpia todo rastro del usuario."""
    client = st.session_state.get("_auth_client")
    if client is not None:
        try:
            client.auth.sign_out()
        except Exception:
            pass
    for k in ("_auth_user_id", "_auth_email", "_auth_client"):
        st.session_state.pop(k, None)
    supabase_repo.set_authenticated_client(None, None)
    st.cache_data.clear()


# ── Gate ──────────────────────────────────────────────────────────────────────

def require_login():
    """Portón de entrada. Llamar al inicio de main.py, tras init_config().

    - DATA_SOURCE=excel  → no exige login, retorna de inmediato.
    - DATA_SOURCE=supabase + sesión activa → re-engancha el repo y retorna.
    - DATA_SOURCE=supabase + sin sesión → muestra el formulario y st.stop().
    """
    if not _auth_enabled():
        return

    if is_authenticated():
        # Re-enganchar en cada rerun (los globals del módulo no persisten
        # garantizadamente entre reruns de Streamlit).
        client = st.session_state.get("_auth_client")
        uid = st.session_state.get("_auth_user_id")
        if client is not None and uid:
            supabase_repo.set_authenticated_client(client, uid)
        return

    _render_login_form()
    st.stop()


def _render_login_form():
    """Formulario de login centrado, estilo oscuro coherente con la app."""
    st.markdown("""
    <style>
    .login-hero { text-align:center; margin: 8vh 0 2rem 0; }
    .login-hero h1 { font-size: 1.8rem; color:#E2E8F0; margin-bottom:0.2rem; }
    .login-hero p  { color:#94A3B8; font-size:0.9rem; }
    </style>
    <div class="login-hero">
        <h1>💰 Finanzas Personales</h1>
        <p>Ingresa con tu cuenta para continuar</p>
    </div>
    """, unsafe_allow_html=True)

    _c1, _c2, _c3 = st.columns([1, 1.4, 1])
    with _c2:
        with st.form("_login_form", clear_on_submit=False):
            email = st.text_input("Email", placeholder="tu@correo.com")
            password = st.text_input("Contraseña", type="password", placeholder="••••••••")
            submitted = st.form_submit_button("Ingresar", type="primary", use_container_width=True)
        if submitted:
            ok, err = login(email, password)
            if ok:
                st.rerun()
            else:
                st.error(err)
        st.caption("¿Sin cuenta? El administrador familiar la crea en Supabase.")


def render_logout_sidebar():
    """Bloque de sesión + botón de logout para el sidebar. Llamar desde main.py."""
    if not _auth_enabled() or not is_authenticated():
        return
    with st.sidebar:
        st.caption(f"👤 {current_email()}")
        if st.button("Cerrar sesión", use_container_width=True, key="_btn_logout"):
            logout()
            st.rerun()
