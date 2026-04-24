import sys
sys.stdout.reconfigure(encoding="utf-8")

import os
import subprocess
import time
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

# ── Rutas ────────────────────────────────────────────────────────────
BASE    = Path(__file__).parent
LOGDIR  = Path(__file__).parent.parent / "logs"
LOGDIR.mkdir(exist_ok=True)
LOGFILE  = LOGDIR / f"despacho_pipeline_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
LOCKFILE = LOGDIR / "despacho_pipeline.lock"
PYTHON   = sys.executable

PAUSA_ENTRE_PASOS = 10  # segundos entre despacho.py y confirmar_salida.py

# ── Helpers ──────────────────────────────────────────────────────────
def log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    linea = f"{ts} | {msg}"
    print(linea)
    with open(LOGFILE, "a", encoding="utf-8") as f:
        f.write(linea + "\n")


def adquirir_lock() -> bool:
    if LOCKFILE.exists():
        try:
            pid = int(LOCKFILE.read_text().strip())
            result = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV"],
                capture_output=True, text=True
            )
            if str(pid) in result.stdout:
                log(f"[LOCK] Instancia ya corriendo (PID {pid}). Abortando.")
                return False
            log(f"[LOCK] Lock obsoleto (PID {pid} no existe). Limpiando.")
        except Exception:
            pass
    LOCKFILE.write_text(str(os.getpid()))
    return True


def liberar_lock():
    try:
        LOCKFILE.unlink(missing_ok=True)
    except Exception:
        pass


def ejecutar_paso(nombre: str, script: str) -> int:
    log(f"[{nombre}] Iniciando → {script}")
    result = subprocess.run(
        [PYTHON, str(BASE / script)],
        cwd=str(BASE),
        capture_output=False,   # output directo a consola + log
    )
    if result.returncode != 0:
        log(f"[FALLO] {nombre} terminó con código {result.returncode}")
    else:
        log(f"[OK] {nombre} completado")
    return result.returncode


# ── Main ─────────────────────────────────────────────────────────────
def main() -> int:
    log("=" * 60)
    log("  WMS EGAKAT — PIPELINE DESPACHO COMPLETO")
    log(f"  Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log("=" * 60)

    if not adquirir_lock():
        return 1

    try:
        # Paso 1: Despacho RF
        rc1 = ejecutar_paso("1/2 Despacho RF", "despacho.py")
        if rc1 != 0:
            log("[STOP] despacho.py falló — no se ejecuta confirmar_salida.py")
            return rc1

        # Pausa para que el WMS procese los despachos
        log(f"[PAUSA] Esperando {PAUSA_ENTRE_PASOS}s para que el WMS procese...")
        time.sleep(PAUSA_ENTRE_PASOS)

        # Paso 2: Confirmar Salida WEB
        rc2 = ejecutar_paso("2/2 Confirmar Salida WEB", "confirmar_salida.py")
        return rc2

    finally:
        liberar_lock()
        log("=" * 60)
        log("  FIN PIPELINE")
        log("=" * 60)


if __name__ == "__main__":
    raise SystemExit(main())
