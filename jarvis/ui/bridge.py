import threading

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
_bridge_lock = threading.Lock()


def get_bridge() -> JarvisBridge:
    global _bridge
    if _bridge is None:
        with _bridge_lock:
            if _bridge is None:
                _bridge = JarvisBridge()
    return _bridge
