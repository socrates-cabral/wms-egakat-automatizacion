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
import traceback
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


def _install_crash_diagnostics() -> None:
    """[DIAG temporal] Captura cualquier salida/excepción no manejada.

    PyQt6 aborta la app ante excepciones no atrapadas en slots; estos hooks
    las dejan registradas en vez de morir en silencio.
    """
    def _excepthook(exc_type, exc, tb):
        logger.error("UNHANDLED EXCEPTION:\n%s",
                     "".join(traceback.format_exception(exc_type, exc, tb)))
    sys.excepthook = _excepthook

    def _thread_excepthook(args):
        logger.error("UNHANDLED THREAD EXCEPTION in %s:\n%s",
                     args.thread.name if args.thread else "?",
                     "".join(traceback.format_exception(
                         args.exc_type, args.exc_value, args.exc_traceback)))
    threading.excepthook = _thread_excepthook

    def _unraisablehook(args):
        logger.error("UNRAISABLE: %s | obj=%r", args.exc_value, args.object)
    sys.unraisablehook = _unraisablehook

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
        logger.info("Hotkeys registrados: Win+J=%s ESC=%s", ok_j, ok_esc)
        msg = ctypes.wintypes.MSG()
        while True:
            ret = u32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if ret == 0:      # WM_QUIT
                logger.warning("Hotkey loop: GetMessageW devolvió WM_QUIT")
                break
            if ret == -1:     # error
                logger.error("Hotkey loop: GetMessageW error %d",
                             ctypes.windll.kernel32.GetLastError())
                break
            if msg.message == _WM_HOTKEY:
                logger.info("WM_HOTKEY recibido wParam=%s", msg.wParam)
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
    _install_crash_diagnostics()
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.aboutToQuit.connect(lambda: logger.warning("app.aboutToQuit emitido"))
    app.aboutToQuit.connect(harness.stop_wakeword)

    bridge = get_bridge()
    overlay = JarvisOverlay(bridge)
    harness = JarvisHarness(bridge)

    def _quit():
        # [DIAG temporal] registrar QUIÉN pide salir
        logger.warning("_quit() llamado desde:\n%s", "".join(traceback.format_stack()))
        QTimer.singleShot(0, app.quit)

    tray = _make_tray_icon(app, _quit)  # noqa: F841 — keeps tray alive

    logger.info("J.A.R.V.I.S. iniciando... (Win+J para hablar, ESC para salir)")

    harness.start()

    def _startup_sequence():
        """Secuencia de arranque sin solapamiento:
        1. Prefetch clima en paralelo mientras suena el startup.mp3.
        2. Cuando el sonido termina, ya tenemos clima → hablar sin superposición.
        """
        from datetime import datetime
        from zoneinfo import ZoneInfo
        from jarvis.tools import get_estado_sistema
        CL_TZ = ZoneInfo("America/Santiago")

        estado_holder: list = [{}]

        def _fetch_clima():
            estado_holder[0] = get_estado_sistema()

        fetch_t = threading.Thread(target=_fetch_clima, daemon=True)
        fetch_t.start()

        voice.play_startup()          # bloquea hasta que startup.mp3 termina

        fetch_t.join(timeout=4.0)     # espera clima (generalmente ya terminó)

        estado = estado_holder[0]
        hora = datetime.now(CL_TZ).strftime("%H:%M")
        clima = estado.get("clima_santiago", "")
        clima_str = f", {clima}" if clima and clima != "sin datos" else ""
        saludo = (
            f"Sistemas en linea. Son las {hora} en Santiago{clima_str}. "
            f"A sus ordenes, Senor Socrates."
        )
        logger.info("JARVIS: %s", saludo)
        voice.speak(saludo)

    threading.Thread(target=_startup_sequence, daemon=True).start()

    hotkey_ok = _start_hotkey_thread(
        on_trigger=harness.trigger,
        on_quit=_quit,
    )
    if not hotkey_ok:
        tray.showMessage("JARVIS", "Win+J no disponible — otro programa lo usa.\nCambia el hotkey en config.py", QSystemTrayIcon.MessageIcon.Warning, 5000)

    tray.showMessage("JARVIS online", "Win+J para hablar | ESC para salir", QSystemTrayIcon.MessageIcon.Information, 3000)

    rc = app.exec()
    logger.warning("app.exec() retornó con código %s — la app va a cerrar", rc)
    sys.exit(rc)


if __name__ == "__main__":
    # Lanzado como ARCHIVO (`py jarvis\main.py`). En esta máquina eso impide
    # abrir el micrófono WASAPI (-9996). Hay que arrancar con start.bat, que
    # usa `py -c "from jarvis.main import main; main()"`.
    print("=" * 64)
    print("  ⚠  JARVIS lanzado como archivo: el MICRÓFONO NO funcionará.")
    print("     Cerrá esto y arrancá con:  jarvis\\start.bat")
    print("     (o:  py -c \"from jarvis.main import main; main()\" )")
    print("=" * 64)
    main()
