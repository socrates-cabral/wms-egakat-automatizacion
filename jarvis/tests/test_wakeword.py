import threading
import time
from unittest.mock import MagicMock, patch
import numpy as np
import pytest


def test_start_returns_false_when_openwakeword_missing():
    """Si openwakeword no está instalado, start() retorna False."""
    from jarvis.wakeword import WakeWordDetector
    detector = WakeWordDetector(callback=lambda: None)
    with patch.dict("sys.modules", {"openwakeword": None, "openwakeword.model": None}):
        result = detector.start("hey_jarvis")
    assert result is False
    assert not detector.is_running()


def test_start_returns_false_on_model_exception():
    """Si Model() lanza excepción (modelo no encontrado), start() retorna False."""
    from jarvis.wakeword import WakeWordDetector
    mock_oww_model = MagicMock()
    mock_oww_model.Model.side_effect = Exception("Model not found")
    mock_oww = MagicMock()
    mock_oww.model = mock_oww_model

    detector = WakeWordDetector(callback=lambda: None)
    with patch.dict("sys.modules", {"openwakeword": mock_oww, "openwakeword.model": mock_oww_model}):
        result = detector.start("hey_jarvis")
    assert result is False
    assert not detector.is_running()


def test_stop_before_start_is_safe():
    """Llamar stop() sin haber llamado start() no lanza excepción."""
    from jarvis.wakeword import WakeWordDetector
    detector = WakeWordDetector(callback=lambda: None)
    detector.stop()


def test_is_running_true_after_start_false_after_stop():
    """is_running() refleja el estado del thread correctamente."""
    from jarvis.wakeword import WakeWordDetector

    mock_model_instance = MagicMock()
    # predict() devuelve score bajo para no disparar el callback
    mock_model_instance.predict.return_value = {"hey_jarvis": 0.0}

    mock_model_cls = MagicMock(return_value=mock_model_instance)
    mock_oww_model_mod = MagicMock()
    mock_oww_model_mod.Model = mock_model_cls

    stop_gate = threading.Event()

    def fake_read(n):
        stop_gate.wait(timeout=5.0)
        return np.zeros((1280, 1), dtype="int16"), None

    mock_stream = MagicMock()
    mock_stream.__enter__ = MagicMock(return_value=mock_stream)
    mock_stream.__exit__ = MagicMock(return_value=False)
    mock_stream.read.side_effect = fake_read

    detector = WakeWordDetector(callback=lambda: None)
    with patch.dict("sys.modules", {"openwakeword.model": mock_oww_model_mod}):
        with patch("sounddevice.InputStream", return_value=mock_stream):
            ok = detector.start("hey_jarvis")
            assert ok is True
            assert detector.is_running()
            stop_gate.set()
            detector.stop()

    assert not detector.is_running()


def test_callback_called_on_detection():
    """Cuando predict() retorna score >= sensitivity, se llama el callback."""
    from jarvis.wakeword import WakeWordDetector

    callback_called = threading.Event()

    mock_model_instance = MagicMock()
    # Primera llamada: sin detección; siguiente: detección
    mock_model_instance.predict.side_effect = [
        {"hey_jarvis": 0.1},   # bajo el threshold
        {"hey_jarvis": 0.9},   # sobre el threshold → trigger
        {"hey_jarvis": 0.0},   # cooldown activo, loop continúa
    ]

    mock_model_cls = MagicMock(return_value=mock_model_instance)
    mock_oww_model_mod = MagicMock()
    mock_oww_model_mod.Model = mock_model_cls

    frame = np.zeros((1280, 1), dtype="int16")
    mock_stream = MagicMock()
    mock_stream.__enter__ = MagicMock(return_value=mock_stream)
    mock_stream.__exit__ = MagicMock(return_value=False)
    mock_stream.read.return_value = (frame, None)

    def callback():
        callback_called.set()

    detector = WakeWordDetector(callback=callback)
    with patch.dict("sys.modules", {"openwakeword.model": mock_oww_model_mod}):
        with patch("sounddevice.InputStream", return_value=mock_stream):
            detector.start("hey_jarvis", sensitivity=0.5)
            callback_called.wait(timeout=2.0)
            detector.stop()

    assert callback_called.is_set(), "Callback no fue llamado tras detección"


def test_cooldown_prevents_double_trigger():
    """Dos detecciones consecutivas dentro del cooldown solo disparan una vez."""
    from jarvis.wakeword import WakeWordDetector

    trigger_count = [0]
    trigger_lock = threading.Lock()

    mock_model_instance = MagicMock()
    # Dos detecciones seguidas sin pausa
    mock_model_instance.predict.side_effect = [
        {"hey_jarvis": 0.9},
        {"hey_jarvis": 0.9},
        {"hey_jarvis": 0.0},
        {"hey_jarvis": 0.0},
    ]

    mock_model_cls = MagicMock(return_value=mock_model_instance)
    mock_oww_model_mod = MagicMock()
    mock_oww_model_mod.Model = mock_model_cls

    frame = np.zeros((1280, 1), dtype="int16")
    mock_stream = MagicMock()
    mock_stream.__enter__ = MagicMock(return_value=mock_stream)
    mock_stream.__exit__ = MagicMock(return_value=False)
    mock_stream.read.return_value = (frame, None)

    done = threading.Event()

    def callback():
        with trigger_lock:
            trigger_count[0] += 1
        done.set()

    detector = WakeWordDetector(callback=callback)
    with patch.dict("sys.modules", {"openwakeword.model": mock_oww_model_mod}):
        with patch("sounddevice.InputStream", return_value=mock_stream):
            detector.start("hey_jarvis", sensitivity=0.5, cooldown=10.0)
            done.wait(timeout=2.0)
            time.sleep(0.1)  # dar tiempo a que procese el segundo frame
            detector.stop()

    assert trigger_count[0] == 1, f"Se esperaba 1 trigger, got {trigger_count[0]}"
