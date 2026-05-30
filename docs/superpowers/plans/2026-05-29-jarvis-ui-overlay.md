# J.A.R.V.I.S. UI Overlay Harness — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Agregar una UI overlay pill en PyQt6 que actúa como harness orquestador de Jarvis — invisible en reposo, aparece al activarse (Win+J), muestra estado de tools en tiempo real, texto de respuesta typewriter, y lee/escribe el sistema de memoria de Claude Code.

**Architecture:** `ui/harness.py` reemplaza el ciclo de `main.py` y orquesta STT → Gemini → tools → TTS. La comunicación thread-safe pasa por `JarvisBridge` (signals Qt). `ui/memory.py` lee `memory/MEMORY.md` al iniciar para inyectar contexto real en el system prompt. Cada tool emite señales de inicio/fin que el overlay muestra.

**Tech Stack:** PyQt6 6.6+, pytest-qt, Python 3.14. Código existente (agent.py, voice.py, config.py, tools.py) se modifica mínimamente — sin cambios de firma.

---

## File Map

| Archivo | Acción | Responsabilidad |
|---------|--------|-----------------|
| `jarvis/ui/__init__.py` | Crear | Paquete UI |
| `jarvis/ui/bridge.py` | Crear | `JarvisBridge(QObject)` singleton — signals thread-safe |
| `jarvis/ui/memory.py` | Crear | `MemoryClient` — load context desde memory/, persist sessions |
| `jarvis/ui/animations.py` | Crear | `WaveformWidget`, `TypewriterLabel` |
| `jarvis/ui/overlay.py` | Crear | `JarvisOverlay(QWidget)` — pill frameless, todos los estados |
| `jarvis/ui/harness.py` | Crear | `JarvisHarness` — orquestador del ciclo STT→agent→TTS |
| `jarvis/tools.py` | Modificar | Agregar `_notify_bridge()` al inicio/fin de cada tool |
| `jarvis/main.py` | Modificar | Reemplazar `keyboard.wait("esc")` loop por `QApplication.exec()` |
| `jarvis/requirements.txt` | Modificar | Agregar `PyQt6>=6.6.0` y `pytest-qt>=4.0` |
| `jarvis/tests/test_bridge.py` | Crear | Tests del bridge |
| `jarvis/tests/test_memory.py` | Crear | Tests del MemoryClient |
| `jarvis/tests/test_animations.py` | Crear | Tests de widgets de animación |
| `jarvis/tests/test_overlay.py` | Crear | Tests de estados del overlay |

---

## Task 0: Instalar dependencias + scaffold

**Files:**
- Modify: `jarvis/requirements.txt`
- Create: `jarvis/tests/__init__.py`
- Create: `jarvis/ui/__init__.py`

- [ ] **Step 1: Instalar PyQt6 y pytest-qt**

```bash
py -m pip install "PyQt6>=6.6.0" "pytest-qt>=4.0"
```

Verificar:
```bash
py -c "from PyQt6.QtWidgets import QApplication; print('PyQt6 OK')"
```
Expected: `PyQt6 OK`

- [ ] **Step 2: Actualizar requirements.txt**

Agregar al final de `jarvis/requirements.txt`:
```
PyQt6>=6.6.0
pytest-qt>=4.0
```

- [ ] **Step 3: Crear directorios**

```bash
mkdir jarvis\ui jarvis\tests
```

- [ ] **Step 4: Crear __init__.py vacíos**

`jarvis/ui/__init__.py` — archivo vacío.

`jarvis/tests/__init__.py` — archivo vacío.

- [ ] **Step 5: Commit**

```bash
git add jarvis/requirements.txt jarvis/ui/__init__.py jarvis/tests/__init__.py
git commit -m "feat(jarvis-ui): scaffold ui/ y tests/ + deps PyQt6"
```

---

## Task 1: Bridge — signals singleton

**Files:**
- Create: `jarvis/ui/bridge.py`
- Create: `jarvis/tests/test_bridge.py`

- [ ] **Step 1: Escribir el test**

`jarvis/tests/test_bridge.py`:
```python
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


def test_get_bridge_returns_singleton():
    b1 = get_bridge()
    b2 = get_bridge()
    assert b1 is b2


def test_get_bridge_is_jarvis_bridge():
    assert isinstance(get_bridge(), JarvisBridge)
```

- [ ] **Step 2: Ejecutar — verificar que falla**

```bash
cd C:\ClaudeWork && py -m pytest jarvis/tests/test_bridge.py -v
```

Expected: `ModuleNotFoundError: No module named 'jarvis.ui.bridge'`

- [ ] **Step 3: Implementar bridge.py**

`jarvis/ui/bridge.py`:
```python
from PyQt6.QtCore import QObject, pyqtSignal

class JarvisBridge(QObject):
    listening_started  = pyqtSignal()
    processing_started = pyqtSignal()
    tool_started       = pyqtSignal(str)   # nombre del tool con emoji
    tool_done          = pyqtSignal(str)
    kai_task_started   = pyqtSignal(str)   # descripción tarea Kai
    kai_task_done      = pyqtSignal(str)   # resultado Kai
    response_ready     = pyqtSignal(str)   # texto completo respuesta
    speaking_done      = pyqtSignal()
    memory_updated     = pyqtSignal(str)   # descripción de qué se guardó

_bridge: "JarvisBridge | None" = None

def get_bridge() -> JarvisBridge:
    global _bridge
    if _bridge is None:
        _bridge = JarvisBridge()
    return _bridge
```

- [ ] **Step 4: Ejecutar — verificar que pasa**

```bash
py -m pytest jarvis/tests/test_bridge.py -v
```

Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add jarvis/ui/bridge.py jarvis/tests/test_bridge.py
git commit -m "feat(jarvis-ui): JarvisBridge singleton con signals Qt"
```

---

## Task 2: MemoryClient — memoria persistente

**Files:**
- Create: `jarvis/ui/memory.py`
- Create: `jarvis/tests/test_memory.py`

- [ ] **Step 1: Escribir los tests**

`jarvis/tests/test_memory.py`:
```python
from pathlib import Path
import pytest
from jarvis.ui.memory import MemoryClient


def test_load_context_returns_file_content(tmp_path):
    memory_dir = tmp_path / "memory"
    memory_dir.mkdir()
    (memory_dir / "user_profile.md").write_text(
        "---\nname: test\n---\n\nSócrates es Head of Control Management.",
        encoding="utf-8",
    )
    client = MemoryClient(memory_dir=memory_dir, priority_files=["user_profile.md"])
    ctx = client.load_context()
    assert "Sócrates es Head of Control Management." in ctx


def test_load_context_strips_frontmatter(tmp_path):
    memory_dir = tmp_path / "memory"
    memory_dir.mkdir()
    (memory_dir / "user_profile.md").write_text(
        "---\nname: test\ntype: user\n---\n\nContenido real.",
        encoding="utf-8",
    )
    client = MemoryClient(memory_dir=memory_dir, priority_files=["user_profile.md"])
    ctx = client.load_context()
    assert "---" not in ctx
    assert "Contenido real." in ctx


def test_load_context_skips_missing_files(tmp_path):
    memory_dir = tmp_path / "memory"
    memory_dir.mkdir()
    client = MemoryClient(memory_dir=memory_dir, priority_files=["no_existe.md"])
    ctx = client.load_context()
    assert ctx == ""


def test_persist_session_writes_file(tmp_path):
    memory_dir = tmp_path / "memory"
    memory_dir.mkdir()
    client = MemoryClient(memory_dir=memory_dir)
    client.persist_session("jarvis_session_test.md", "Contenido de sesión.")
    result = (memory_dir / "jarvis_session_test.md").read_text(encoding="utf-8")
    assert "Contenido de sesión." in result


def test_persist_session_overwrites_existing(tmp_path):
    memory_dir = tmp_path / "memory"
    memory_dir.mkdir()
    client = MemoryClient(memory_dir=memory_dir)
    client.persist_session("note.md", "Primera versión.")
    client.persist_session("note.md", "Segunda versión.")
    result = (memory_dir / "note.md").read_text(encoding="utf-8")
    assert "Segunda versión." in result
    assert "Primera versión." not in result
```

- [ ] **Step 2: Ejecutar — verificar que falla**

```bash
py -m pytest jarvis/tests/test_memory.py -v
```

Expected: `ModuleNotFoundError: No module named 'jarvis.ui.memory'`

- [ ] **Step 3: Implementar memory.py**

`jarvis/ui/memory.py`:
```python
import re
import logging
from pathlib import Path

logger = logging.getLogger("jarvis.ui.memory")

_DEFAULT_MEMORY_DIR = Path(r"C:\Users\Socrates Cabral\.claude\projects\C--ClaudeWork\memory")

_DEFAULT_PRIORITY_FILES = [
    "user_profile.md",
    "crypto_estrategia_bot.md",
    "project_kpi_ops.md",
    "project_agente_apuestas.md",
    "project_jarvis.md",
    "project_mirofish.md",
]

_FRONTMATTER_RE = re.compile(r"^---.*?---\s*", re.DOTALL)


class MemoryClient:
    def __init__(
        self,
        memory_dir: Path = _DEFAULT_MEMORY_DIR,
        priority_files: list[str] | None = None,
    ):
        self.memory_dir = memory_dir
        self.priority_files = priority_files if priority_files is not None else _DEFAULT_PRIORITY_FILES

    def load_context(self) -> str:
        """Lee los archivos de memoria prioritarios y retorna un bloque de contexto."""
        blocks: list[str] = []
        for fname in self.priority_files:
            path = self.memory_dir / fname
            if not path.exists():
                continue
            try:
                raw = path.read_text(encoding="utf-8")
                content = _FRONTMATTER_RE.sub("", raw).strip()
                if content:
                    blocks.append(f"[{fname}]\n{content}")
            except Exception as e:
                logger.warning(f"No se pudo leer {fname}: {e}")
        return "\n\n".join(blocks)

    def persist_session(self, filename: str, content: str) -> None:
        """Escribe o sobreescribe un archivo en el directorio de memoria."""
        path = self.memory_dir / filename
        try:
            path.write_text(content, encoding="utf-8")
            logger.info(f"Memory persistida: {filename}")
        except Exception as e:
            logger.error(f"Error persistiendo {filename}: {e}")
```

- [ ] **Step 4: Ejecutar — verificar que pasa**

```bash
py -m pytest jarvis/tests/test_memory.py -v
```

Expected: `5 passed`

- [ ] **Step 5: Commit**

```bash
git add jarvis/ui/memory.py jarvis/tests/test_memory.py
git commit -m "feat(jarvis-ui): MemoryClient — load/persist memoria Claude Code"
```

---

## Task 3: Animations — WaveformWidget y TypewriterLabel

**Files:**
- Create: `jarvis/ui/animations.py`
- Create: `jarvis/tests/test_animations.py`

- [ ] **Step 1: Escribir los tests**

`jarvis/tests/test_animations.py`:
```python
import pytest
from jarvis.ui.animations import TypewriterLabel, WaveformWidget


def test_typewriter_starts_empty(qtbot):
    label = TypewriterLabel()
    label.start_typing("Hola")
    assert label.text() == "" or len(label.text()) < 5  # empieza vacío o con pocos chars


def test_typewriter_emits_finished(qtbot):
    label = TypewriterLabel()
    with qtbot.waitSignal(label.finished, timeout=2000):
        label.start_typing("Hi")


def test_typewriter_shows_full_text_on_finish(qtbot):
    label = TypewriterLabel()
    with qtbot.waitSignal(label.finished, timeout=2000):
        label.start_typing("Hola mundo")
    assert label.text() == "Hola mundo"


def test_typewriter_skip_shows_full_text(qtbot):
    label = TypewriterLabel()
    label.start_typing("Texto largo aquí")
    label.skip()
    assert label.text() == "Texto largo aquí"


def test_waveform_can_start_and_stop(qtbot):
    waveform = WaveformWidget(mode="input")
    waveform.start()
    qtbot.wait(100)
    waveform.stop()  # no debe lanzar excepción


def test_waveform_has_correct_mode(qtbot):
    w = WaveformWidget(mode="output")
    assert w.mode == "output"
```

- [ ] **Step 2: Ejecutar — verificar que falla**

```bash
py -m pytest jarvis/tests/test_animations.py -v
```

Expected: `ModuleNotFoundError: No module named 'jarvis.ui.animations'`

- [ ] **Step 3: Implementar animations.py**

`jarvis/ui/animations.py`:
```python
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
        self._timer.start(33)  # ~30 chars/s

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
```

- [ ] **Step 4: Ejecutar — verificar que pasa**

```bash
py -m pytest jarvis/tests/test_animations.py -v
```

Expected: `6 passed`

- [ ] **Step 5: Commit**

```bash
git add jarvis/ui/animations.py jarvis/tests/test_animations.py
git commit -m "feat(jarvis-ui): WaveformWidget + TypewriterLabel"
```

---

## Task 4: Overlay — pill QWidget con todos los estados

**Files:**
- Create: `jarvis/ui/overlay.py`
- Create: `jarvis/tests/test_overlay.py`

- [ ] **Step 1: Escribir los tests**

`jarvis/tests/test_overlay.py`:
```python
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
```

- [ ] **Step 2: Ejecutar — verificar que falla**

```bash
py -m pytest jarvis/tests/test_overlay.py -v
```

Expected: `ModuleNotFoundError: No module named 'jarvis.ui.overlay'`

- [ ] **Step 3: Implementar overlay.py**

`jarvis/ui/overlay.py`:
```python
import sys
sys.stdout.reconfigure(encoding="utf-8")

from enum import Enum, auto

from PyQt6.QtWidgets import (
    QWidget, QFrame, QLabel, QHBoxLayout, QVBoxLayout, QApplication, QSizePolicy,
)
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QRect, pyqtSlot
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
    "dim":    "#8b949e",
}


class JarvisOverlay(QWidget):
    PILL_W   = 360
    PILL_H_COLLAPSED = 52
    PILL_H_EXPANDED  = 120
    MARGIN_BOTTOM    = 48

    def __init__(self, bridge: JarvisBridge):
        super().__init__()
        self._bridge = bridge
        self.state = OverlayState.IDLE
        self._setup_window()
        self._setup_ui()
        self._connect_signals()
        self._fade_timer = QTimer(self)
        self._fade_timer.setSingleShot(True)
        self._fade_timer.timeout.connect(self._do_hide)

    # ── Window setup ──────────────────────────────────────────────────────────

    def _setup_window(self) -> None:
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._reposition(self.PILL_H_COLLAPSED)

    def _reposition(self, pill_h: int) -> None:
        screen = QApplication.primaryScreen().geometry()
        x = (screen.width() - self.PILL_W) // 2
        y = screen.height() - pill_h - self.MARGIN_BOTTOM
        self.setGeometry(x, y, self.PILL_W, pill_h)

    # ── UI setup ──────────────────────────────────────────────────────────────

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

        # ── Row 1: status bar (always visible) ────────────────────────────
        row1 = QHBoxLayout()
        row1.setSpacing(10)

        self._icon = QLabel("●")
        self._icon.setStyleSheet(f"color: {_COLORS['cyan']}; font-size: 10px;")
        row1.addWidget(self._icon)

        self._status = QLabel("JARVIS")
        font = QFont("Consolas", 8)
        self._status.setFont(font)
        self._status.setStyleSheet(
            f"color: {_COLORS['blue']}; letter-spacing: 2px;"
        )
        row1.addWidget(self._status)
        row1.addStretch()

        self._waveform = WaveformWidget(mode="input")
        row1.addWidget(self._waveform)
        outer.addLayout(row1)

        # ── Row 2: response text (visible in SPEAKING state) ──────────────
        self._response = TypewriterLabel()
        self._response.setFont(QFont("Consolas", 9))
        self._response.setStyleSheet(f"color: {_COLORS['white']};")
        self._response.setMaximumWidth(self.PILL_W - 48)
        self._response.hide()
        outer.addWidget(self._response)

    # ── Signal connections ────────────────────────────────────────────────────

    def _connect_signals(self) -> None:
        self._bridge.listening_started.connect(self.show_listening)
        self._bridge.processing_started.connect(self.show_processing)
        self._bridge.tool_started.connect(self.show_tool)
        self._bridge.tool_done.connect(self._on_tool_done)
        self._bridge.kai_task_started.connect(self.show_kai)
        self._bridge.response_ready.connect(self.show_speaking)
        self._bridge.speaking_done.connect(self.hide_overlay)

    # ── State transitions ─────────────────────────────────────────────────────

    @pyqtSlot()
    def show_listening(self) -> None:
        self.state = OverlayState.LISTENING
        self._collapse()
        self._status.setText("ESCUCHANDO")
        self._status.setStyleSheet(f"color: {_COLORS['cyan']}; letter-spacing: 2px;")
        self._waveform.mode = "input"
        self._waveform.start()
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
    def show_kai(self, description: str) -> None:
        self.state = OverlayState.KAI_RUNNING
        self._status.setText(f"🤖 Kai: {description[:30]}")
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
        self._waveform.stop()
        self._fade_timer.start(300)

    def _do_hide(self) -> None:
        self._collapse()
        self._response.hide()
        self.hide()
        self.state = OverlayState.IDLE

    def mousePressEvent(self, _event) -> None:
        if self.state == OverlayState.SPEAKING:
            self._response.skip()
            self.hide_overlay()

    # ── Helpers ───────────────────────────────────────────────────────────────

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
```

- [ ] **Step 4: Ejecutar — verificar que pasa**

```bash
py -m pytest jarvis/tests/test_overlay.py -v
```

Expected: `6 passed`

- [ ] **Step 5: Commit**

```bash
git add jarvis/ui/overlay.py jarvis/tests/test_overlay.py
git commit -m "feat(jarvis-ui): JarvisOverlay pill — 6 estados con animaciones"
```

---

## Task 5: Harness — orquestador del ciclo

**Files:**
- Create: `jarvis/ui/harness.py`

No tests de harness — depende de STT/TTS/micrófono real. El overlay y el bridge ya están testeados; el harness es glue code entre ellos.

- [ ] **Step 1: Implementar harness.py**

`jarvis/ui/harness.py`:
```python
import sys
sys.stdout.reconfigure(encoding="utf-8")

import logging
import threading
from datetime import datetime
from zoneinfo import ZoneInfo

from PyQt6.QtCore import QObject

from jarvis import voice
from jarvis.agent import Agent
from jarvis.config import HOTKEY
from jarvis.ui.bridge import JarvisBridge
from jarvis.ui.memory import MemoryClient

logger = logging.getLogger("jarvis.ui.harness")
CL_TZ = ZoneInfo("America/Santiago")


class JarvisHarness(QObject):
    """Orquestador del ciclo STT → Gemini → tools → TTS.
    Corre el ciclo en un thread para no bloquear el event loop de Qt.
    """

    def __init__(self, bridge: JarvisBridge):
        super().__init__()
        self._bridge = bridge
        self._memory = MemoryClient()
        self._agent: Agent | None = None
        self._active = False
        self._lock = threading.Lock()

    def start(self) -> None:
        """Inicializa el agente con contexto de memoria. Llamar una vez al arrancar."""
        context = self._memory.load_context()
        self._agent = Agent(memory_context=context)
        logger.info("Harness inicializado. Contexto de memoria cargado.")

    def trigger(self) -> None:
        """Lanza un ciclo STT → agente → TTS en un thread separado."""
        with self._lock:
            if self._active:
                return
            self._active = True
        t = threading.Thread(target=self._cycle, daemon=True)
        t.start()

    def _cycle(self) -> None:
        try:
            self._bridge.listening_started.emit()
            text = voice.listen()
            if not text:
                voice.speak("No escuché nada, Señor Sócrates.")
                self._bridge.speaking_done.emit()
                return

            self._bridge.processing_started.emit()
            response = self._agent.process_message(text)

            self._bridge.response_ready.emit(response)
            voice.speak(response)
            self._bridge.speaking_done.emit()

            if any(w in text.lower() for w in ("hasta luego", "apágate", "cierra")):
                from PyQt6.QtWidgets import QApplication
                QApplication.quit()
        except Exception as e:
            logger.error(f"Cycle error: {e}")
            voice.speak("Error inesperado, Señor Sócrates.")
            self._bridge.speaking_done.emit()
        finally:
            with self._lock:
                self._active = False
```

- [ ] **Step 2: Actualizar Agent para aceptar memory_context**

`jarvis/agent.py` — agregar el parámetro `memory_context` al `__init__`:

```python
# Reemplazar:
def __init__(self):
    self._client = genai.Client(api_key=GOOGLE_API_KEY)
    self._config = types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        ...
    )

# Con:
def __init__(self, memory_context: str = ""):
    self._client = genai.Client(api_key=GOOGLE_API_KEY)
    system = SYSTEM_PROMPT
    if memory_context:
        system = f"{SYSTEM_PROMPT}\n\n## Contexto de memoria\n{memory_context}"
    self._config = types.GenerateContentConfig(
        system_instruction=system,
        tools=TOOLS,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=False),
    )
    self._history: list = []
```

- [ ] **Step 3: Verificar que los tests existentes siguen pasando**

```bash
py -m pytest jarvis/ -v --ignore=jarvis/tests/test_overlay.py
```

Expected: todos los tests anteriores en verde.

- [ ] **Step 4: Commit**

```bash
git add jarvis/ui/harness.py jarvis/agent.py
git commit -m "feat(jarvis-ui): JarvisHarness orquestador + Agent acepta memory_context"
```

---

## Task 6: tools.py — notificaciones al bridge

**Files:**
- Modify: `jarvis/tools.py`

- [ ] **Step 1: Agregar helper _notify_bridge al inicio de tools.py**

Agregar después de las importaciones existentes en `jarvis/tools.py` (después de `logger = ...`):

```python
def _notify_bridge(signal: str, message: str = "") -> None:
    """Emite un signal del bridge si Qt está disponible. No falla si no lo está."""
    try:
        from jarvis.ui.bridge import get_bridge
        bridge = get_bridge()
        sig = getattr(bridge, signal)
        if message:
            sig.emit(message)
        else:
            sig.emit()
    except Exception:
        pass
```

- [ ] **Step 2: Agregar notificaciones a cada tool**

En `get_estado_sistema()`, al inicio y al final:
```python
def get_estado_sistema() -> dict:
    _notify_bridge("tool_started", "🌐 Consultando sistema...")
    # ... código existente sin cambios ...
    _notify_bridge("tool_done", "🌐 Sistema")
    return {"hora": hora_str, "clima_santiago": clima, "btc": btc, "eth": eth}
```

En `get_wms_kpi()`:
```python
def get_wms_kpi() -> dict:
    _notify_bridge("tool_started", "📊 Leyendo WMS KPI...")
    # ... código existente ...
    _notify_bridge("tool_done", "📊 WMS KPI")
    return ...
```

En `get_apuestas()`:
```python
def get_apuestas() -> dict:
    _notify_bridge("tool_started", "⚽ Consultando apuestas...")
    # ... código existente ...
    _notify_bridge("tool_done", "⚽ Apuestas")
    return ...
```

En `abrir_aplicacion()`:
```python
def abrir_aplicacion(nombre: str) -> str:
    _notify_bridge("tool_started", f"🖥 Abriendo {nombre}...")
    # ... código existente ...
    _notify_bridge("tool_done", "🖥 App")
    return ...
```

En `set_timer()`:
```python
def set_timer(minutos: int, mensaje: str = "Tiempo cumplido") -> str:
    _notify_bridge("tool_started", f"⏱ Timer {minutos}min...")
    # ... código existente ...
    _notify_bridge("tool_done", "⏱ Timer")
    return ...
```

En `tomar_nota()`:
```python
def tomar_nota(texto: str) -> str:
    _notify_bridge("tool_started", "📝 Guardando nota...")
    # ... código existente ...
    _notify_bridge("tool_done", "📝 Nota")
    return ...
```

En `invoke_claude()`:
```python
def invoke_claude(pregunta: str) -> str:
    _notify_bridge("kai_task_started", pregunta[:40])
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        msg = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=1024,
            system=(
                "Eres un asistente técnico experto en el stack de Sócrates Cabral "
                "(Python, Playwright, Streamlit, crypto bot grid trading, WMS Egakat). "
                "Responde de forma concisa en español."
            ),
            messages=[{"role": "user", "content": pregunta}],
        )
        resultado = msg.content[0].text
    except Exception as e:
        resultado = f"Error escalando a Claude: {e}"
    _notify_bridge("kai_task_done", resultado[:40])
    return resultado
```

- [ ] **Step 3: Verificar que tests existentes siguen pasando**

```bash
py -m pytest jarvis/ -v
```

Expected: todos los tests en verde. La función `_notify_bridge` falla silenciosamente sin Qt.

- [ ] **Step 4: Commit**

```bash
git add jarvis/tools.py
git commit -m "feat(jarvis-ui): tools emiten bridge signals — tool_started/done"
```

---

## Task 7: main.py — reemplazar loop por QApplication

**Files:**
- Modify: `jarvis/main.py`

- [ ] **Step 1: Reemplazar main.py**

`jarvis/main.py` (reemplazar completo):

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

import logging
import keyboard
from PyQt6.QtWidgets import QApplication

from jarvis.config import HOTKEY
from jarvis import voice
from jarvis.ui.bridge import get_bridge
from jarvis.ui.overlay import JarvisOverlay
from jarvis.ui.harness import JarvisHarness

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("jarvis")


def main() -> None:
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # overlay oculto no cierra la app

    bridge = get_bridge()
    overlay = JarvisOverlay(bridge)
    harness = JarvisHarness(bridge)

    print("=" * 50)
    print("  J.A.R.V.I.S. — Iniciando...")
    print(f"  Hotkey: {HOTKEY.upper()}")
    print("  ESC para salir")
    print("=" * 50)

    voice.play_startup()
    harness.start()

    # Saludo inicial
    from datetime import datetime
    from zoneinfo import ZoneInfo
    CL_TZ = ZoneInfo("America/Santiago")
    from jarvis.tools import get_estado_sistema
    estado = get_estado_sistema()
    hora = datetime.now(CL_TZ).strftime("%H:%M")
    clima = estado.get("clima_santiago", "")
    clima_str = f", {clima}" if clima and clima != "sin datos" else ""
    saludo = f"Sistemas en línea. Son las {hora} en Santiago{clima_str}. A sus órdenes, Señor Sócrates."
    print(f"\nJARVIS: {saludo}\n")
    voice.speak(saludo)

    keyboard.add_hotkey(HOTKEY, harness.trigger)
    keyboard.add_hotkey("esc", app.quit)
    print(f"En espera. Presiona {HOTKEY.upper()} para hablar.\n")

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Ejecutar Jarvis y verificar comportamiento**

```bash
py jarvis/main.py
```

Verificar:
1. Arranca sin errores — startup sound reproduce
2. Overlay NO visible en reposo
3. Win+J → pill aparece en bottom-center con "ESCUCHANDO" y waveform
4. Hablar → waveform activa, luego "PROCESANDO..."
5. Tool ejecuta → pill muestra nombre en ámbar
6. Respuesta → pill expande con texto typewriter
7. TTS termina → pill desaparece con fade
8. ESC → cierra limpiamente

- [ ] **Step 3: Ejecutar todos los tests finales**

```bash
py -m pytest jarvis/ -v
```

Expected: todos los tests en verde.

- [ ] **Step 4: Commit final**

```bash
git add jarvis/main.py
git commit -m "feat(jarvis-ui): main.py — QApplication harness, overlay activo"
```

---

## Resumen de archivos creados/modificados

| Archivo | Estado |
|---------|--------|
| `jarvis/ui/__init__.py` | Nuevo |
| `jarvis/ui/bridge.py` | Nuevo |
| `jarvis/ui/memory.py` | Nuevo |
| `jarvis/ui/animations.py` | Nuevo |
| `jarvis/ui/overlay.py` | Nuevo |
| `jarvis/ui/harness.py` | Nuevo |
| `jarvis/tests/__init__.py` | Nuevo |
| `jarvis/tests/test_bridge.py` | Nuevo |
| `jarvis/tests/test_memory.py` | Nuevo |
| `jarvis/tests/test_animations.py` | Nuevo |
| `jarvis/tests/test_overlay.py` | Nuevo |
| `jarvis/agent.py` | Modificado (memory_context param) |
| `jarvis/tools.py` | Modificado (_notify_bridge en cada tool) |
| `jarvis/main.py` | Modificado (QApplication + harness) |
| `jarvis/requirements.txt` | Modificado (PyQt6, pytest-qt) |
