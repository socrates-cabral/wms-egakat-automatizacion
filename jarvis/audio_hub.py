"""AudioHub — dueño único del micrófono para Jarvis v3.

Problema que resuelve: tener dos `sd.rec()` compitiendo por el dispositivo
(loop de wake word + voice.listen del comando) causa PaErrorCode -9996/-9999
en esta máquina (WASAPI/WDM-KS no permite dos streams simultáneos).

Solución: UN solo thread graba el micrófono (recorder) y empuja chunks a una
cola acotada. El processor los consume:
  - modo WAKE:    transcribe ventana rodante con whisper tiny, busca "jarvis".
  - modo COMMAND: corre VAD, acumula la frase, y al terminar entrega el PCM.
Un tercer thread (command worker) corre on_command (STT+Gemini+TTS) sin
bloquear al processor.

Win+J no abre un stream nuevo: solo cambia el modo a COMMAND. Colisión imposible.

Concurrencia:
  - _mode + estado VAD (_vad_*): SIEMPRE bajo _mode_lock.
  - mute es un CONTADOR reentrante (_mute_count) bajo _mute_lock — el saludo
    de arranque y un on_command pueden mutear anidados sin pisarse.
  - on_command corre en el command worker, no en el processor → ESC/Win+J
    siguen atendidos mientras Jarvis habla.

Callbacks:
    on_listening()              -> al entrar en COMMAND (mostrar pill).
    on_command(pcm16k, source)  -> frase capturada; source = "hotkey"|"wakeword".
                                   El hub silencia el mic mientras corre (no se
                                   oye a sí mismo). pcm vacío = sin habla.
"""
import sys
try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

import logging
import queue
import threading
import time
import unicodedata
from typing import Callable

import numpy as np

logger = logging.getLogger("jarvis.audio_hub")

_WAKE    = "wake"
_COMMAND = "command"


def _normalize(text: str) -> str:
    """Minúsculas sin tildes ni puntuación — para fuzzy match del wake word."""
    t = unicodedata.normalize("NFD", text.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return "".join(c if c.isalnum() or c.isspace() else " " for c in t)


# Mapa fonético: agrupa sonidos que whisper confunde al transcribir "Jarvis"
# con acento chileno. j/g/y → mismo sonido; v/b → mismo (español); quita vocales
# débiles. "jarvis", "jeremy", "jairis", "arviz", "harvis" → todos colapsan a ~"jrvs".
_PHON_MAP = str.maketrans({
    "g": "j", "y": "j", "h": "",          # j-sounds
    "v": "b", "w": "b",                    # b-sounds
    "z": "s", "c": "s", "k": "s",          # s-sounds
    "i": "", "e": "", "o": "", "u": "",    # vocales débiles (mantenemos 'a')
})


def _phonetic(word: str) -> str:
    """Reduce una palabra a su esqueleto consonántico para match aproximado."""
    w = _normalize(word).strip().replace(" ", "")
    skel = w.translate(_PHON_MAP)
    # colapsar repetidos: "jjrbs" → "jrbs"
    out = []
    for ch in skel:
        if not out or out[-1] != ch:
            out.append(ch)
    return "".join(out)


class AudioHub:
    # Audio
    REC_CHUNK_S = 0.5
    MIC_RATE    = 48000
    OUT_RATE    = 16000
    BOOST       = 25
    DOWNSAMP    = MIC_RATE // OUT_RATE   # 3

    # VAD (sobre audio CRUDO sin boost — pico de voz típico ~120-800, silencio <60)
    SILENCE_THRESH = 150    # pico crudo mínimo para considerar "voz"
    MAX_SILENCE    = 3      # 1.5s de silencio post-habla → fin de frase
    PRESPEECH      = 10     # 5s sin voz tras trigger → abortar
    MAX_TOTAL      = 12     # 6s tope absoluto
    NORM_TARGET    = 0.8    # normalización de pico al transcribir (80% sin clip)

    QUEUE_MAX      = 40     # 20s de audio — cota dura de memoria

    def __init__(
        self,
        *,
        on_listening: Callable[[], None],
        on_command:   Callable[[bytes, str], None],
        wake_phrases: tuple[str, ...] = (
            # whisper-es mapea "Jarvis" (acento chileno) a estos fonemas.
            # Capturado del log real: "arví", "arviz", "oye arviz".
            "jarvis", "yarvis", "jarbis", "yarbis", "harvis", "jarvys",
            "arvis", "arviz", "arvi", "arbiz", "arbis",
        ),
        cooldown: float = 2.0,
        wake_model_size: str = "base",
        wake_enabled: bool = False,
    ):
        self._on_listening    = on_listening
        self._on_command      = on_command
        # Frases normalizadas (sin tildes/puntuación) para fuzzy match.
        self._wake_phrases    = [_normalize(p).strip() for p in wake_phrases]
        self._cooldown        = cooldown
        self._wake_model_size = wake_model_size
        self._wake_enabled    = wake_enabled

        self._mode      = _WAKE
        self._source    = "wakeword"
        self._mode_lock = threading.Lock()

        self._queue     = queue.Queue(maxsize=self.QUEUE_MAX)
        self._cmd_queue = queue.Queue()
        self._stop      = threading.Event()
        self._ready     = threading.Event()

        self._mute_lock  = threading.Lock()
        self._mute_count = 0

        self._rec_thread:  threading.Thread | None = None
        self._proc_thread: threading.Thread | None = None
        self._cmd_thread:  threading.Thread | None = None
        self._running = False

        # Estado VAD — SOLO bajo _mode_lock
        self._vad_chunks: list = []
        self._vad_started = False
        self._vad_silence = 0
        self._vad_pre     = 0

        self._last_wake = 0.0   # solo lo toca el processor

    # ── API pública ──────────────────────────────────────────────────────

    def is_running(self) -> bool:
        return self._running

    def start(self, ready_timeout: float = 4.0) -> bool:
        """Arranca recorder + processor + command worker. True solo si el mic abre."""
        self._stop.clear()
        self._ready.clear()
        with self._mute_lock:
            self._mute_count = 0
        self._running = True

        self._rec_thread = threading.Thread(
            target=self._recorder_loop, daemon=True, name="audiohub-rec")
        self._proc_thread = threading.Thread(
            target=self._processor_loop, daemon=True, name="audiohub-proc")
        self._cmd_thread = threading.Thread(
            target=self._command_loop, daemon=True, name="audiohub-cmd")
        self._rec_thread.start()
        self._proc_thread.start()
        self._cmd_thread.start()

        if not self._ready.wait(timeout=ready_timeout):
            logger.warning("AudioHub: micrófono no disponible.")
            self.stop()
            return False
        logger.info("AudioHub activo — mic compartido (wake + comando).")
        return True

    def stop(self) -> None:
        self._stop.set()
        try:
            from jarvis.voice import cancel_tts
            cancel_tts()                # corta un TTS en vuelo → command worker sale rápido
        except Exception:
            pass
        self._cmd_queue.put(None)       # desbloquea el command worker
        for t in (self._rec_thread, self._proc_thread, self._cmd_thread):
            if t is not None:
                t.join(timeout=3.0)
        self._running = False

    def trigger_command(self, source: str = "hotkey") -> None:
        """Win+J: pasar a captura de comando. NO abre un stream nuevo."""
        self._enter_command(source)

    # Mute reentrante (contador) — el saludo y on_command pueden anidar.
    def mute(self) -> None:
        with self._mute_lock:
            self._mute_count += 1

    def unmute(self) -> None:
        with self._mute_lock:
            self._mute_count = max(0, self._mute_count - 1)
            resumed = self._mute_count == 0
        if resumed:
            self._drain_queue()

    def _is_muted(self) -> bool:
        with self._mute_lock:
            return self._mute_count > 0

    # ── Recorder: ÚNICO dueño del micrófono ──────────────────────────────

    def _recorder_loop(self) -> None:
        import sounddevice as sd
        from jarvis.voice import _find_mic_device

        device = _find_mic_device()
        n      = int(self.REC_CHUNK_S * self.MIC_RATE)
        first  = True

        while not self._stop.is_set():
            if self._is_muted():
                self._stop.wait(timeout=0.05)
                continue
            try:
                frame = sd.rec(n, samplerate=self.MIC_RATE, channels=2,
                               dtype="int16", device=device, blocking=True)
            except Exception as e:
                logger.error("Recorder error: %s", e)
                self._stop.wait(timeout=0.5)
                continue

            if first:
                self._ready.set()
                first = False

            # Bug 3: si nos muteamos/paramos DURANTE este sd.rec, descartar el
            # frame — pudo capturar el inicio de la propia voz de Jarvis.
            if self._is_muted() or self._stop.is_set():
                continue

            # Audio CRUDO (sin boost): el boost ×25 clipeaba al 100% y destruía
            # la señal para Whisper. El VAD mide energía real; la normalización
            # de pico se aplica al transcribir (sobre la frase completa).
            mono16k = np.ascontiguousarray(frame[::self.DOWNSAMP, 0])
            self._put(mono16k)

    def _put(self, item) -> None:
        """Encola con cota dura: si está llena, descarta el más viejo (Bug 6)."""
        try:
            self._queue.put_nowait(item)
        except queue.Full:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                pass
            try:
                self._queue.put_nowait(item)
            except queue.Full:
                pass

    # ── Processor: wake detection / VAD ──────────────────────────────────

    def _processor_loop(self) -> None:
        # VAD unificado: en AMBOS modos el VAD captura frases completas. El
        # camino de comando (Win+J) ya funcionaba perfecto; ahora el wake usa
        # EL MISMO VAD en vez de la ventana rodante (que cortaba "Jarvis" mal).
        self._wake_model = self._load_wake_model()

        while not self._stop.is_set():
            try:
                chunk = self._queue.get(timeout=0.2)
            except queue.Empty:
                continue

            # Bug 1: inicializar las 3 antes del lock — evita UnboundLocalError
            # latente si la condición de dispatch se reordena en el futuro.
            pcm = source = wake_pcm = None
            with self._mode_lock:
                mode = self._mode
                if mode == _COMMAND:
                    pcm = self._feed_vad(chunk)
                    if pcm is not None:
                        source = self._source
                        self._mode = _WAKE
                        self._reset_vad()
                elif self._wake_model is not None:
                    # WAKE: mismo VAD, pero la frase completa va a _detect_wake.
                    wake_pcm = self._feed_vad(chunk)
                    if wake_pcm is not None:
                        self._reset_vad()

            # COMMAND terminado → dispatch a worker (mute + STT + Gemini + TTS).
            if mode == _COMMAND and pcm is not None:
                self.mute()
                self._drain_queue()
                self._cmd_queue.put((pcm, source))
                continue

            # WAKE: frase capturada → ¿contiene "Jarvis"?
            if mode == _WAKE and self._wake_model is not None and wake_pcm:
                self._detect_wake(self._wake_model, wake_pcm)

    def _command_loop(self) -> None:
        """Corre on_command (STT+Gemini+TTS) fuera del processor (Bug 5)."""
        while not self._stop.is_set():
            item = self._cmd_queue.get()
            if item is None:               # señal de stop()
                break
            pcm, source = item
            try:
                self._on_command(pcm, source)
            except Exception as e:
                logger.error("on_command error: %s", e)
            finally:
                self.unmute()              # balancea el mute del dispatch

    def _load_wake_model(self):
        if not self._wake_enabled:
            return None   # wake desactivado por config → solo Win+J, no carga modelo
        try:
            from faster_whisper import WhisperModel
            logger.info("Cargando whisper '%s' para wake word...", self._wake_model_size)
            m = WhisperModel(self._wake_model_size, device="cpu", compute_type="int8")
            logger.info("Wake word listo (match fonético).")
            return m
        except Exception as e:
            logger.error("Wake word desactivado (whisper no cargó: %s). Solo Win+J.", e)
            return None

    def _detect_wake(self, model, pcm: bytes) -> None:
        """Transcribe una frase completa (capturada por VAD). Si contiene el wake
        word, dispara el comando. Mismo modelo/calidad que el comando — por eso
        ahora SÍ reconoce 'Jarvis' (antes la ventana rodante lo cortaba)."""
        if not pcm:
            return
        audio = np.frombuffer(pcm, dtype="<i2").astype("float32") / 32768.0
        try:
            segments, _ = model.transcribe(
                audio, language="es", beam_size=1, vad_filter=True,
                no_speech_threshold=0.5, condition_on_previous_text=False,
            )
            text = " ".join(s.text for s in segments).strip()
        except Exception as e:
            logger.error("Wake transcribe error: %s", e)
            return
        if not text:
            return
        logger.info("wake chunk: '%s'", text)
        if self._matches_wake(text):
            now = time.monotonic()
            if now - self._last_wake >= self._cooldown:
                self._last_wake = now
                logger.info("Wake word detectado: '%s'", text)
                self._enter_command("wakeword")

    def _matches_wake(self, text: str) -> bool:
        """Match fonético: 'Jarvis' acento chileno → whisper produce Jeremy,
        Jairis, Arviz... Comparamos el esqueleto consonántico de cada palabra
        contra 'jarvis' con similaridad difusa (umbral 0.6)."""
        from difflib import SequenceMatcher
        target = _phonetic("jarvis")            # 'jarbs'
        for word in _normalize(text).split():
            if len(word) < 3:
                continue
            skel = _phonetic(word)
            if not skel:
                continue
            ratio = SequenceMatcher(None, skel, target).ratio()
            if ratio >= 0.6:
                logger.info("  match fonético: '%s' (%s ~ %s = %.2f)",
                            word, skel, target, ratio)
                return True
        return False

    # ── VAD de comando ───────────────────────────────────────────────────

    def _enter_command(self, source: str) -> None:
        # Bug 2: idempotente — si ya estamos capturando, ignorar el re-trigger.
        with self._mode_lock:
            if self._mode == _COMMAND:
                return
            self._mode   = _COMMAND
            self._source = source
            self._reset_vad()
        self._drain_queue()        # descartar la palabra "jarvis"/ambiente pre-Win+J
        self._on_listening()

    def _reset_vad(self) -> None:
        self._vad_chunks  = []
        self._vad_started = False
        self._vad_silence = 0
        self._vad_pre     = 0

    def _feed_vad(self, chunk) -> bytes | None:
        """SOLO se llama bajo _mode_lock. bytes (posible b'') si terminó, None si sigue.

        Un único punto de retorno de 'done' para no finalizar dos veces (Bug 8).
        """
        peak = int(np.abs(chunk).max())
        if peak > self.SILENCE_THRESH:
            self._vad_started = True
            self._vad_silence = 0
            self._vad_chunks.append(chunk)
        elif self._vad_started:
            self._vad_silence += 1
            self._vad_chunks.append(chunk)
        else:
            self._vad_pre += 1

        done = (
            (self._vad_started and self._vad_silence >= self.MAX_SILENCE)
            or (not self._vad_started and self._vad_pre >= self.PRESPEECH)
            or (len(self._vad_chunks) >= self.MAX_TOTAL)
        )
        if not done:
            return None
        if self._vad_started and self._vad_chunks:
            return self._normalize_pcm(np.concatenate(self._vad_chunks))
        return b""

    def _normalize_pcm(self, samples: np.ndarray) -> bytes:
        """Normaliza el pico de la frase a NORM_TARGET sin clipear. Reemplaza el
        boost ×25 fijo que saturaba la señal y la hacía ininteligible para STT."""
        s = samples.astype("int32")
        peak = int(np.abs(s).max())
        if peak > 0:
            gain = (32767 * self.NORM_TARGET) / peak
            s = np.clip(s * gain, -32768, 32767)
        return s.astype("int16").tobytes()

    # ── Utilidades ───────────────────────────────────────────────────────

    def _drain_queue(self) -> None:
        try:
            while True:
                self._queue.get_nowait()
        except queue.Empty:
            pass
