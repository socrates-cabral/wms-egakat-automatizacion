import sys
sys.stdout.reconfigure(encoding="utf-8")

import logging
import google.generativeai as genai

from jarvis.config import GOOGLE_API_KEY, GEMINI_MODEL, SYSTEM_PROMPT
from jarvis.tools import (
    get_estado_sistema, get_wms_kpi, get_apuestas,
    abrir_aplicacion, set_timer, tomar_nota, invoke_claude,
)

logger = logging.getLogger("jarvis.agent")

TOOLS = [
    get_estado_sistema,
    get_wms_kpi,
    get_apuestas,
    abrir_aplicacion,
    set_timer,
    tomar_nota,
    invoke_claude,
]


class Agent:
    def __init__(self):
        genai.configure(api_key=GOOGLE_API_KEY)
        self._model = genai.GenerativeModel(
            model_name=GEMINI_MODEL,
            tools=TOOLS,
            system_instruction=SYSTEM_PROMPT,
        )
        self._chat = self._model.start_chat(
            enable_automatic_function_calling=True
        )

    def process_message(self, text: str) -> str:
        """Envía mensaje a Gemini, ejecuta tools automáticamente, retorna respuesta."""
        try:
            response = self._chat.send_message(text)
            return response.text
        except Exception as e:
            logger.error(f"Agent error: {e}")
            return f"Hubo un error procesando su solicitud, Señor Sócrates: {e}"
