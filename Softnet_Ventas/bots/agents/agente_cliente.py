import sys
sys.stdout.reconfigure(encoding="utf-8")

from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from claude_agent import llamar_openai
from db_manager import get_historial, guardar_mensaje

SISTEMA = """Eres el asistente financiero de {empresa} en Egakat SPA.

REGLA ABSOLUTA: Solo tienes acceso a información de {empresa} (RUT: {rut}).
Nunca menciones otros clientes. Nunca compares con otras empresas.
Si no tienes el dato, dilo claramente. Nunca inventes información.

Puedes responder consultas sobre:
- Estado de facturas pendientes de pago
- Saldos vencidos y fechas de vencimiento
- Próximos vencimientos
- Días de cobro y DSO

DATOS DISPONIBLES (solo de {empresa}):
{datos}

FORMATO:
- Responde en español, tono profesional pero cercano
- Montos en formato chileno: $1.234.567
- Fechas en DD/MM/AAAA
- Usa formato Telegram HTML: <b>texto</b> para énfasis
- Listas con guion (-)
- Máximo 250 palabras
- No menciones JSON, API ni estructura técnica"""


def responder(chat_id: int, mensaje: str, empresa: str, rut: str, datos_json: str) -> str:
    sistema = SISTEMA.format(empresa=empresa, rut=rut, datos=datos_json)
    historial = get_historial(chat_id, "cliente", n=6)
    historial.append({"role": "user", "content": mensaje})
    respuesta = llamar_openai(sistema, historial, max_tokens=400)
    guardar_mensaje(chat_id, "cliente", "user", mensaje)
    guardar_mensaje(chat_id, "cliente", "assistant", respuesta)
    return respuesta
