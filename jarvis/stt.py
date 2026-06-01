"""STT local via faster-whisper — offline, sin API key.

Primera ejecución: descarga el modelo (~244MB para 'small') desde HuggingFace.
Ejecuciones siguientes: carga desde caché (~2s).

Uso:
    from jarvis.stt import transcribe
    text = transcribe(pcm_int16_bytes, samplerate=16000)
"""
import sys
try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

import logging
import threading
import numpy as np

from jarvis.config import STT_MODEL, STT_LANGUAGE, STT_INITIAL_PROMPT

logger = logging.getLogger("jarvis.stt")

_model      = None
_model_lock = threading.Lock()


def _get_model():
    global _model
    if _model is None:                          # Bug 5: double-checked locking
        with _model_lock:
            if _model is None:
                from faster_whisper import WhisperModel
                logger.info("Cargando faster-whisper '%s'...", STT_MODEL)
                _model = WhisperModel(STT_MODEL, device="cpu", compute_type="int8")
                logger.info("faster-whisper listo.")
    return _model


def transcribe(pcm_int16: bytes, samplerate: int = 16000) -> str:
    """Transcribe PCM int16 bytes a texto en español.

    Si samplerate != 16000, resamplea via interpolación lineal antes de enviar
    a Whisper (que requiere 16kHz). Retorna '' si falla o no hay habla.
    """
    try:
        model = _get_model()
        audio = np.frombuffer(pcm_int16, dtype="<i2").astype("float32") / 32768.0

        if samplerate != 16000 and samplerate > 0:
            n_out = int(len(audio) * 16000 / samplerate)
            if n_out > 0:
                audio = np.interp(
                    np.linspace(0, len(audio) - 1, n_out),
                    np.arange(len(audio)),
                    audio,
                ).astype("float32")

        segments, _ = model.transcribe(
            audio,
            language=STT_LANGUAGE,
            beam_size=5,
            vad_filter=True,
            initial_prompt=STT_INITIAL_PROMPT,
        )
        text = " ".join(s.text.strip() for s in segments).strip()
        if text:
            logger.info("STT: '%s'", text)
        return text
    except Exception as e:
        logger.error("STT error: %s", e)
        return ""
