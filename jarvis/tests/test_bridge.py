import pytest
from PyQt6.QtCore import QCoreApplication
from jarvis.ui.bridge import JarvisBridge, get_bridge


def test_bridge_emits_listening_started(qtbot):
    bridge = JarvisBridge()
    with qtbot.waitSignal(bridge.listening_started, timeout=500):
        bridge.listening_started.emit()


def test_bridge_emits_tool_started_with_name(qtbot):
    bridge = JarvisBridge()
    received = []
    bridge.tool_started.connect(received.append)
    bridge.tool_started.emit("📊 Leyendo WMS...")
    assert received == ["📊 Leyendo WMS..."]


def test_get_bridge_returns_singleton(qapp):
    b1 = get_bridge()
    b2 = get_bridge()
    assert b1 is b2


def test_get_bridge_is_jarvis_bridge(qapp):
    assert isinstance(get_bridge(), JarvisBridge)
