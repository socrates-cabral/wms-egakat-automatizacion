"""
secure_ai_agent.py
Agente local seguro para consultas puntuales a Claude API.
Filtra datos sensibles y limita contexto antes de enviar.
Uso: py otros_proyectos/secure_ai_agent.py
"""
import sys
sys.stdout.reconfigure(encoding="utf-8")

import os
from pathlib import Path
from dotenv import load_dotenv
from anthropic import Anthropic

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))

# Palabras que NUNCA deben enviarse a la API
SENSIBLES = [
    "password", "passwd", "secret", "api_key", "token",
    "WMS_PASSWORD", "SHAREPOINT_PASSWORD", "CORREO_PASSWORD",
    "LIMESURVEY_PASSWORD", "client_secret",
]

MAX_CONTEXT  = 3000   # caracteres maximos de contexto
MAX_TOKENS   = 1024   # tokens maximos de respuesta
MODEL        = "claude-sonnet-4-6"


def sanitizar(texto: str) -> str:
    """Reemplaza datos sensibles antes de enviar."""
    texto_lower = texto.lower()
    for palabra in SENSIBLES:
        if palabra.lower() in texto_lower:
            return "[CONTEXTO REDACTADO — contiene datos sensibles]"
    return texto


def leer_archivo(ruta: str) -> str:
    """Lee un archivo local y limita a MAX_CONTEXT caracteres."""
    try:
        contenido = Path(ruta).read_text(encoding="utf-8", errors="ignore")
        if len(contenido) > MAX_CONTEXT:
            contenido = contenido[:MAX_CONTEXT] + f"\n... [truncado a {MAX_CONTEXT} chars]"
        return contenido
    except Exception as e:
        return f"[Error leyendo archivo: {e}]"


def preguntar(pregunta: str, contexto: str = "") -> str:
    """Envia pregunta a Claude con contexto filtrado y limitado."""
    if not client.api_key:
        return "ERROR: ANTHROPIC_API_KEY no esta en .env"

    contexto_seguro = sanitizar(contexto)

    prompt = f"Contexto:\n{contexto_seguro}\n\nPregunta:\n{pregunta}" if contexto_seguro else pregunta

    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text


# ── Modo interactivo ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"Agente seguro Egakat — modelo: {MODEL} | max_tokens: {MAX_TOKENS} | max_context: {MAX_CONTEXT} chars")
    print("Escribe 'archivo:<ruta>' para incluir contexto de un archivo.")
    print("Escribe 'salir' para terminar.\n")

    while True:
        entrada = input("Pregunta: ").strip()
        if entrada.lower() in ("salir", "exit", "q"):
            break
        if not entrada:
            continue

        contexto = ""
        if entrada.startswith("archivo:"):
            partes  = entrada.split(" ", 1)
            ruta    = partes[0].replace("archivo:", "")
            entrada = partes[1] if len(partes) > 1 else "¿Qué hace este código?"
            contexto = leer_archivo(ruta)
            print(f"[Contexto cargado: {len(contexto)} chars]")

        respuesta = preguntar(entrada, contexto)
        print(f"\nClaude: {respuesta}\n")
