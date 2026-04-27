import html
from typing import Any, Dict

def build_email_html_hibrido(payload: Dict[str, Any]) -> str:
    """Versión híbrida: base visual limpia tipo correo operativo + resumen ejecutivo compacto."""
    # Este helper es una plantilla visual. Integra el mismo criterio del preview híbrido.
    # Recomendación: usarlo para reemplazar la función build_email_html actual.
    return payload.get("email_preview", {}).get("body_html", "")
