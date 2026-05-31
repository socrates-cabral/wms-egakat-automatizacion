import sys
try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

import logging
import threading
from PyQt6.QtCore import QObject

from jarvis import voice
from jarvis.agent import Agent
from jarvis.config import HOTKEY
from jarvis.ui.bridge import JarvisBridge
from jarvis.ui.memory import MemoryClient

logger = logging.getLogger("jarvis.ui.harness")


class JarvisHarness(QObject):
    """Orquestador del ciclo STT -> Gemini -> tools -> TTS.
    Corre el ciclo en un thread separado para no bloquear el event loop de Qt.
    """

    def __init__(self, bridge: JarvisBridge):
        super().__init__()
        self._bridge = bridge
        self._memory = MemoryClient()
        self._agent: Agent | None = None
        self._active = False
        self._lock = threading.Lock()

    def start(self) -> None:
        """Inicializa el agente con contexto de memoria. Llamar una vez al arrancar."""
        context = self._memory.load_context()
        self._agent = Agent(memory_context=context)
        logger.info("Harness inicializado. Contexto de memoria cargado.")

    def trigger(self) -> None:
        """Lanza un ciclo STT -> agente -> TTS en un thread separado."""
        with self._lock:
            if self._active:
                return
            self._active = True
        t = threading.Thread(target=self._cycle, daemon=True)
        t.start()

    def _cycle(self) -> None:
        try:
            if self._agent is None:
                voice.speak("Aun me estoy inicializando.")
                self._bridge.speaking_done.emit()
                return
            self._bridge.listening_started.emit()
            text = voice.listen()
            if not text:
                voice.speak("No escuche nada, Senor Socrates.")
                self._bridge.speaking_done.emit()
                return

            self._bridge.processing_started.emit()
            response = self._agent.process_message(text)

            self._bridge.response_ready.emit(response)
            voice.speak(response)
            self._bridge.speaking_done.emit()

            if any(w in text.lower() for w in ("hasta luego", "apagate", "cierra")):
                from PyQt6.QtCore import QTimer
                from PyQt6.QtWidgets import QApplication
                QTimer.singleShot(0, QApplication.quit)
        except Exception as e:
            logger.error(f"Cycle error: {e}")
            voice.speak("Error inesperado.")
            self._bridge.speaking_done.emit()
        finally:
            with self._lock:
                self._active = False
