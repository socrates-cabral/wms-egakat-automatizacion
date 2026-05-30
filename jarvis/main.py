import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass  # pythonw no tiene stdout

import ctypes
import ctypes.wintypes
import logging
import threading
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PyQt6.QtGui import QIcon, QPixmap, QColor
from PyQt6.QtCore import QTimer

from jarvis import voice
from jarvis.ui.bridge import get_bridge
from jarvis.ui.overlay import JarvisOverlay
from jarvis.ui.harness import JarvisHarness

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("jarvis")

# Win32 RegisterHotKey constants
_MOD_WIN       = 0x0008
_MOD_NOREPEAT  = 0x4000
_VK_J          = 0x4A
_VK_ESCAPE     = 0x1B
_WM_HOTKEY     = 0x0312
_HOTKEY_ID_J   = 1
_HOTKEY_ID_ESC = 2


def _start_hotkey_thread(on_trigger, on_quit) -> bool:
    """RegisterHotKey en thread daemon — funciona con tecla Win sin admin.
    Retorna True si Win+J se registró correctamente."""
    result: list[bool] = [False]
    ready = threading.Event()

    def _loop():
        u32 = ctypes.windll.user32
        ok_j   = bool(u32.RegisterHotKey(None, _HOTKEY_ID_J,   _MOD_WIN | _MOD_NOREPEAT, _VK_J))
        ok_esc = bool(u32.RegisterHotKey(None, _HOTKEY_ID_ESC, _MOD_NOREPEAT,             _VK_ESCAPE))
        if not ok_j:
            logger.error("No se pudo registrar Win+J (error %d) — otro programa puede tenerlo ocupado",
                         ctypes.windll.kernel32.GetLastError())
        if not ok_esc:
            logger.warning("No se pudo registrar ESC global")
        result[0] = ok_j
        ready.set()
        msg = ctypes.wintypes.MSG()
        while u32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
            if msg.message == _WM_HOTKEY:
                if msg.wParam == _HOTKEY_ID_J:
                    on_trigger()
                elif msg.wParam == _HOTKEY_ID_ESC:
                    on_quit()
        u32.UnregisterHotKey(None, _HOTKEY_ID_J)
        u32.UnregisterHotKey(None, _HOTKEY_ID_ESC)

    t = threading.Thread(target=_loop, daemon=True, name="hotkey-listener")
    t.start()
    ready.wait(timeout=1.0)
    return result[0]


def _make_tray_icon(app: QApplication, on_quit) -> QSystemTrayIcon:
    """Ícono azul cyan en la bandeja. Click derecho → Salir."""
    px = QPixmap(16, 16)
    px.fill(QColor("#00d4ff"))
    icon = QIcon(px)

    tray = QSystemTrayIcon(icon, app)
    menu = QMenu()
    menu.addAction("J.A.R.V.I.S.").setEnabled(False)
    menu.addSeparator()
    menu.addAction("Salir", on_quit)
    tray.setContextMenu(menu)
    tray.setToolTip("J.A.R.V.I.S. — Win+J para hablar")
    tray.show()
    return tray


def main() -> None:
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    bridge = get_bridge()
    overlay = JarvisOverlay(bridge)
    harness = JarvisHarness(bridge)

    def _quit():
        QTimer.singleShot(0, app.quit)

    tray = _make_tray_icon(app, _quit)  # noqa: F841 — keeps tray alive

    logger.info("J.A.R.V.I.S. iniciando... (Win+J para hablar, ESC para salir)")

    voice.play_startup()
    harness.start()

    def _saludo_inicial():
        from datetime import datetime
        from zoneinfo import ZoneInfo
        from jarvis.tools import get_estado_sistema
        CL_TZ = ZoneInfo("America/Santiago")
        estado = get_estado_sistema()
        hora = datetime.now(CL_TZ).strftime("%H:%M")
        clima = estado.get("clima_santiago", "")
        clima_str = f", {clima}" if clima and clima != "sin datos" else ""
        saludo = (
            f"Sistemas en linea. Son las {hora} en Santiago{clima_str}. "
            f"A sus ordenes, Senor Socrates."
        )
        logger.info(f"JARVIS: {saludo}")
        voice.speak(saludo)

    hotkey_ok = _start_hotkey_thread(
        on_trigger=harness.trigger,
        on_quit=_quit,
    )
    if not hotkey_ok:
        tray.showMessage("JARVIS", "Win+J no disponible — otro programa lo usa.\nCambia el hotkey en config.py", QSystemTrayIcon.MessageIcon.Warning, 5000)

    tray.showMessage("JARVIS online", "Win+J para hablar | ESC para salir", QSystemTrayIcon.MessageIcon.Information, 3000)

    QTimer.singleShot(500, _saludo_inicial)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
