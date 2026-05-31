"""Wake word detector usando OpenWakeWord (sin cuenta, sin API key, 100% local).

Modelo por defecto: 'hey_jarvis' (bundled en openwakeword + onnxruntime).
Requiere: pip install openwakeword onnxruntime

Uso:
    detector = WakeWordDetector(callback=harness.trigger_wakeword)
    detector.start()
    detector.pause()   # antes de listen() — libera el mic
    detector.resume()  # después del ciclo STT+TTS
    detector.stop()    # al salir
"""
import sys
try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

import logging
import threading
import time
from typing import Callable

logger = logging.getLogger("jarvis.wakeword")


class WakeWordDetector:
    """Detecta wake word en thread daemon via OpenWakeWord.

    pause()/resume() coordinan el acceso al micrófono con el ciclo STT:
    el wake word cede el mic durante listen()/speak() para evitar conflicto.
    """

    def __init__(self, callback: Callable[[], None]):
        self._callback   = callback
        self._stop_event = threading.Event()
        self._resume     = threading.Event()   # clear=pausado, set=activo
        self._resume.set()
        self._ready      = threading.Event()   # set tras primer sd.rec() exitoso
        self._thread: threading.Thread | None = None
        self._running    = False

    def is_running(self) -> bool:
        return self._running

    def pause(self) -> None:
        """Pausa la captura — cede el micrófono al ciclo STT/TTS."""
        self._resume.clear()

    def resume(self) -> None:
        """Reanuda la captura tras liberar el micrófono."""
        self._resume.set()

    def start(self, model_name: str = "hey_jarvis",
              sensitivity: float = 0.5, cooldown: float = 2.0) -> bool:
        """Inicia el detector. Retorna True solo cuando el micrófono abre con éxito."""
        try:
            from openwakeword.model import Model
            oww = Model(wakeword_models=[model_name], inference_framework="onnx")
            logger.info("OpenWakeWord modelo '%s' cargado.", model_name)
        except Exception as e:
            logger.warning("OpenWakeWord init falló: %s — wake word desactivado", e)
            return False

        self._stop_event.clear()
        self._ready.clear()
        self._resume.set()
        self._running = True
        self._thread = threading.Thread(
            target=self._loop,
            args=(oww, sensitivity, cooldown),
            daemon=True,
            name="wakeword-oww",
        )
        self._thread.start()

        # Bug 9: esperar confirmación de que el mic abrió OK antes de declarar éxito
        if not self._ready.wait(timeout=2.0):
            logger.warning("Wake word: micrófono no disponible en 2s — solo Win+J")
            self._stop_event.set()
            self._resume.set()   # desbloquear si está esperando
            self._running = False
            return False

        logger.info("Wake word 'Hey Jarvis' activo (sensitivity=%.1f, cooldown=%.1fs)",
                    sensitivity, cooldown)
        return True

    def stop(self) -> None:
        """Detiene el detector limpiamente."""
        self._stop_event.set()
        self._resume.set()   # desbloquear si está pausado
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        self._running = False

    def _loop(self, oww, sensitivity: float, cooldown: float) -> None:
        import sounddevice as sd
        import numpy as np
        from jarvis.voice import _find_mic_device, _MIC_SAMPLERATE

        # Grabar a 48kHz nativo, downsamplear a 16kHz para OpenWakeWord
        OWW_RATE     = 16000
        CHUNK_S      = 0.08                          # 80ms por chunk
        DOWNSAMP     = _MIC_SAMPLERATE // OWW_RATE   # 3
        CHUNK_N      = int(CHUNK_S * _MIC_SAMPLERATE) # 3840 samples a 48kHz
        last_trigger = 0.0
        device       = _find_mic_device()
        ready_set    = False

        from jarvis.config import WAKE_WORD_DEBUG

        while not self._stop_event.is_set():
            # Bug 2 + 11: ceder el mic mientras el ciclo STT/TTS está activo
            if not self._resume.is_set():
                self._resume.wait(timeout=0.1)
                continue

            try:
                frame = sd.rec(CHUNK_N, samplerate=_MIC_SAMPLERATE, channels=2,
                               dtype="int16", device=device, blocking=True)

                if not ready_set:
                    self._ready.set()   # Bug 9: primer rec exitoso → start() puede retornar
                    ready_set = True

                # SIN boost — OpenWakeWord espera niveles naturales de audio.
                # El boost×25 clipea la señal (peak=100%) y destruye el patrón acústico.
                audio = np.ascontiguousarray(frame[::DOWNSAMP, 0])   # Bug 1: contiguous

                predictions = oww.predict(audio)
                for ww, score in predictions.items():
                    if WAKE_WORD_DEBUG and score > 0.05:
                        logger.debug("wakeword score '%s': %.3f (threshold=%.2f)",
                                     ww, score, sensitivity)
                    if score >= sensitivity:
                        now = time.monotonic()
                        if now - last_trigger < cooldown:
                            continue
                        last_trigger = now
                        logger.info("Wake word '%s' detectado (score=%.2f)", ww, score)
                        self._callback()
                        break

            except Exception as e:
                logger.error("Wake word loop error: %s", e)
                self._stop_event.wait(timeout=1.0)

        self._running = False
