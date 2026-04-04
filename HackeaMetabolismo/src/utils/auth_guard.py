"""
auth_guard.py — Guard de autenticación para páginas Streamlit
Sprint S12 — llama require_auth() al inicio de cada página protegida
"""
import streamlit as st


def require_auth() -> dict:
    """
    Verifica que el usuario esté autenticado.
    Si no, muestra botón para ir al Login y detiene la página.
    Retorna el dict del usuario si está autenticado: {'id': ..., 'email': ...}
    """
    user = st.session_state.get("auth_user")
    if not user:
        st.warning("🔐 Debes iniciar sesión para acceder a esta sección.")
        st.page_link("pages/00_Login.py", label="→ Ir a Login", icon="🔑")
        st.stop()
    return user


def get_auth_user() -> dict | None:
    """Retorna el usuario autenticado o None (sin detener la página)."""
    return st.session_state.get("auth_user")


def auth_badge():
    """Muestra badge del usuario en el sidebar."""
    user = st.session_state.get("auth_user")
    if user:
        with st.sidebar:
            st.caption(f"👤 {user['email']}")
            if st.button("🚪 Salir", key="logout_badge"):
                try:
                    from src.db.supabase_client import cerrar_sesion
                    cerrar_sesion()
                except Exception:
                    pass
                st.session_state.pop("auth_user", None)
                st.session_state.pop("auth_email", None)
                st.rerun()
