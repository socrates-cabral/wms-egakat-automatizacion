"""
azure_graph.py — Helper Microsoft Graph API para WMS Egakat
Autor: Claude Code 2026-03-18

Permisos requeridos en la App Registration (application permissions + admin consent):
  - Mail.Send          → enviar correo
  - Sites.ReadWrite.All → subir archivos a SharePoint
"""

import sys
if sys.stdout:
    sys.stdout.reconfigure(encoding="utf-8")

import os
import time
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

CLIENT_ID     = os.getenv("Application_(client)_ID")
TENANT_ID     = os.getenv("Directory_(tenant)_ID")
CLIENT_SECRET = os.getenv("Client_Secret_Value")
GRAPH_BASE    = "https://graph.microsoft.com/v1.0"

SP_HOST      = "egakatcom.sharepoint.com"
SP_SITE_PATH = "/sites/DatosparaDashboard"
DOC_LIBRARY  = "Documentos"


# ─── AUTH ─────────────────────────────────────────────────────────────────────

_token_cache: dict = {"token": None, "expires_at": 0.0}
_TOKEN_REFRESH_BUFFER = 5 * 60  # refrescar 5 min antes de expirar (patrón spec/09 Bridge)

def get_token(scope: str = "https://graph.microsoft.com/.default") -> str:
    """Obtiene access token via OAuth2 client_credentials.
    Cache en memoria: reutiliza el token mientras queden >5 min de vida.
    Evita llamadas redundantes y detecta expiración antes de que falle mid-run."""
    now = time.time()
    if _token_cache["token"] and (_token_cache["expires_at"] - now) > _TOKEN_REFRESH_BUFFER:
        return _token_cache["token"]

    url  = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"
    resp = requests.post(url, data={
        "grant_type":    "client_credentials",
        "client_id":     CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "scope":         scope,
    }, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    _token_cache["token"]      = data["access_token"]
    _token_cache["expires_at"] = now + data.get("expires_in", 3600)
    return _token_cache["token"]


def _gh(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


# ─── EMAIL ────────────────────────────────────────────────────────────────────

def enviar_email(
    from_email: str,
    to_email: str,
    asunto: str,
    html_body: str,
    cc_emails: list | None = None,
    extra_to_emails: list | None = None,
) -> bool:
    """
    Envía correo HTML via Graph API en nombre de from_email.
    - to_email: destinatario principal (requerido para compatibilidad)
    - extra_to_emails: destinatarios TO adicionales
    - cc_emails: destinatarios en CC
    Requiere permiso Mail.Send (application) con admin consent.
    """
    try:
        token = get_token()
        all_to = [to_email] + (extra_to_emails or [])
        to_recipients = [{"emailAddress": {"address": e}} for e in all_to if e]
        message: dict = {
            "subject": asunto,
            "body": {"contentType": "HTML", "content": html_body},
            "toRecipients": to_recipients,
        }
        if cc_emails:
            message["ccRecipients"] = [{"emailAddress": {"address": e}} for e in cc_emails if e]
        resp = requests.post(
            f"{GRAPH_BASE}/users/{from_email}/sendMail",
            json={"message": message, "saveToSentItems": True},
            headers=_gh(token),
            timeout=30,
        )
        resp.raise_for_status()
        return True
    except Exception as e:
        print(f"[azure_graph] enviar_email error: {e}")
        return False


# ─── SHAREPOINT ───────────────────────────────────────────────────────────────

def get_drive_id(token: str) -> str:
    """
    Retorna el drive_id de la biblioteca 'Documentos compartidos' en el site.
    Requiere permiso Sites.ReadWrite.All.
    """
    # 1. Obtener site ID
    site_resp = requests.get(
        f"{GRAPH_BASE}/sites/{SP_HOST}:{SP_SITE_PATH}",
        headers=_gh(token), timeout=15,
    )
    site_resp.raise_for_status()
    site_id = site_resp.json()["id"]

    # 2. Buscar la biblioteca por nombre
    drives_resp = requests.get(
        f"{GRAPH_BASE}/sites/{site_id}/drives",
        headers=_gh(token), timeout=15,
    )
    drives_resp.raise_for_status()
    for drive in drives_resp.json().get("value", []):
        if drive["name"] == DOC_LIBRARY:
            return drive["id"]
    raise ValueError(f"No se encontró la biblioteca '{DOC_LIBRARY}' en {SP_SITE_PATH}")


def listar_archivos_sp(token: str, drive_id: str, folder_path: str) -> set:
    """
    Lista nombres de archivos en una carpeta del drive.
    folder_path: ruta relativa a la raíz de la biblioteca (ej: 'Clientes EK/ABINBEV/Inventario/2026/03 Marzo')
    Retorna set vacío si la carpeta no existe.
    """
    resp = requests.get(
        f"{GRAPH_BASE}/drives/{drive_id}/root:/{folder_path}:/children",
        headers=_gh(token), timeout=30,
    )
    if resp.status_code == 404:
        return set()
    resp.raise_for_status()
    return {item["name"] for item in resp.json().get("value", []) if "file" in item}


def subir_archivo_sp(token: str, drive_id: str, folder_path: str, ruta_local: Path) -> bool:
    """
    Sube un archivo al drive de SharePoint (PUT — hasta ~4 MB, suficiente para CSVs staging).
    folder_path: ruta relativa dentro de la biblioteca (sin barra inicial).
    Retorna True si OK.
    """
    nombre = ruta_local.name
    url    = f"{GRAPH_BASE}/drives/{drive_id}/root:/{folder_path}/{nombre}:/content"
    with open(ruta_local, "rb") as f:
        data = f.read()
    resp = requests.put(url, data=data, headers={
        "Authorization": f"Bearer {token}",
        "Content-Type":  "application/octet-stream",
    }, timeout=120)
    return resp.status_code in (200, 201)


# ─── TEST ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    email = os.getenv("SHAREPOINT_USER", "")
    print("=" * 50)
    print("TEST 1 — Token Graph API")
    try:
        t = get_token()
        print(f"  [OK] Token obtenido ({len(t)} chars)")
    except Exception as e:
        print(f"  [FALLO] {e}")
        raise SystemExit(1)

    print("\nTEST 2 — SharePoint drive ID")
    try:
        drive_id = get_drive_id(t)
        print(f"  [OK] Drive ID: {drive_id[:20]}...")
    except Exception as e:
        print(f"  [FALLO] {e} (verificar permiso Sites.ReadWrite.All)")
        drive_id = None

    print("\nTEST 3 — Email via Graph API")
    ok = enviar_email(
        from_email=email,
        to_email=email,
        asunto="[Test] WMS Egakat - Graph API OK",
        html_body="<h2>Test exitoso</h2><p>Graph API autenticada correctamente.</p>",
    )
    print(f"  {'[OK] Correo enviado.' if ok else '[FALLO] Verificar permiso Mail.Send con Jose C.'}")
    print("=" * 50)
