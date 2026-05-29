"""
auth_guard.py — Guard de autenticación para páginas Streamlit
Sprint S12 — S15: persistencia de sesión via cookie (F5 no desloguea)

Patrón: refresh_token guardado en cookie 7 días. require_auth() lo restaura
automáticamente antes de redirigir al login.
"""
import streamlit as st
from datetime import datetime, timedelta

_COOKIE_NAME = "hackea_session"
_COOKIE_DAYS = 7
_GRACE_MAX   = 6   # reruns para que el CookieManager sincronice (es asíncrono)


# ── CookieManager ─────────────────────────────────────────────────────────────

def _nuevo_cm():
    """Crea CookieManager fresco por run y lo guarda en session_state.
    Debe llamarse UNA VEZ por run, antes de cualquier otro widget."""
    import extra_streamlit_components as stx
    cm = stx.CookieManager(key="hackea_cookie_mgr")
    st.session_state["_hm_cm"] = cm
    return cm


def _get_cm():
    cm = st.session_state.get("_hm_cm")
    if cm is None:
        cm = _nuevo_cm()
    return cm


def _guardar_cookie(refresh_token: str):
    if not refresh_token:
        return
    try:
        _get_cm().set(
            _COOKIE_NAME,
            refresh_token,
            expires_at=datetime.now() + timedelta(days=_COOKIE_DAYS),
            secure=True,
            same_site="none",
        )
    except Exception:
        pass


def _borrar_cookie():
    try:
        _get_cm().delete(_COOKIE_NAME)
    except Exception:
        pass


def _restaurar_desde_cookie(token: str) -> bool:
    """Restaura la sesión Supabase desde el refresh_token guardado en cookie."""
    from src.db.supabase_client import get_supabase
    from src.db.queries import get_o_crear_usuario_por_email, get_usuario
    try:
        sb = get_supabase()
        resp = sb.auth.refresh_session(token)
        user    = getattr(resp, "user", None)
        session = getattr(resp, "session", None)
        if not user:
            _borrar_cookie()
            return False
        uid    = get_o_crear_usuario_por_email(user.email)
        perfil = get_usuario(uid)
        nombre = perfil["nombre"] if perfil else (user.email or "usuario").split("@")[0]
        st.session_state["auth_user"]   = {"id": user.id, "email": user.email}
        st.session_state["auth_email"]  = user.email
        st.session_state["auth_uid"]    = uid
        st.session_state["auth_nombre"] = nombre
        # Rotar token
        nuevo = getattr(session, "refresh_token", token) if session else token
        _guardar_cookie(nuevo)
        return True
    except Exception:
        _borrar_cookie()
        return False


# ── Gate principal ────────────────────────────────────────────────────────────

def require_auth() -> dict:
    """
    Verifica que el usuario esté autenticado.
    - Si hay sesión activa en session_state → retorna el usuario.
    - Si hay cookie válida → restaura la sesión sin pedir login.
    - Si no hay nada → muestra botón de Login y detiene la página.
    """
    # CookieManager renderiza un widget — instanciar una vez por run, aquí
    cm = _nuevo_cm()

    user = st.session_state.get("auth_user")
    if user:
        return user

    # El CookieManager es asíncrono: los primeros reruns devuelven {} aunque
    # haya cookie. Esperamos hasta _GRACE_MAX reruns antes de rendirse.
    cookies  = cm.get_all() or {}
    intentos = st.session_state.get("_hm_cookie_intentos", 0)
    if not cookies and intentos < _GRACE_MAX:
        st.session_state["_hm_cookie_intentos"] = intentos + 1
        st.markdown("""
        <div style="text-align:center; margin-top:18vh; color:#94A3B8;">
            <div style="font-size:2rem;">🔥</div>
            <p style="margin-top:0.6rem;">Restaurando sesión…</p>
        </div>""", unsafe_allow_html=True)
        st.stop()

    st.session_state.pop("_hm_cookie_intentos", None)

    token = cookies.get(_COOKIE_NAME)
    if token and _restaurar_desde_cookie(token):
        st.rerun()

    # Sin sesión ni cookie válida → pedir login
    st.warning("🔐 Debes iniciar sesión para acceder a esta sección.")
    st.page_link("pages/00_Login.py", label="→ Ir a Login", icon="🔑")
    st.stop()


# ── Helpers ───────────────────────────────────────────────────────────────────

def get_auth_user() -> dict | None:
    """Retorna el usuario autenticado o None (sin detener la página)."""
    return st.session_state.get("auth_user")


def get_uid_activo() -> int:
    """Retorna el usuario_id SQLite del usuario autenticado, o el demo si no hay sesión."""
    auth_user = st.session_state.get("auth_user")
    if auth_user:
        uid = st.session_state.get("auth_uid")
        if uid:
            return uid
        from src.db.queries import get_o_crear_usuario_por_email
        uid = get_o_crear_usuario_por_email(auth_user["email"])
        st.session_state["auth_uid"] = uid
        return uid
    from src.db.queries import get_o_crear_usuario_activo
    return get_o_crear_usuario_activo()


def auth_badge():
    """Muestra badge del usuario (nombre + email) en el sidebar con botón de logout."""
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
                _borrar_cookie()
                for k in ("auth_user", "auth_email", "auth_uid", "auth_nombre"):
                    st.session_state.pop(k, None)
                st.rerun()
