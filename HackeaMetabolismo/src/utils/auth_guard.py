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


def get_uid_activo() -> int:
    """Retorna el usuario_id SQLite del usuario autenticado, o el demo si no hay sesión."""
    import streamlit as _st
    auth_user = _st.session_state.get("auth_user")
    if auth_user:
        uid = _st.session_state.get("auth_uid")
        if uid:
            return uid
        from src.db.queries import get_o_crear_usuario_por_email
        uid = get_o_crear_usuario_por_email(auth_user["email"])
        _st.session_state["auth_uid"] = uid
        return uid
    from src.db.queries import get_o_crear_usuario_activo
    return get_o_crear_usuario_activo()


def auth_badge():
    """Muestra badge del usuario (nombre + email) en el sidebar."""
    user = st.session_state.get("auth_user")
    if user:
        nombre = st.session_state.get("auth_nombre") or user["email"].split("@")[0]
        with st.sidebar:
            st.caption(f"👤 **{nombre}**")
            st.caption(f"✉️ {user['email']}")
            if st.button("🚪 Salir", key="logout_badge"):
                try:
                    from src.db.supabase_client import cerrar_sesion
                    cerrar_sesion()
                except Exception:
                    pass
                st.session_state.pop("auth_user", None)
                st.session_state.pop("auth_email", None)
                st.session_state.pop("auth_nombre", None)
                st.rerun()
