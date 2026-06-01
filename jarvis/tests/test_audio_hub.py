"""Tests del AudioHub — mic compartido (recorder único + processor + cmd worker).

Estrategia: mockear sounddevice.rec (única fuente de audio) y el modelo whisper
de wake. Las frases speech/silence se inyectan para ejercitar VAD, wake y races.
"""
import threading
import time
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from jarvis.audio_hub import AudioHub, _normalize


# Frames a 48kHz/2ch que produce sd.rec (antes de boost+downsample)
_N = int(AudioHub.REC_CHUNK_S * AudioHub.MIC_RATE)   # 24000
_SPEECH  = np.full((_N, 2), 200, dtype="int16")       # 200*25 = 5000 > 3000 → voz
_SILENCE = np.zeros((_N, 2), dtype="int16")           # 0 → silencio


class _FrameFeeder:
    """sd.rec mock: entrega frames de un script y luego silencio. Paced 10ms."""
    def __init__(self, script):
        self._script = list(script)
        self._i = 0
        self._lock = threading.Lock()

    def __call__(self, *a, **kw):
        time.sleep(0.01)   # evita spin infinito con mock instantáneo
        with self._lock:
            if self._i < len(self._script):
                f = self._script[self._i]
                self._i += 1
                return f
        return _SILENCE


def _hub_ctx(feeder, wake_model=None):
    """Devuelve los 3 context managers comunes para usar con un solo `with`."""
    from contextlib import ExitStack
    stack = ExitStack()
    stack.enter_context(patch("jarvis.voice._find_mic_device", return_value=0))
    stack.enter_context(patch("sounddevice.rec", side_effect=feeder))
    stack.enter_context(patch.object(AudioHub, "_load_wake_model", return_value=wake_model))
    return stack


def test_normalize_strips_accents_and_punctuation():
    """_normalize: minúsculas, sin tildes ni puntuación (fuzzy wake match)."""
    assert _normalize("¡Jarvis!").strip() == "jarvis"
    assert _normalize("Jarvis.").strip() == "jarvis"
    assert _normalize("JARVIS").strip() == "jarvis"
    assert _normalize("¿Qué?").strip() == "que"


def test_wake_phrases_match_real_outputs():
    """Las frases por defecto del hub detectan 'Jarvis' sin falsos positivos comunes."""
    hub = AudioHub(on_listening=lambda: None, on_command=lambda p, s: None)
    phrases = hub._wake_phrases   # ya normalizadas en __init__

    def matches(text):
        norm = _normalize(text)
        return any(p in norm for p in phrases)

    # Positivos: variantes reales que whisper-es produjo para "Jarvis" (del log)
    assert matches("Jarvis")
    assert matches("¡Oye Arviz!")
    assert matches("Oh le arví")
    assert matches("Yarvis")
    # Negativos: ruido/conversación real del log que NO debe disparar
    assert not matches("hola")
    assert not matches("dame el tiempo")
    assert not matches("gracias")
    assert not matches("dónde estás")
    assert not matches("bien desayuno")


def test_start_returns_false_when_mic_fails():
    """Si sd.rec siempre lanza, start() retorna False tras el timeout."""
    def boom(*a, **kw):
        time.sleep(0.01)
        raise Exception("device unavailable")

    hub = AudioHub(on_listening=lambda: None, on_command=lambda p, s: None)
    with _hub_ctx(boom):
        ok = hub.start(ready_timeout=0.5)
    assert ok is False
    assert not hub.is_running()


def test_start_returns_true_when_mic_opens():
    """Con sd.rec devolviendo silencio, start() retorna True."""
    hub = AudioHub(on_listening=lambda: None, on_command=lambda p, s: None)
    with _hub_ctx(_FrameFeeder([])):
        ok = hub.start(ready_timeout=2.0)
        assert ok is True
        assert hub.is_running()
        hub.stop()
    assert not hub.is_running()


def test_hotkey_speech_yields_nonempty_command():
    """Win+J + voz seguida de silencio → on_command con PCM no vacío."""
    captured = {}
    done = threading.Event()

    def on_command(pcm, source):
        captured["pcm"] = pcm
        captured["source"] = source
        done.set()

    feeder = _FrameFeeder([_SPEECH, _SPEECH, _SILENCE, _SILENCE, _SILENCE])
    hub = AudioHub(on_listening=lambda: None, on_command=on_command)
    with _hub_ctx(feeder):
        assert hub.start(ready_timeout=2.0)
        hub.trigger_command(source="hotkey")
        assert done.wait(timeout=5.0), "on_command no fue llamado"
        hub.stop()

    assert captured["source"] == "hotkey"
    assert len(captured["pcm"]) > 0


def test_hotkey_silence_yields_empty_command():
    """Win+J sin voz → on_command con PCM vacío tras timeout pre-speech."""
    captured = {}
    done = threading.Event()

    def on_command(pcm, source):
        captured["pcm"] = pcm
        done.set()

    hub = AudioHub(on_listening=lambda: None, on_command=on_command)
    with _hub_ctx(_FrameFeeder([])):
        assert hub.start(ready_timeout=2.0)
        hub.trigger_command(source="hotkey")
        assert done.wait(timeout=5.0), "on_command no fue llamado en silencio"
        hub.stop()

    assert captured["pcm"] == b""


def test_wake_word_triggers_command():
    """Modelo wake detecta 'jarvis' → on_listening + on_command."""
    listening = threading.Event()
    commanded = threading.Event()

    seg = MagicMock(); seg.text = " hola jarvis "
    wake_model = MagicMock()
    wake_model.transcribe.return_value = ([seg], MagicMock())

    feeder = _FrameFeeder([_SPEECH, _SPEECH, _SILENCE, _SILENCE, _SILENCE])
    hub = AudioHub(on_listening=lambda: listening.set(),
                   on_command=lambda p, s: commanded.set())
    with _hub_ctx(feeder, wake_model=wake_model):
        assert hub.start(ready_timeout=2.0)
        assert listening.wait(timeout=5.0), "on_listening no disparó tras wake"
        assert commanded.wait(timeout=5.0), "on_command no disparó tras wake"
        hub.stop()


def test_mute_stops_recording():
    """Tras mute(), sd.rec deja de aportar audio nuevo a la cola."""
    calls = [0]
    lock = threading.Lock()

    def feeder(*a, **kw):
        time.sleep(0.01)
        with lock:
            calls[0] += 1
        return _SILENCE

    hub = AudioHub(on_listening=lambda: None, on_command=lambda p, s: None)
    with _hub_ctx(feeder):
        assert hub.start(ready_timeout=2.0)
        time.sleep(0.2)
        hub.mute()
        time.sleep(0.1)
        with lock:
            before = calls[0]
        time.sleep(0.3)
        with lock:
            after = calls[0]
        hub.stop()

    assert after == before, f"recorder siguió grabando tras mute ({before}→{after})"


def test_mute_is_reentrant():
    """mute() x2 requiere unmute() x2 para reanudar (contador, no Event)."""
    hub = AudioHub(on_listening=lambda: None, on_command=lambda p, s: None)
    hub.mute()
    hub.mute()
    assert hub._is_muted()
    hub.unmute()
    assert hub._is_muted(), "un solo unmute no debe reanudar tras dos mute"
    hub.unmute()
    assert not hub._is_muted()
    hub.unmute()  # extra no debe romper (clamp en 0)
    assert not hub._is_muted()


def test_double_trigger_is_idempotent():
    """trigger_command x2 rápido durante captura → una sola sesión de comando."""
    count = [0]
    done = threading.Event()
    lock = threading.Lock()

    def on_command(pcm, source):
        with lock:
            count[0] += 1
        done.set()

    feeder = _FrameFeeder([_SPEECH, _SPEECH, _SILENCE, _SILENCE, _SILENCE])
    hub = AudioHub(on_listening=lambda: None, on_command=on_command)
    with _hub_ctx(feeder):
        assert hub.start(ready_timeout=2.0)
        hub.trigger_command(source="hotkey")
        hub.trigger_command(source="hotkey")   # segundo trigger inmediato
        hub.trigger_command(source="hotkey")
        assert done.wait(timeout=5.0)
        time.sleep(0.3)
        hub.stop()

    assert count[0] == 1, f"se esperaba 1 comando, hubo {count[0]}"


def test_stop_during_long_command_returns_clean():
    """stop() mientras on_command duerme 5s → retorna sin colgar (cancel_tts)."""
    started = threading.Event()

    def slow_command(pcm, source):
        started.set()
        time.sleep(5.0)   # simula Gemini+TTS largo

    feeder = _FrameFeeder([_SPEECH, _SPEECH, _SILENCE, _SILENCE, _SILENCE])
    hub = AudioHub(on_listening=lambda: None, on_command=slow_command)
    with _hub_ctx(feeder):
        assert hub.start(ready_timeout=2.0)
        hub.trigger_command(source="hotkey")
        assert started.wait(timeout=5.0), "on_command no arrancó"
        t0 = time.monotonic()
        hub.stop()                      # no debe esperar los 5s completos
        elapsed = time.monotonic() - t0

    # stop hace join(timeout=3) por thread; el cmd worker es daemon → no cuelga
    assert elapsed < 4.0, f"stop() tardó {elapsed:.1f}s — ¿no canceló?"
    assert not hub.is_running()
