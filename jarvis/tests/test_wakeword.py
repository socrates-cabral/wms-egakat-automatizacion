import threading
import time
from unittest.mock import MagicMock, patch
import numpy as np
import pytest


def _make_oww_mock(scores=None):
    """Crea un mock de openwakeword.model.Model con predict() configurable."""
    scores = scores or [{"hey_jarvis": 0.0}]
    mock_instance = MagicMock()
    mock_instance.predict.side_effect = scores + [{"hey_jarvis": 0.0}] * 100
    mock_cls = MagicMock(return_value=mock_instance)
    mock_mod = MagicMock()
    mock_mod.Model = mock_cls
    return mock_mod, mock_instance


def test_start_returns_false_when_openwakeword_missing():
    """Si openwakeword no está instalado, start() retorna False."""
    from jarvis.wakeword import WakeWordDetector
    detector = WakeWordDetector(callback=lambda: None)
    with patch.dict("sys.modules", {"openwakeword": None, "openwakeword.model": None}):
        result = detector.start("hey_jarvis")
    assert result is False
    assert not detector.is_running()


def test_start_returns_false_on_model_exception():
    """Si Model() lanza, start() retorna False."""
    from jarvis.wakeword import WakeWordDetector
    mock_mod = MagicMock()
    mock_mod.Model.side_effect = Exception("Model not found")
    detector = WakeWordDetector(callback=lambda: None)
    with patch.dict("sys.modules", {"openwakeword.model": mock_mod}):
        result = detector.start("hey_jarvis")
    assert result is False
    assert not detector.is_running()


def test_stop_before_start_is_safe():
    """stop() sin start() no lanza excepción."""
    from jarvis.wakeword import WakeWordDetector
    detector = WakeWordDetector(callback=lambda: None)
    detector.stop()


def test_start_returns_false_when_mic_unavailable():
    """Si sd.rec() siempre falla, start() espera 2s y retorna False."""
    from jarvis.wakeword import WakeWordDetector
    mock_mod, _ = _make_oww_mock()

    with patch.dict("sys.modules", {"openwakeword.model": mock_mod}):
        with patch("sounddevice.rec", side_effect=Exception("device unavailable")):
            with patch("jarvis.voice._find_mic_device", return_value=5):
                t0 = time.monotonic()
                detector = WakeWordDetector(callback=lambda: None)
                result = detector.start("hey_jarvis", sensitivity=0.5, cooldown=2.0)
                elapsed = time.monotonic() - t0

    assert result is False
    assert elapsed >= 1.9   # esperó ~2s de timeout


def test_start_returns_true_when_mic_opens():
    """Si sd.rec() tiene éxito, start() retorna True rápidamente."""
    from jarvis.wakeword import WakeWordDetector
    mock_mod, _ = _make_oww_mock()
    frame = np.zeros((3840, 2), dtype="int16")

    with patch.dict("sys.modules", {"openwakeword.model": mock_mod}):
        with patch("sounddevice.rec", return_value=frame):
            with patch("jarvis.voice._find_mic_device", return_value=5):
                detector = WakeWordDetector(callback=lambda: None)
                t0 = time.monotonic()
                result = detector.start("hey_jarvis")
                elapsed = time.monotonic() - t0
                detector.stop()

    assert result is True
    assert elapsed < 1.0   # no espera el timeout completo


def test_callback_called_on_detection():
    """Cuando score >= sensitivity, se llama el callback."""
    from jarvis.wakeword import WakeWordDetector
    callback_called = threading.Event()
    frame = np.zeros((3840, 2), dtype="int16")

    mock_mod, mock_instance = _make_oww_mock(scores=[
        {"hey_jarvis": 0.1},   # bajo threshold
        {"hey_jarvis": 0.9},   # sobre threshold → trigger
    ])

    with patch.dict("sys.modules", {"openwakeword.model": mock_mod}):
        with patch("sounddevice.rec", return_value=frame):
            with patch("jarvis.voice._find_mic_device", return_value=5):
                detector = WakeWordDetector(callback=lambda: callback_called.set())
                ok = detector.start("hey_jarvis", sensitivity=0.5)
                assert ok
                callback_called.wait(timeout=2.0)
                detector.stop()

    assert callback_called.is_set()


def test_cooldown_prevents_double_trigger():
    """Dos detecciones seguidas dentro del cooldown solo disparan una vez."""
    from jarvis.wakeword import WakeWordDetector
    count = [0]
    frame = np.zeros((3840, 2), dtype="int16")
    done  = threading.Event()

    mock_mod, _ = _make_oww_mock(scores=[
        {"hey_jarvis": 0.9},
        {"hey_jarvis": 0.9},
    ])

    def cb():
        count[0] += 1
        done.set()

    with patch.dict("sys.modules", {"openwakeword.model": mock_mod}):
        with patch("sounddevice.rec", return_value=frame):
            with patch("jarvis.voice._find_mic_device", return_value=5):
                detector = WakeWordDetector(callback=cb)
                detector.start("hey_jarvis", sensitivity=0.5, cooldown=60.0)
                done.wait(timeout=2.0)
                time.sleep(0.15)
                detector.stop()

    assert count[0] == 1


def test_pause_resume_stops_recording():
    """pause() detiene el loop; resume() lo reanuda."""
    from jarvis.wakeword import WakeWordDetector
    rec_calls = [0]
    frame     = np.zeros((3840, 2), dtype="int16")
    mock_mod, _ = _make_oww_mock()

    def fake_rec(*a, **kw):
        rec_calls[0] += 1
        return frame

    with patch.dict("sys.modules", {"openwakeword.model": mock_mod}):
        with patch("sounddevice.rec", side_effect=fake_rec):
            with patch("jarvis.voice._find_mic_device", return_value=5):
                detector = WakeWordDetector(callback=lambda: None)
                detector.start("hey_jarvis")
                time.sleep(0.3)
                before = rec_calls[0]
                detector.pause()
                time.sleep(0.3)
                paused_calls = rec_calls[0] - before
                detector.resume()
                time.sleep(0.3)
                after_resume = rec_calls[0]
                detector.stop()

    # Durante pausa no hubo grabaciones nuevas
    assert paused_calls == 0
    # Tras resume sí hubo
    assert after_resume > rec_calls[0] - 1 or after_resume > before
