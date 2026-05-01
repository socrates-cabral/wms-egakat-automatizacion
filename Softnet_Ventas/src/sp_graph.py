import sys
sys.stdout.reconfigure(encoding="utf-8")

import os
import time
import requests

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
_token_cache: dict = {"token": None, "expires_at": 0.0}
_TOKEN_BUFFER = 5 * 60


def _get_token() -> str:
    now = time.time()
    if _token_cache["token"] and (_token_cache["expires_at"] - now) > _TOKEN_BUFFER:
        return _token_cache["token"]

    tenant_id = os.getenv("Directory_(tenant)_ID")
    client_id = os.getenv("Application_(client)_ID")
    client_secret = os.getenv("Client_Secret_Value")
    assert tenant_id and client_id and client_secret, "[FALLO] Credenciales Azure faltantes en .env"

    url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    resp = requests.post(url, data={
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
        "scope": "https://graph.microsoft.com/.default",
    }, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    _token_cache["token"] = data["access_token"]
    _token_cache["expires_at"] = now + data.get("expires_in", 3600)
    return _token_cache["token"]


def _headers() -> dict:
    return {"Authorization": f"Bearer {_get_token()}"}


def get_site_id(hostname: str, site_path: str) -> str:
    url = f"{GRAPH_BASE}/sites/{hostname}:{site_path}"
    r = requests.get(url, headers=_headers(), timeout=30)
    r.raise_for_status()
    return r.json()["id"]


def get_drive_id(site_id: str, drive_name: str = "Documentos") -> str:
    url = f"{GRAPH_BASE}/sites/{site_id}/drives"
    r = requests.get(url, headers=_headers(), timeout=30)
    r.raise_for_status()
    for d in r.json()["value"]:
        if d["name"] == drive_name:
            return d["id"]
    raise ValueError(f"Drive '{drive_name}' no encontrado en site")


def descargar_archivo(drive_id: str, ruta_archivo: str, timeout: int = 60) -> bytes | None:
    """Retorna bytes del archivo o None si no existe (404).

    Args:
        drive_id: ID del drive SharePoint
        ruta_archivo: Ruta relativa del archivo
        timeout: Timeout en segundos (default 60s, configurable para archivos grandes)
    """
    url = f"{GRAPH_BASE}/drives/{drive_id}/root:/{ruta_archivo}:/content"
    r = requests.get(url, headers=_headers(), timeout=timeout)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.content


def subir_archivo(drive_id: str, ruta_archivo: str, contenido: bytes) -> dict:
    """PUT directo (archivos <4MB). Sobreescribe si existe."""
    url = f"{GRAPH_BASE}/drives/{drive_id}/root:/{ruta_archivo}:/content"
    headers = {**_headers(), "Content-Type": "application/octet-stream"}
    r = requests.put(url, headers=headers, data=contenido, timeout=120)
    r.raise_for_status()
    return r.json()


def asegurar_carpeta(drive_id: str, ruta_carpeta: str) -> None:
    """Crea carpetas anidadas si no existen. Idempotente (409 = ya existe → ignorar)."""
    partes = ruta_carpeta.strip("/").split("/")
    parent = ""
    for parte in partes:
        if parent:
            url = f"{GRAPH_BASE}/drives/{drive_id}/root:/{parent}:/children"
        else:
            url = f"{GRAPH_BASE}/drives/{drive_id}/root/children"
        body = {"name": parte, "folder": {}, "@microsoft.graph.conflictBehavior": "fail"}
        r = requests.post(
            url,
            headers={**_headers(), "Content-Type": "application/json"},
            json=body,
            timeout=30,
        )
        if r.status_code not in (201, 409):
            r.raise_for_status()
        parent = f"{parent}/{parte}" if parent else parte
