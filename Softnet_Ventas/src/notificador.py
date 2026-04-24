import sys
sys.stdout.reconfigure(encoding="utf-8")

import os
import time
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from plantilla_correo import build_html, build_asunto

_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_ROOT / "WMS_Automatizacion"))
try:
    from azure_graph import enviar_email as _graph_email
    _HAS_GRAPH = True
except ImportError:
    _HAS_GRAPH = False
finally:
    sys.path.pop(0)


def enviar_resumen_diario(resumen: dict, destinatarios: list[str], cc: list[str] | None = None) -> bool:
    modo_test = os.getenv("MODO_TEST", "true").strip().lower() == "true"
    cc_efectivo = [] if modo_test else (cc or [])
    if modo_test:
        print("[notificador] MODO_TEST=true — correo solo a destinatario principal, sin CC")

    asunto = build_asunto(resumen)
    html   = build_html(resumen)
    from_email = os.getenv("SHAREPOINT_USER", "")
    ok = False
    if _HAS_GRAPH and from_email and destinatarios:
        for intento in range(2):
            try:
                ok = _graph_email(
                    from_email=from_email,
                    to_email=destinatarios[0],
                    asunto=asunto,
                    html_body=html,
                    extra_to_emails=destinatarios[1:],
                    cc_emails=cc_efectivo,
                )
                if ok:
                    break
            except Exception as e:
                if intento == 0:
                    print(f"[notificador] Graph API fallo (intento 1): {e} — reintentando en 30s")
                    time.sleep(30)
                else:
                    print(f"[notificador] Graph API fallo (intento 2): {e} — cayendo a SMTP")
    if not ok:
        ok = _enviar_smtp(from_email, destinatarios, cc_efectivo, asunto, html)
    return ok


def _enviar_smtp(from_email: str, to: list[str], cc: list[str], asunto: str, html: str) -> bool:
    password = os.getenv("SHAREPOINT_PASSWORD", "")
    if not from_email or not password or not to:
        print("[notificador] Sin credenciales SMTP o sin destinatarios — correo no enviado")
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = asunto
        msg["From"] = from_email
        msg["To"] = ", ".join(to)
        if cc:
            msg["Cc"] = ", ".join(cc)
        msg.attach(MIMEText(html, "html", "utf-8"))
        todos = to + cc
        with smtplib.SMTP("smtp.office365.com", 587) as server:
            server.starttls()
            server.login(from_email, password)
            server.sendmail(from_email, todos, msg.as_string())
        return True
    except Exception as e:
        print(f"[FALLO] SMTP: {e}")
        return False
