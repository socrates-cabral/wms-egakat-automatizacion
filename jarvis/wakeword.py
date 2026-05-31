"""Wake word detector — dos engines disponibles:

  whisper (default): faster-whisper tiny transcribe chunks de 2s, detecta "jarvis"
                     en el texto. Funciona con cualquier pronunciación/acento.
  oww:               OpenWakeWord hey_jarvis_v0.1.onnx. Requiere pronunciación
                     inglesa exacta — no recomendado con acento español.

Config (.env o config.py):
    WAKE_WORD_ENGINE = "whisper"   # o "oww"
    WAKE_WORD_PHRASES = jarvis,harvey,jarviz
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
    """Detecta wake word en thread daemon.

    pause()/resume() coordinan el acceso al mic con el ciclo STT.
    """

    def __init__(self, callback: Callable[[], None]):
        self._callback   = callback
        self._stop_event = threading.Event()
        self._resume     = threading.Event()
        self._resume.set()
        self._ready      = threading.Event()
        self._mic_busy   = threading.Event()
        self._thread: threading.Thread | None = None
        self._running    = False

    def is_running(self) -> bool:
        return self._running

    def pause(self) -> None:
        """Pausa y espera a que el rec() en curso libere el mic (max 1.5s)."""
        self._resume.clear()
        deadline = time.monotonic() + 1.5   # cubre chunks de hasta 1s + margen
        while self._mic_busy.is_set() and time.monotonic() < deadline:
            time.sleep(0.005)

    def resume(self) -> None:
        """Devuelve el mic al detector."""
        self._resume.set()

    def stop(self) -> None:
        self._stop_event.set()
        self._resume.set()
        if self._thread is not None:
            self._thread.join(timeout=3.0)
        self._running = False

    def start(self, engine: str = "whisper",
              phrases: list[str] | None = None,
              sensitivity: float = 0.3,
              cooldown: float = 2.0,
              oww_model: str = "hey_jarvis",
              whisper_chunk_s: float = 1.0,
              whisper_model_size: str = "tiny") -> bool:
        """Inicia el detector. Retorna True solo cuando el mic confirma apertura."""
        self._stop_event.clear()
        self._ready.clear()
        self._resume.set()
        self._running = True

        if engine == "oww":
            target = self._loop_oww
            args   = (oww_model, sensitivity, cooldown)
        else:
            target = self._loop_whisper
            args   = (phrases or ["jarvis", "harvey", "jarviz"], cooldown,
                      whisper_chunk_s, whisper_model_size)

        self._thread = threading.Thread(target=target, args=args,
                                        daemon=True, name="wakeword")
        self._thread.start()

        if not self._ready.wait(timeout=4.0):
            logger.warning("Wake word: mic no abrió en 4s — solo Win+J disponible.")
            self._stop_event.set()
            self._resume.set()
            self._running = False
            return False

        logger.info("Wake word activo [%s] (cooldown=%.1fs)", engine, cooldown)
        return True

    # ── Engine: Whisper ────────────────────────────────────────────────────

    def _loop_whisper(self, phrases: list[str], cooldown: float,
                      chunk_s: float, model_size: str) -> None:
        import sounddevice as sd
        import numpy as np
        from jarvis.voice import _find_mic_device, _MIC_SAMPLERATE

        device    = _find_mic_device()
        OWW_RATE  = 16000
        DOWNSAMP  = _MIC_SAMPLERATE // OWW_RATE
        CHUNK_N   = int(chunk_s * _MIC_SAMPLERATE)
        last_trig = 0.0

        # Test rápido del mic para señalizar _ready antes de cargar el modelo
        try:
            self._mic_busy.set()
            sd.rec(1280, samplerate=_MIC_SAMPLERATE, channels=2,
                   dtype="int16", device=device, blocking=True)
            self._mic_busy.clear()
            self._ready.set()
        except Exception as e:
            self._mic_busy.clear()
            logger.error("Mic test falló: %s", e)
            self._running = False
            return

        # Cargar modelo tiny (39MB, ~1s en caché)
        try:
            from faster_whisper import WhisperModel
            logger.info("Cargando whisper '%s' para wake word...", model_size)
            model = WhisperModel(model_size, device="cpu", compute_type="int8")
            logger.info("Whisper wake word listo. Frases: %s", phrases)
        except Exception as e:
            logger.error("Whisper no pudo cargar: %s — wake word desactivado", e)
            self._running = False
            return

        while not self._stop_event.is_set():
            if not self._resume.is_set():
                self._resume.wait(timeout=0.1)
                continue
            try:
                self._mic_busy.set()
                frame = sd.rec(CHUNK_N, samplerate=_MIC_SAMPLERATE, channels=2,
                               dtype="int16", device=device, blocking=True)
                self._mic_busy.clear()

                audio = (np.ascontiguousarray(frame[::DOWNSAMP, 0])
                         .astype("float32") / 32768.0)

                # vad_filter=True: salta chunks de silencio sin gastar CPU en inference
                segments, _ = model.transcribe(audio, beam_size=1, vad_filter=True)
                text = " ".join(s.text for s in segments).lower().strip()

                if text:
                    logger.info("whisper chunk: '%s'", text)
                    if any(p in text for p in phrases):
                        now = time.monotonic()
                        if now - last_trig >= cooldown:
                            last_trig = now
                            logger.info("Wake word detectado: '%s'", text)
                            self._callback()

            except Exception as e:
                self._mic_busy.clear()
                logger.error("Wake word loop error: %s", e)
                self._stop_event.wait(timeout=1.0)

        self._mic_busy.clear()
        self._running = False

    # ── Engine: OpenWakeWord ───────────────────────────────────────────────

    def _loop_oww(self, model_name: str, sensitivity: float, cooldown: float) -> None:
        import sounddevice as sd
        import numpy as np
        from jarvis.voice import _find_mic_device, _MIC_SAMPLERATE

        try:
            from openwakeword.model import Model
            oww = Model(wakeword_models=[model_name], inference_framework="onnx")
        except Exception as e:
            logger.warning("OpenWakeWord init falló: %s", e)
            self._running = False
            return

        device    = _find_mic_device()
        DOWNSAMP  = _MIC_SAMPLERATE // 16000
        CHUNK_N   = int(0.08 * _MIC_SAMPLERATE)   # 80ms
        last_trig = 0.0
        ready_set = False

        while not self._stop_event.is_set():
            if not self._resume.is_set():
                self._resume.wait(timeout=0.1)
                continue
            try:
                self._mic_busy.set()
                frame = sd.rec(CHUNK_N, samplerate=_MIC_SAMPLERATE, channels=2,
                               dtype="int16", device=device, blocking=True)
                self._mic_busy.clear()

                if not ready_set:
                    self._ready.set()
                    ready_set = True

                audio       = np.ascontiguousarray(frame[::DOWNSAMP, 0])
                predictions = oww.predict(audio)
                for ww, score in predictions.items():
                    if score > 0.05:
                        logger.info("oww score '%s': %.3f (threshold=%.2f)",
                                    ww, score, sensitivity)
                    if score >= sensitivity:
                        now = time.monotonic()
                        if now - last_trig >= cooldown:
                            last_trig = now
                            logger.info("Wake word detectado '%s' (%.2f)", ww, score)
                            self._callback()
                            break
            except Exception as e:
                self._mic_busy.clear()
                logger.error("Wake word loop error: %s", e)
                self._stop_event.wait(timeout=1.0)

        self._mic_busy.clear()
        self._running = False
