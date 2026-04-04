"""
supabase_client.py — Cliente Supabase singleton para Hackea tu Metabolismo
Sprint S12
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import os
from dotenv import load_dotenv
load_dotenv(dotenv_path=Path(__file__).parent.parent.parent / ".env")

from supabase import create_client, Client
from src.utils.secrets import get_secret

_client: Client | None = None


def get_supabase() -> Client:
    """Retorna el cliente Supabase (singleton)."""
    global _client
    if _client is None:
        url = get_secret("SUPABASE_URL")
        key = get_secret("SUPABASE_KEY")
        if not url or not key:
            raise RuntimeError("SUPABASE_URL y SUPABASE_KEY deben estar en .env")
        _client = create_client(url, key)
    return _client


def supabase_disponible() -> bool:
    """Retorna True si las credenciales Supabase están configuradas."""
    url = get_secret("SUPABASE_URL")
    key = get_secret("SUPABASE_KEY")
    return bool(url and key and not url.endswith("supabase.co") == False
                and "rqa...." not in url)


def registrar_usuario(email: str, password: str) -> dict:
    """Registra un nuevo usuario con Supabase Auth."""
    sb = get_supabase()
    resp = sb.auth.sign_up({"email": email, "password": password})
    return {"user": resp.user, "session": resp.session}


def iniciar_sesion(email: str, password: str) -> dict:
    """Inicia sesión con Supabase Auth. Retorna {'user':..., 'session':...}."""
    sb = get_supabase()
    resp = sb.auth.sign_in_with_password({"email": email, "password": password})
    return {"user": resp.user, "session": resp.session}


def cerrar_sesion() -> None:
    """Cierra la sesión activa en Supabase."""
    sb = get_supabase()
    sb.auth.sign_out()


def usuario_activo() -> dict | None:
    """Retorna el usuario autenticado actualmente, o None."""
    try:
        sb = get_supabase()
        user = sb.auth.get_user()
        return user.user if user else None
    except Exception:
        return None


def recuperar_password(email: str) -> None:
    """Envía email de recuperación de contraseña."""
    sb = get_supabase()
    sb.auth.reset_password_email(email)
