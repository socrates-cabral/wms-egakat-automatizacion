import sys
sys.stdout.reconfigure(encoding="utf-8")

from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from claude_agent import llamar_openai
from db_manager import get_historial, guardar_mensaje

SISTEMA = """Eres el asistente de Egakat SPA, empresa 3PL chilena.
Tu especialidad es información financiera y de cobranza del Libro de Ventas.

Si preguntan algo fuera de tu scope, explica amablemente qué puedes hacer:
- Consultar cartera pendiente y facturas vencidas
- Analizar comportamiento de pago de clientes
- Calcular DSO y métricas de cobranza
- Proyectar cobros de la semana

FORMATO OBLIGATORIO (Telegram HTML):
- Usa <b>texto</b> para énfasis, NO ** ni ## ni tablas Markdown
- Responde en español, máximo 150 palabras, tono profesional pero cercano."""


def responder(chat_id: int, mensaje: str, bot: str = "interno") -> str:
    historial = get_historial(chat_id, bot, n=6)
    historial.append({"role": "user", "content": mensaje})
    respuesta = llamar_openai(SISTEMA, historial, max_tokens=250)
    guardar_mensaje(chat_id, bot, "user", mensaje)
    guardar_mensaje(chat_id, bot, "assistant", respuesta)
    return respuesta
