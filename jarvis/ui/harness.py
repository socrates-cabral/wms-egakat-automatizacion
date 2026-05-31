import sys
try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

import logging
import threading
import unicodedata
from PyQt6.QtCore import QObject

from jarvis import voice
from jarvis.agent import Agent
from jarvis.config import HOTKEY
from jarvis.ui.bridge import JarvisBridge
from jarvis.ui.memory import MemoryClient

logger = logging.getLogger("jarvis.ui.harness")


class JarvisHarness(QObject):
    """Orquestador del ciclo STT -> Gemini -> tools -> TTS."""

    def __init__(self, bridge: JarvisBridge):
        super().__init__()
        self._bridge = bridge
        self._memory = MemoryClient()
        self._agent: Agent | None = None
        self._active = False
        self._lock   = threading.Lock()

    def start(self) -> None:
        """Inicializa agente, restaura timers, arranca wake word."""
        context = self._memory.load_context()
        self._agent = Agent(memory_context=context)
        self._bridge.tts_cancel_requested.connect(voice.cancel_tts)

        from jarvis.tools import restore_timers
        for msg in restore_timers():
            logger.info("Timer restaurado: %s", msg)

        from jarvis.wakeword import WakeWordDetector
        from jarvis.config import WAKE_WORD_MODEL, WAKE_WORD_SENSITIVITY, WAKE_WORD_COOLDOWN
        # Bug 7: callback usa trigger_wakeword (silencioso si no hay habla)
        self._wakeword = WakeWordDetector(callback=self.trigger_wakeword)
        ok = self._wakeword.start(WAKE_WORD_MODEL, WAKE_WORD_SENSITIVITY, WAKE_WORD_COOLDOWN)
        if not ok:
            logger.warning("Wake word desactivado — solo Win+J disponible.")

        logger.info("Harness inicializado. Contexto de memoria cargado.")

    def stop_wakeword(self) -> None:
        """Detiene el wake word detector. Llamar en app.aboutToQuit."""
        if hasattr(self, "_wakeword"):
            self._wakeword.stop()
            logger.info("Wake word detector detenido.")

    # ── Triggers ───────────────────────────────────────────────────────────

    def trigger(self) -> None:
        """Activa ciclo desde Win+J — habla si no escucha nada."""
        self._trigger_impl(source="hotkey")

    def trigger_wakeword(self) -> None:
        """Activa ciclo desde wake word — silencioso si no hay habla (Bug 7)."""
        self._trigger_impl(source="wakeword")

    def _trigger_impl(self, source: str) -> None:
        with self._lock:
            if self._active:
                voice.cancel_tts()
                return
            self._active = True
        t = threading.Thread(target=self._cycle, args=(source,), daemon=True)
        t.start()

    # ── Ciclo STT → Gemini → TTS ───────────────────────────────────────────

    def _cycle(self, source: str = "hotkey") -> None:
        # Bug 2 + 11: pausar wake word para ceder el mic y evitar auto-trigger
        ww = getattr(self, "_wakeword", None)
        if ww:
            ww.pause()
        try:
            if self._agent is None:
                voice.speak("Aun me estoy inicializando.")
                self._bridge.speaking_done.emit()
                return

            self._bridge.listening_started.emit()
            text = voice.listen()

            if not text:
                # Bug 7: Win+J → avisa; wake word → silencio (falso positivo probable)
                if source == "hotkey":
                    voice.speak("No escuche nada, Senor Socrates.")
                self._bridge.speaking_done.emit()
                return

            self._bridge.processing_started.emit()
            response = self._agent.process_message(text)

            self._bridge.response_ready.emit(response)
            voice.speak(response)
            self._bridge.speaking_done.emit()

            normalized = unicodedata.normalize("NFD", text.lower())
            normalized = "".join(c for c in normalized if unicodedata.category(c) != "Mn")
            if any(w in normalized for w in ("hasta luego", "apagate", "cierra", "apaga")):
                from PyQt6.QtCore import QTimer
                from PyQt6.QtWidgets import QApplication
                QTimer.singleShot(500, QApplication.quit)

        except Exception as e:
            logger.error(f"Cycle error: {e}")
            voice.speak("Error inesperado.")
            self._bridge.speaking_done.emit()
        finally:
            if ww:
                ww.resume()   # devolver el mic al wake word
            with self._lock:
                self._active = False
