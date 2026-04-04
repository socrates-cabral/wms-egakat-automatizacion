"""
secrets.py — Acceso unificado a credenciales
Intenta st.secrets primero (Streamlit Cloud), cae a os.getenv (local .env)
"""
import os


def get_secret(key: str, default: str = "") -> str:
    """Retorna el valor de una variable de entorno/secret.
    Prioridad: st.secrets → os.getenv → default
    """
    try:
        import streamlit as st
        val = st.secrets.get(key, None)
        if val:
            return str(val)
    except Exception:
        pass
    return os.getenv(key, default)
