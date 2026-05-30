import pytest
from PyQt6.QtCore import Qt
from jarvis.ui.bridge import JarvisBridge
from jarvis.ui.overlay import JarvisOverlay, OverlayState


def test_overlay_starts_hidden(qtbot):
    bridge = JarvisBridge()
    overlay = JarvisOverlay(bridge)
    assert not overlay.isVisible()


def test_overlay_shows_on_listening(qtbot):
    bridge = JarvisBridge()
    overlay = JarvisOverlay(bridge)
    bridge.listening_started.emit()
    qtbot.wait(300)
    assert overlay.isVisible()
    assert overlay.state == OverlayState.LISTENING


def test_overlay_shows_processing_state(qtbot):
    bridge = JarvisBridge()
    overlay = JarvisOverlay(bridge)
    bridge.listening_started.emit()
    bridge.processing_started.emit()
    qtbot.wait(50)
    assert overlay.state == OverlayState.PROCESSING


def test_overlay_shows_tool_state(qtbot):
    bridge = JarvisBridge()
    overlay = JarvisOverlay(bridge)
    bridge.listening_started.emit()
    bridge.tool_started.emit("📊 Leyendo WMS...")
    qtbot.wait(50)
    assert overlay.state == OverlayState.TOOL_EXECUTING


def test_overlay_shows_speaking_state(qtbot):
    bridge = JarvisBridge()
    overlay = JarvisOverlay(bridge)
    bridge.listening_started.emit()
    bridge.response_ready.emit("BTC en $73,000.")
    qtbot.wait(50)
    assert overlay.state == OverlayState.SPEAKING


def test_overlay_hides_after_speaking_done(qtbot):
    bridge = JarvisBridge()
    overlay = JarvisOverlay(bridge)
    bridge.listening_started.emit()
    qtbot.wait(300)
    bridge.speaking_done.emit()
    qtbot.wait(500)
    assert not overlay.isVisible()
