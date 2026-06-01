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

_SHUTDOWN_WORDS = ("hasta luego", "apagate", "apaga", "cierra", "adios")


class JarvisHarness(QObject):
    """Orquesta el ciclo Wake/Win+J → STT → Gemini → TTS sobre un mic compartido.

    El AudioHub es el único dueño del micrófono. Este harness solo aporta el
    'cerebro': STT del comando, Gemini y TTS. No abre streams de audio.
    """

    def __init__(self, bridge: JarvisBridge):
        super().__init__()
        self._bridge = bridge
        self._memory = MemoryClient()
        self._agent: Agent | None = None
        self._hub = None
        self._processing = False

    def start(self) -> None:
        """Inicializa agente, restaura timers y arranca el mic compartido."""
        context = self._memory.load_context()
        self._agent = Agent(memory_context=context)
        self._bridge.tts_cancel_requested.connect(voice.cancel_tts)

        from jarvis.tools import restore_timers
        for msg in restore_timers():
            logger.info("Timer restaurado: %s", msg)

        from jarvis.audio_hub import AudioHub
        from jarvis.config import WAKE_WORD_PHRASES, WAKE_WORD_COOLDOWN
        self._hub = AudioHub(
            on_listening=self._on_listening,
            on_command=self._on_command,
            wake_phrases=tuple(WAKE_WORD_PHRASES),
            cooldown=WAKE_WORD_COOLDOWN,
        )
        if not self._hub.start():
            logger.warning("AudioHub no arrancó — micrófono no disponible.")

        logger.info("Harness inicializado. Contexto de memoria cargado.")

    # ── Control del micrófono (para el saludo inicial) ───────────────────

    def mute_mic(self) -> None:
        if self._hub is not None:
            self._hub.mute()

    def unmute_mic(self) -> None:
        if self._hub is not None:
            self._hub.unmute()

    def stop_audio(self) -> None:
        """Detiene el hub. Llamar en app.aboutToQuit."""
        if self._hub is not None:
            self._hub.stop()
            logger.info("AudioHub detenido.")

    # ── Triggers ─────────────────────────────────────────────────────────

    def trigger(self) -> None:
        """Win+J: si Jarvis está hablando, interrumpe; si no, captura comando."""
        if self._processing:
            voice.cancel_tts()
            return
        if self._hub is not None:
            self._hub.trigger_command(source="hotkey")

    # ── Callbacks del hub ────────────────────────────────────────────────
    # _on_listening corre en el processor; _on_command en el command worker.

    def _on_listening(self) -> None:
        self._bridge.listening_started.emit()

    def _on_command(self, pcm: bytes, source: str) -> None:
        self._processing = True
        try:
            if self._agent is None:
                voice.speak("Aun me estoy inicializando.")
                self._bridge.speaking_done.emit()
                return

            if not pcm:
                # wake word: falso positivo probable → silencio; Win+J: avisar
                if source == "hotkey":
                    voice.speak("No escuche nada, Senor Socrates.")
                self._bridge.speaking_done.emit()
                return

            from jarvis import stt
            text = stt.transcribe(pcm, samplerate=16000)
            if not text:
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
            normalized = "".join(c for c in normalized
                                 if unicodedata.category(c) != "Mn")
            if any(w in normalized for w in _SHUTDOWN_WORDS):
                from PyQt6.QtCore import QTimer
                from PyQt6.QtWidgets import QApplication
                QTimer.singleShot(500, QApplication.quit)

        except Exception as e:
            logger.error(f"Command error: {e}")
            voice.speak("Error inesperado.")
            self._bridge.speaking_done.emit()
        finally:
            self._processing = False
