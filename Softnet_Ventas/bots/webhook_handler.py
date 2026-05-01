"""
Recibe payload de n8n y retorna respuesta del agente correspondiente.
Llamada desde n8n via Execute Command node:
  py C:\\ClaudeWork\\Softnet_Ventas\\bots\\webhook_handler.py CHAT_ID "mensaje" bot_type
"""
import sys
sys.stdout.reconfigure(encoding="utf-8")

from pathlib import Path
from dotenv import load_dotenv

_BASE = Path(__file__).resolve().parent.parent
load_dotenv(_BASE / ".env")
load_dotenv(_BASE.parent / ".env")

sys.path.insert(0, str(Path(__file__).resolve().parent))
from agents.orquestador import clasificar
from agents.agente_cobranza import responder as cobranza_responder
from agents.agente_general import responder as general_responder
from telegram_utils import enviar_grupo_interno, enviar_cliente


VALID_BOT_TYPES = {"interno", "cliente"}


def procesar_mensaje(chat_id: int, mensaje: str,
                     bot_type: str = "interno",
                     es_grupo: bool = True) -> str:
    """
    Punto de entrada principal.
    bot_type: 'interno' | 'cliente'
    """
    # Validación bot_type
    if bot_type not in VALID_BOT_TYPES:
        raise ValueError(f"bot_type inválido: '{bot_type}' (permitidos: {VALID_BOT_TYPES})")

    bot_username = "EgakatIntelBot"
    mensaje_limpio = mensaje.replace(f"@{bot_username}", "").strip()
    if not mensaje_limpio:
        return "¿En qué puedo ayudarte? Puedo consultar cartera, facturas vencidas o pagos."

    intencion = clasificar(mensaje_limpio)
    print(f"[INFO] chat_id={chat_id} | intención={intencion} | msg={mensaje_limpio[:60]}")

    if intencion in ("COBRANZA", "ALERTAS", "PROYECCION"):
        respuesta = cobranza_responder(chat_id, mensaje_limpio, bot=bot_type)
    else:
        respuesta = general_responder(chat_id, mensaje_limpio, bot=bot_type)

    if bot_type == "interno" and es_grupo:
        enviar_grupo_interno(respuesta)
    elif bot_type == "cliente":
        enviar_cliente(chat_id, respuesta)

    return respuesta


if __name__ == "__main__":
    if len(sys.argv) >= 3:
        chat_id = int(sys.argv[1])
        mensaje = sys.argv[2]
        bot_type = sys.argv[3] if len(sys.argv) > 3 else "interno"
        resultado = procesar_mensaje(chat_id, mensaje, bot_type)
        print("\n--- RESPUESTA ---")
        print(resultado)
    else:
        print("Uso: py webhook_handler.py CHAT_ID 'mensaje' [bot_type]")
        sys.exit(1)
