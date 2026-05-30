import sys
sys.stdout.reconfigure(encoding="utf-8")

from enum import Enum, auto

from PyQt6.QtWidgets import (
    QWidget, QFrame, QLabel, QHBoxLayout, QVBoxLayout, QApplication,
)
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, pyqtSlot
from PyQt6.QtGui import QFont

from jarvis.ui.bridge import JarvisBridge
from jarvis.ui.animations import WaveformWidget, TypewriterLabel


class OverlayState(Enum):
    IDLE           = auto()
    LISTENING      = auto()
    PROCESSING     = auto()
    TOOL_EXECUTING = auto()
    KAI_RUNNING    = auto()
    SPEAKING       = auto()


_PILL_STYLE = """
QFrame#pill {
    background-color: rgba(10, 15, 26, 220);
    border: 1px solid rgba(0, 212, 255, 100);
    border-radius: 26px;
}
"""

_COLORS = {
    "cyan":   "#00d4ff",
    "blue":   "#4a9eff",
    "white":  "#e6edf3",
    "amber":  "#f0a500",
    "violet": "#a371f7",
}


class JarvisOverlay(QWidget):
    PILL_W           = 360
    PILL_H_COLLAPSED = 52
    PILL_H_EXPANDED  = 120
    MARGIN_BOTTOM    = 48

    def __init__(self, bridge: JarvisBridge):
        super().__init__()
        self._bridge = bridge
        self.state = OverlayState.IDLE
        self._fade_out_anim: QPropertyAnimation | None = None
        self._setup_window()
        self._setup_ui()
        self._connect_signals()

    def _setup_window(self) -> None:
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._reposition(self.PILL_H_COLLAPSED)

    def _reposition(self, pill_h: int) -> None:
        screen = QApplication.primaryScreen()
        if screen is not None:
            geo = screen.geometry()
            x = (geo.width() - self.PILL_W) // 2
            y = geo.height() - pill_h - self.MARGIN_BOTTOM
        else:
            x, y = 100, 100
        self.setGeometry(x, y, self.PILL_W, pill_h)

    def _setup_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)

        self._pill = QFrame(self)
        self._pill.setObjectName("pill")
        self._pill.setStyleSheet(_PILL_STYLE)
        root_layout.addWidget(self._pill)

        outer = QVBoxLayout(self._pill)
        outer.setContentsMargins(16, 8, 16, 8)
        outer.setSpacing(6)

        # Row 1: status bar (always visible)
        row1 = QHBoxLayout()
        row1.setSpacing(10)

        self._icon = QLabel("●")
        self._icon.setStyleSheet(f"color: {_COLORS['cyan']}; font-size: 10px;")
        row1.addWidget(self._icon)

        self._status = QLabel("JARVIS")
        self._status.setFont(QFont("Consolas", 8))
        self._status.setStyleSheet(f"color: {_COLORS['blue']}; letter-spacing: 2px;")
        row1.addWidget(self._status)
        row1.addStretch()

        self._waveform = WaveformWidget(mode="input")
        row1.addWidget(self._waveform)
        outer.addLayout(row1)

        # Row 2: response text (only in SPEAKING state)
        self._response = TypewriterLabel()
        self._response.setFont(QFont("Consolas", 9))
        self._response.setStyleSheet(f"color: {_COLORS['white']};")
        self._response.setMaximumWidth(self.PILL_W - 48)
        self._response.hide()
        outer.addWidget(self._response)

    def _connect_signals(self) -> None:
        self._bridge.listening_started.connect(self.show_listening)
        self._bridge.processing_started.connect(self.show_processing)
        self._bridge.tool_started.connect(self.show_tool)
        self._bridge.tool_done.connect(self._on_tool_done)
        self._bridge.kai_task_started.connect(self.show_kai)
        self._bridge.response_ready.connect(self.show_speaking)
        self._bridge.speaking_done.connect(self.hide_overlay)
        self._bridge.kai_task_done.connect(self._on_kai_done)
        self._bridge.memory_updated.connect(self._on_memory_updated)

    @pyqtSlot()
    def show_listening(self) -> None:
        self.state = OverlayState.LISTENING
        self._collapse()
        self._status.setText("ESCUCHANDO")
        self._status.setStyleSheet(f"color: {_COLORS['cyan']}; letter-spacing: 2px;")
        self._waveform.mode = "input"
        self._waveform.start()
        from PyQt6.QtCore import QAbstractAnimation
        if (self._fade_out_anim is not None and
                self._fade_out_anim.state() == QAbstractAnimation.State.Running):
            self._fade_out_anim.stop()
            self._fade_out_anim = None
        self.setWindowOpacity(0.0)
        self.show()
        self._fade_in()

    @pyqtSlot()
    def show_processing(self) -> None:
        self.state = OverlayState.PROCESSING
        self._waveform.stop()
        self._status.setText("PROCESANDO...")
        self._status.setStyleSheet(f"color: {_COLORS['blue']}; letter-spacing: 2px;")

    @pyqtSlot(str)
    def show_tool(self, tool_name: str) -> None:
        self.state = OverlayState.TOOL_EXECUTING
        color = _COLORS["violet"] if "Kai" in tool_name else _COLORS["amber"]
        self._status.setText(tool_name)
        self._status.setStyleSheet(f"color: {color}; letter-spacing: 1px;")

    @pyqtSlot(str)
    def _on_tool_done(self, _tool_name: str) -> None:
        self.state = OverlayState.PROCESSING
        self._status.setText("PROCESANDO...")
        self._status.setStyleSheet(f"color: {_COLORS['blue']}; letter-spacing: 2px;")

    @pyqtSlot(str)
    def _on_kai_done(self, _result: str) -> None:
        self.state = OverlayState.PROCESSING
        self._status.setText("PROCESANDO...")
        self._status.setStyleSheet(f"color: {_COLORS['blue']}; letter-spacing: 2px;")

    @pyqtSlot(str)
    def _on_memory_updated(self, _description: str) -> None:
        pass  # notificación informativa, sin cambio de estado visual

    @pyqtSlot(str)
    def show_kai(self, description: str) -> None:
        self.state = OverlayState.KAI_RUNNING
        self._status.setText(f"Kai: {description[:30]}")
        self._status.setStyleSheet(f"color: {_COLORS['violet']}; letter-spacing: 1px;")

    @pyqtSlot(str)
    def show_speaking(self, response: str) -> None:
        self.state = OverlayState.SPEAKING
        self._waveform.mode = "output"
        self._waveform.start()
        self._status.setText("J.A.R.V.I.S.")
        self._status.setStyleSheet(f"color: {_COLORS['cyan']}; letter-spacing: 2px;")
        self._response.show()
        self._expand()
        self._response.start_typing(response)

    @pyqtSlot()
    def hide_overlay(self) -> None:
        from PyQt6.QtCore import QAbstractAnimation
        if (self._fade_out_anim is not None and
                self._fade_out_anim.state() == QAbstractAnimation.State.Running):
            return  # ya se está ocultando
        self._waveform.stop()
        self._fade_out_anim = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade_out_anim.setDuration(300)
        self._fade_out_anim.setStartValue(1.0)
        self._fade_out_anim.setEndValue(0.0)
        self._fade_out_anim.setEasingCurve(QEasingCurve.Type.InCubic)
        self._fade_out_anim.finished.connect(self._do_hide)
        self._fade_out_anim.start()

    def _do_hide(self) -> None:
        self._collapse()
        self._response.hide()
        self.hide()
        self.state = OverlayState.IDLE

    def mousePressEvent(self, _event) -> None:
        if self.state == OverlayState.SPEAKING:
            self._response.skip()
            self.hide_overlay()

    def _fade_in(self) -> None:
        anim = QPropertyAnimation(self, b"windowOpacity", self)
        anim.setDuration(200)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.start()

    def _collapse(self) -> None:
        self._reposition(self.PILL_H_COLLAPSED)

    def _expand(self) -> None:
        self._reposition(self.PILL_H_EXPANDED)
