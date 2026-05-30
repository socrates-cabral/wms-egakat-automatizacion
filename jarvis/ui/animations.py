import random
from PyQt6.QtWidgets import QLabel, QWidget
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QPainter, QColor


class WaveformWidget(QWidget):
    NUM_BARS = 7
    BAR_W = 3
    GAP = 5

    def __init__(self, parent=None, mode: str = "input"):
        super().__init__(parent)
        self.mode = mode
        self._heights = [0.3] * self.NUM_BARS
        self._targets = [0.3] * self.NUM_BARS
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._animate)
        total_w = self.NUM_BARS * self.GAP - (self.GAP - self.BAR_W)
        self.setFixedSize(total_w, 20)

    def start(self) -> None:
        self._timer.start(60)

    def stop(self) -> None:
        self._timer.stop()
        self._heights = [0.2] * self.NUM_BARS
        self.update()

    def _animate(self) -> None:
        for i in range(self.NUM_BARS):
            if random.random() < 0.3:
                self._targets[i] = random.uniform(0.15, 1.0)
            self._heights[i] += (self._targets[i] - self._heights[i]) * 0.35
        self.update()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = QColor("#00d4ff") if self.mode == "input" else QColor("#4a9eff")
        painter.setBrush(color)
        painter.setPen(Qt.PenStyle.NoPen)
        total_w = self.NUM_BARS * self.GAP - (self.GAP - self.BAR_W)
        start_x = (self.width() - total_w) // 2
        for i, h in enumerate(self._heights):
            bar_h = max(2, int(h * self.height()))
            x = start_x + i * self.GAP
            y = (self.height() - bar_h) // 2
            painter.drawRoundedRect(x, y, self.BAR_W, bar_h, 1, 1)


class TypewriterLabel(QLabel):
    finished = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._full_text = ""
        self._pos = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self.setWordWrap(True)

    def start_typing(self, text: str) -> None:
        self._full_text = text
        self._pos = 0
        self.setText("")
        self._timer.start(33)

    def skip(self) -> None:
        self._timer.stop()
        self.setText(self._full_text)
        self.finished.emit()

    def _tick(self) -> None:
        self._pos += 1
        self.setText(self._full_text[: self._pos])
        if self._pos >= len(self._full_text):
            self._timer.stop()
            self.finished.emit()
