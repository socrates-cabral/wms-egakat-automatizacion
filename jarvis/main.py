import sys
sys.stdout.reconfigure(encoding="utf-8")

import logging
import keyboard
from datetime import datetime
from zoneinfo import ZoneInfo

from jarvis.config import HOTKEY
from jarvis import voice
from jarvis.agent import Agent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("jarvis")

CL_TZ = ZoneInfo("America/Santiago")
_agent = None
_listening = False


def _saludo_inicial() -> str:
    from jarvis.tools import get_estado_sistema
    estado = get_estado_sistema()
    hora = datetime.now(CL_TZ).strftime("%H:%M")
    clima = estado.get("clima_santiago", "")
    clima_str = f", {clima}" if clima and clima != "sin datos" else ""
    return (
        f"Sistemas en línea. Son las {hora} en Santiago{clima_str}. "
        f"A sus órdenes, Señor Sócrates."
    )


def _on_hotkey():
    global _listening
    if _listening:
        return
    _listening = True
    try:
        text = voice.listen()
        if not text:
            voice.speak("No escuché nada, Señor Sócrates.")
            return
        print(f"\nSeñor Sócrates: {text}")
        response = _agent.process_message(text)
        print(f"JARVIS: {response}\n")
        voice.speak(response)
        if any(w in text.lower() for w in ("hasta luego", "apágate", "cierra")):
            voice.speak("Hasta luego, Señor Sócrates. Sistemas en espera.")
            raise SystemExit(0)
    except SystemExit:
        raise
    except Exception as e:
        logger.error(f"Ciclo error: {e}")
        voice.speak("Error inesperado, Señor Sócrates.")
    finally:
        _listening = False


def main():
    global _agent
    print("=" * 50)
    print("  J.A.R.V.I.S. — Iniciando...")
    print(f"  Hotkey: {HOTKEY.upper()}")
    print("  ESC para salir")
    print("=" * 50)

    voice.play_startup()
    _agent = Agent()

    saludo = _saludo_inicial()
    print(f"\nJARVIS: {saludo}\n")
    voice.speak(saludo)

    keyboard.add_hotkey(HOTKEY, _on_hotkey)
    print(f"En espera. Presiona {HOTKEY.upper()} para hablar.\n")
    keyboard.wait("esc")
    print("JARVIS: Cerrando sistemas.")


if __name__ == "__main__":
    main()
