import sys
sys.stdout.reconfigure(encoding="utf-8")

import logging
from google import genai
from google.genai import types

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
    def __init__(self, memory_context: str = ""):
        self._client = genai.Client(api_key=GOOGLE_API_KEY)
        system = SYSTEM_PROMPT
        if memory_context:
            system = f"{SYSTEM_PROMPT}\n\n## Contexto de memoria\n{memory_context}"
        self._config = types.GenerateContentConfig(
            system_instruction=system,
            tools=TOOLS,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(
                disable=False
            ),
        )
        self._history: list = []

    def process_message(self, text: str) -> str:
        """Envía mensaje a Gemini, ejecuta tools automáticamente, retorna respuesta."""
        try:
            self._history.append({"role": "user", "parts": [{"text": text}]})
            response = self._client.models.generate_content(
                model=GEMINI_MODEL,
                contents=self._history,
                config=self._config,
            )
            # response.text es None cuando AFC completa una tool call sin generar
            # texto final (comportamiento de gemini-2.5-flash-lite).
            # En ese caso, pedimos explícitamente el resumen verbal.
            reply = response.text
            if not reply:
                followup = self._client.models.generate_content(
                    model=GEMINI_MODEL,
                    contents=self._history + [
                        {"role": "user", "parts": [{"text": "Resume en voz alta el resultado de la consulta anterior."}]}
                    ],
                    config=self._config,
                )
                reply = followup.text or "Consulta completada, Señor Sócrates."
            self._history.append({"role": "model", "parts": [{"text": reply}]})
            return reply
        except Exception as e:
            logger.error(f"Agent error: {e}")
            error_reply = f"Hubo un error procesando su solicitud, Senor Socrates: {e}"
            self._history.append({"role": "model", "parts": [{"text": error_reply}]})
            return error_reply
