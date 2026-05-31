"""Wake word detector usando OpenWakeWord (sin cuenta, sin API key, 100% local).

Modelo por defecto: 'hey_jarvis' (bundled en openwakeword).
Requiere: pip install openwakeword onnxruntime

Uso:
    from jarvis.wakeword import WakeWordDetector
    detector = WakeWordDetector(callback=harness.trigger)
    detector.start()       # usa config.py para modelo y sensibilidad
    detector.stop()        # al salir
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

    Si openwakeword no está instalado o el modelo falla, start() retorna False
    y Win+J sigue funcionando sin interrupción.
    """

    def __init__(self, callback: Callable[[], None]):
        self._callback   = callback
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._running    = False

    def is_running(self) -> bool:
        return self._running

    def start(self, model_name: str = "hey_jarvis",
              sensitivity: float = 0.5, cooldown: float = 2.0) -> bool:
        """Inicia el detector. Retorna True si arrancó correctamente."""
        try:
            from openwakeword.model import Model
            oww = Model(wakeword_models=[model_name], inference_framework="onnx")
            logger.info("OpenWakeWord modelo '%s' cargado.", model_name)
        except Exception as e:
            logger.warning("OpenWakeWord init falló: %s — wake word desactivado", e)
            return False

        self._stop_event.clear()
        self._running = True
        self._thread = threading.Thread(
            target=self._loop,
            args=(oww, sensitivity, cooldown),
            daemon=True,
            name="wakeword-oww",
        )
        self._thread.start()
        logger.info("Wake word 'Hey Jarvis' activo (sensitivity=%.1f, cooldown=%.1fs)",
                    sensitivity, cooldown)
        return True

    def stop(self) -> None:
        """Detiene el detector limpiamente."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        self._running = False

    def _loop(self, oww, sensitivity: float, cooldown: float) -> None:
        import sounddevice as sd
        import numpy as np
        from jarvis.voice import _find_mic_device, _MIC_SAMPLERATE, _MIC_BOOST

        # Grabar a la tasa nativa del dispositivo (48kHz) y downsamplear a 16kHz.
        # Mismo patrón que el VAD — sd.rec() compatible con WASAPI en esta máquina.
        OWW_RATE  = 16000   # OpenWakeWord requiere 16kHz
        CHUNK_S   = 0.08    # 80ms por chunk (1280 samples a 16kHz)
        DOWNSAMP  = _MIC_SAMPLERATE // OWW_RATE            # 48000//16000 = 3
        CHUNK_N   = int(CHUNK_S * _MIC_SAMPLERATE)         # 3840 samples a 48kHz
        last_trigger = 0.0
        device = _find_mic_device()

        while not self._stop_event.is_set():
            try:
                frame = sd.rec(CHUNK_N, samplerate=_MIC_SAMPLERATE, channels=2,
                               dtype="int16", device=device, blocking=True)
                # Boost + downsample + mono (igual que VAD)
                boosted = np.clip(frame.astype("int32") * _MIC_BOOST,
                                  -32768, 32767).astype("int16")
                audio = boosted[::DOWNSAMP, 0]   # 1280 samples mono a 16kHz

                predictions = oww.predict(audio)
                for ww, score in predictions.items():
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
