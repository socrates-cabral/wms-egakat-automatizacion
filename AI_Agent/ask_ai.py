"""
ask_ai.py — Agente local seguro Egakat
Uso:
    py AI_Agent/ask_ai.py "pregunta libre"
    py AI_Agent/ask_ai.py /explain wms_descarga.py
    py AI_Agent/ask_ai.py /fix staging_descarga.py
    py AI_Agent/ask_ai.py /test posiciones_descarga.py
    py AI_Agent/ask_ai.py /refactor run_todos.py
"""
import sys
sys.stdout.reconfigure(encoding="utf-8")

import os
import re
from pathlib import Path
from dotenv import load_dotenv
from anthropic import Anthropic

# ── Config ────────────────────────────────────────────────────────────────────
BASE_DIR    = Path(__file__).parent.parent
load_dotenv(dotenv_path=BASE_DIR / ".env")

client      = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))
MODEL       = "claude-sonnet-4-6"
MAX_TOKENS  = 1500
MAX_CONTEXT = 4000   # chars por archivo

# ── Patrones sensibles (regex) ────────────────────────────────────────────────
PATRON_SENSIBLE = re.compile(
    r'(password|passwd|secret|api_key|token|client_secret|private_key'
    r'|WMS_PASSWORD|SHAREPOINT_PASSWORD|CORREO_PASSWORD|LIMESURVEY_PASSWORD'
    r')\s*[=:]\s*\S+',
    re.IGNORECASE
)

# ── Prompts por comando ───────────────────────────────────────────────────────
PROMPTS = {
    "/explain":  "Explica qué hace este código en español, de forma concisa. Señala las partes clave.",
    "/fix":      "Identifica bugs, errores o mejoras críticas en este código. Sé específico y proporciona el fix.",
    "/test":     "Genera tests unitarios básicos en Python (pytest) para las funciones principales de este código.",
    "/refactor": "Sugiere refactorizaciones concretas para mejorar legibilidad y mantenibilidad. Muestra el código mejorado.",
}

# ── Funciones ─────────────────────────────────────────────────────────────────
def sanitizar(texto: str) -> str:
    """Reemplaza valores sensibles por [REDACTED] manteniendo el resto del código."""
    return PATRON_SENSIBLE.sub(lambda m: m.group(1) + "=[REDACTED]", texto)


def buscar_archivo(nombre: str) -> Path | None:
    """Busca el archivo en todo C:\\ClaudeWork recursivamente."""
    for p in BASE_DIR.rglob(nombre):
        return p
    return None


def leer_archivo(nombre: str) -> tuple[str, str]:
    """Retorna (contenido_sanitizado, ruta_encontrada)."""
    # Ruta directa
    ruta = Path(nombre)
    if not ruta.exists():
        ruta = BASE_DIR / nombre
    if not ruta.exists():
        ruta = buscar_archivo(Path(nombre).name)

    if ruta is None or not ruta.exists():
        return f"[Archivo no encontrado: {nombre}]", nombre

    contenido = ruta.read_text(encoding="utf-8", errors="ignore")

    if len(contenido) > MAX_CONTEXT:
        contenido = contenido[:MAX_CONTEXT] + f"\n\n... [truncado — {len(contenido)} chars totales]"

    return sanitizar(contenido), str(ruta)


def enviar(system_prompt: str, user_content: str) -> str:
    """Envía a Claude y retorna respuesta."""
    if not client.api_key:
        return "ERROR: ANTHROPIC_API_KEY no está en .env"

    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=system_prompt,
        messages=[{"role": "user", "content": user_content}]
    )
    return response.content[0].text


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    args = sys.argv[1:]

    if not args:
        print("Uso: py AI_Agent/ask_ai.py \"pregunta\" | /explain archivo.py | /fix | /test | /refactor")
        sys.exit(0)

    comando = args[0].lower()

    # ── Slash commands ────────────────────────────────────────────────────────
    if comando in PROMPTS:
        if len(args) < 2:
            print(f"Uso: py AI_Agent/ask_ai.py {comando} <archivo.py>")
            sys.exit(1)

        archivo = args[1]
        contexto, ruta = leer_archivo(archivo)

        print(f"[Archivo: {ruta}]")
        print(f"[Contexto: {len(contexto)} chars enviados]\n")

        respuesta = enviar(
            system_prompt="Eres un asistente experto en Python. Responde en español de forma clara y directa.",
            user_content=f"{PROMPTS[comando]}\n\nCódigo:\n```python\n{contexto}\n```"
        )
        print(respuesta)

    # ── Pregunta libre con archivo opcional ───────────────────────────────────
    elif comando.endswith(".py") or (len(args) > 1 and args[-1].endswith(".py")):
        # ask_ai.py pregunta archivo.py  o  ask_ai.py archivo.py pregunta
        if args[0].endswith(".py"):
            archivo   = args[0]
            pregunta  = " ".join(args[1:]) if len(args) > 1 else "¿Qué hace este código?"
        else:
            pregunta  = " ".join(args[:-1])
            archivo   = args[-1]

        contexto, ruta = leer_archivo(archivo)
        print(f"[Archivo: {ruta}]")
        print(f"[Contexto: {len(contexto)} chars enviados]\n")

        respuesta = enviar(
            system_prompt="Eres un asistente experto en Python. Responde en español de forma clara y directa.",
            user_content=f"Código:\n```python\n{contexto}\n```\n\nPregunta: {pregunta}"
        )
        print(respuesta)

    # ── Pregunta libre ────────────────────────────────────────────────────────
    else:
        pregunta = " ".join(args)
        print(f"[Pregunta directa — sin archivo]\n")
        respuesta = enviar(
            system_prompt="Eres un asistente experto en Python y automatización. Responde en español de forma clara y directa.",
            user_content=pregunta
        )
        print(respuesta)


if __name__ == "__main__":
    main()
