import sys
sys.stdout.reconfigure(encoding="utf-8")

"""
Sincronizacion bidireccional con Supabase.
El bot escribe despues de cada ciclo; el dashboard lee desde la nube.
Falla silenciosamente para no interrumpir el bot si hay problemas de red.
"""

from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

from dotenv import load_dotenv
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

import os

_client = None


def _get_client():
    global _client
    if _client:
        return _client
    url = os.getenv("SUPABASE_URL", "")
    # Proceso backend: service role bypasea RLS correctamente
    # Fallback a anon key si service role no está configurado
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "") or os.getenv("SUPABASE_KEY", "")
    if not url or not key:
        return None
    from supabase import create_client
    _client = create_client(url, key)
    return _client


def push_estado(estado: dict) -> bool:
    """Upsert del estado grid completo. Retorna True si OK."""
    client = _get_client()
    if not client:
        return False
    try:
        client.table("crypto_grid_state").upsert({
            "par":        estado["par"],
            "estado":     estado,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).execute()
        return True
    except Exception:
        return False


def push_operacion(op: dict, par: str) -> bool:
    """Inserta una operacion en historial. Retorna True si OK."""
    client = _get_client()
    if not client:
        return False
    try:
        client.table("crypto_operaciones").upsert({
            "par":       par,
            "tipo":      op["tipo"],
            "precio":    op["precio"],
            "qty":       op["qty"],
            "pnl":       op.get("pnl"),
            "order_id":  op.get("order_id"),
            "timestamp": op.get("timestamp", datetime.now(timezone.utc).isoformat()),
        }, on_conflict="order_id").execute()
        return True
    except Exception:
        return False


def fetch_estado(par: str) -> Optional[dict]:
    """Lee estado grid desde Supabase. Retorna None si falla."""
    client = _get_client()
    if not client:
        return None
    try:
        resp = client.table("crypto_grid_state").select("estado").eq("par", par).single().execute()
        return resp.data["estado"] if resp.data else None
    except Exception:
        return None


def fetch_operaciones(par: str, limit: int = 100) -> list[dict]:
    """Lee historial de operaciones desde Supabase."""
    client = _get_client()
    if not client:
        return []
    try:
        resp = (
            client.table("crypto_operaciones")
            .select("tipo, precio, qty, pnl, order_id, timestamp")
            .eq("par", par)
            .order("timestamp", desc=True)
            .limit(limit)
            .execute()
        )
        return resp.data or []
    except Exception:
        return []


def is_available() -> bool:
    return _get_client() is not None
