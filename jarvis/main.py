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
    app.setQuitOnLastWindowClosed(False)

    bridge = get_bridge()
    overlay = JarvisOverlay(bridge)
    harness = JarvisHarness(bridge)

    print("=" * 50)
    print("  J.A.R.V.I.S. -- Iniciando...")
    print(f"  Hotkey: {HOTKEY.upper()}")
    print("  ESC para salir")
    print("=" * 50)

    voice.play_startup()
    harness.start()

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
    print(f"\nJARVIS: {saludo}\n")
    voice.speak(saludo)

    keyboard.add_hotkey(HOTKEY, harness.trigger)
    keyboard.add_hotkey("esc", app.quit)
    print(f"En espera. Presiona {HOTKEY.upper()} para hablar.\n")

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
