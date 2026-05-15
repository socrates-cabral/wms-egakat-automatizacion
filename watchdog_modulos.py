"""
watchdog_modulos.py — v1.1
Vigilante diario para Productividad y FillRate.
Programado en Task Scheduler: lunes a viernes 15:00.

Escenarios detectados:
  1. Sin log de hoy         → alerta email + reintento
  2. Log con [FALLO]        → alerta email
  3. Lock huérfano          → limpia lock + reintento
  4. Log incompleto (crash) → limpia lock + reintento
  5. Script corriendo       → sin acción (esperar)
  6. Todo OK                → sin acción
"""
import sys
sys.stdout.reconfigure(encoding="utf-8")

import os
import subprocess
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

BASE = Path(__file__).parent
load_dotenv(BASE / ".env")

# Importar Graph API email desde FillRate (ya configurado con TO/CC correctos)
sys.path.insert(0, str(BASE / "FillRate_Automatizacion"))
from fillrate_utils import send_summary_email  # type: ignore

PYTHON = str(Path(os.getenv(
    "PYTHON_EXE",
    r"C:\Users\Socrates Cabral\AppData\Local\Python\pythoncore-3.14-64\python.exe"
)))

MODULOS = [
    {
        "nombre": "Productividad",
        "log_dir": BASE / "Productividad_Automatizacion" / "logs",
        # Task Scheduler corre productividad_diario.py → log con prefijo "productividad_diario_".
        # Aceptamos también logs sin "diario_" para reintentos manuales con descarga.py.
        "log_glob": "productividad_diario_{date}_*.log",
        "log_glob_extra": "productividad_{date}_*.log",
        "date_fmt": "%Y%m%d",
        "lock_file": BASE / "Productividad_Automatizacion" / "logs" / "productividad_run.lock",
        # Reintento usa el runner idempotente: si todos los clientes ya están al día, sale silencioso.
        "script": BASE / "Productividad_Automatizacion" / "productividad_diario.py",
        # Marcadores de cierre aceptables:
        #   - "[TOTALES] ok="  → productividad_diario.py corrió clientes (línea 1104)
        #   - "[SKIP] Sin clientes pendientes" → diario skip idempotente (línea 1044)
        #   - "[DIARIO] Totales |" → productividad_descarga.py reintento manual (línea 1300)
        "fin_markers": ("[TOTALES] ok=", "[SKIP] Sin clientes pendientes", "[DIARIO] Totales |"),
    },
    {
        "nombre": "FillRate",
        "log_dir": BASE / "FillRate_Automatizacion" / "logs",
        "log_glob": "fillrate_{date}.log",          # date = YYYY-MM-DD
        "date_fmt": "%Y-%m-%d",
        "lock_file": BASE / "FillRate_Automatizacion" / "logs" / "fillrate_run.lock",
        "script": BASE / "FillRate_Automatizacion" / "fillrate_descarga.py",
        "fin_markers": ("FIN MODULO FILL RATE",),
    },
]


def pid_vivo(pid: int) -> bool:
    try:
        import psutil
        return psutil.pid_exists(pid)
    except ImportError:
        # Fallback sin psutil
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False


def lock_huerfano(lock_path: Path) -> bool:
    if not lock_path.exists():
        return False
    try:
        pid = int(lock_path.read_text().strip())
        return not pid_vivo(pid)
    except Exception:
        return True


def encontrar_log_hoy(log_dir: Path, glob_patterns, date_fmt: str) -> Path | None:
    """Devuelve el log más reciente de hoy. glob_patterns puede ser str o lista de str."""
    if isinstance(glob_patterns, str):
        glob_patterns = [glob_patterns]
    hoy = datetime.now().strftime(date_fmt)
    matches = []
    for pattern in glob_patterns:
        patron = pattern.replace("{date}", hoy)
        matches.extend(log_dir.glob(patron))
    if not matches:
        return None
    # Ordenar por mtime (más reciente primero) para evitar quedarse con un log viejo
    matches.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return matches[0]


def revisar_modulo(m: dict) -> dict:
    nombre      = m["nombre"]
    lock_path   = m["lock_file"]
    fin_markers = m["fin_markers"]

    estado = {"nombre": nombre, "ok": True, "accion": None, "detalle": "", "script": m["script"]}

    # Lock huérfano → limpiar y reintentar
    if lock_huerfano(lock_path):
        print(f"[WATCHDOG][{nombre}] Lock huérfano detectado.")
        lock_path.unlink(missing_ok=True)
        estado.update(ok=False, accion="reintento",
                      detalle="Lock huérfano (proceso muerto). Se relanzará.")
        return estado

    # Script todavía corriendo → esperar
    if lock_path.exists():
        print(f"[WATCHDOG][{nombre}] En ejecución (lock activo).")
        estado["detalle"] = "En ejecución"
        return estado

    # Sin log de hoy → no corrió
    globs = [m["log_glob"]] + ([m["log_glob_extra"]] if m.get("log_glob_extra") else [])
    log_path = encontrar_log_hoy(m["log_dir"], globs, m["date_fmt"])
    if not log_path:
        print(f"[WATCHDOG][{nombre}] Sin log de hoy.")
        estado.update(ok=False, accion="reintento",
                      detalle="No se encontró log de hoy. El script no corrió.")
        return estado

    contenido = log_path.read_text(encoding="utf-8", errors="ignore")

    # Log incompleto (crash sin lock) — fin_markers es tupla, cualquiera vale
    if not any(marker in contenido for marker in fin_markers):
        print(f"[WATCHDOG][{nombre}] Log incompleto (crash).")
        estado.update(ok=False, accion="reintento",
                      detalle=f"Log existe pero terminó sin marcador de fin. Crash probable.")
        return estado

    # Terminó con fallos
    fallos = [l.strip() for l in contenido.splitlines()
              if "[FALLO]" in l and "[FALLO PARCIAL]" not in l]
    if fallos:
        print(f"[WATCHDOG][{nombre}] Terminó con {len(fallos)} líneas [FALLO].")
        estado.update(ok=False, accion="alerta",
                      detalle=f"Corrida completada con {len(fallos)} fallos:\n" + "\n".join(fallos[-5:]))
        return estado

    print(f"[WATCHDOG][{nombre}] OK.")
    estado["detalle"] = "Corrida completa sin fallos."
    return estado


def reintentar(script: Path) -> None:
    print(f"[WATCHDOG] Relanzando {script.name}...")
    kwargs = {"creationflags": subprocess.CREATE_NEW_CONSOLE} if sys.platform == "win32" else {}
    subprocess.Popen([PYTHON, str(script)], **kwargs)


def main() -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[WATCHDOG] Inicio — {ts}")
    alertas = []

    for m in MODULOS:
        resultado = revisar_modulo(m)
        if not resultado["ok"]:
            alertas.append(resultado)
            if resultado["accion"] == "reintento":
                reintentar(resultado["script"])

    if alertas:
        resumen_txt = "\n\n".join(f"[{a['nombre']}] {a['detalle']}" for a in alertas)
        asunto = f"[WATCHDOG] Incidencias — {datetime.now().strftime('%d/%m/%Y %H:%M')}"
        html = (
            f"<h2>Watchdog Módulos — {datetime.now().strftime('%d/%m/%Y %H:%M')}</h2>"
            f"<p>Se detectaron problemas en los siguientes módulos:</p>"
            f"<pre style='font-family:monospace;background:#f5f5f5;padding:12px'>{resumen_txt}</pre>"
            f"<p>Los módulos con acción=<b>reintento</b> fueron relanzados automáticamente.</p>"
        )
        try:
            send_summary_email(asunto, html)
            print(f"[WATCHDOG] Alerta enviada: {asunto}")
        except Exception as e:
            print(f"[WATCHDOG] No se pudo enviar correo: {e}")
    else:
        print("[WATCHDOG] Todos los módulos OK.")

    print(f"[WATCHDOG] Fin — {datetime.now().strftime('%H:%M:%S')}")


if __name__ == "__main__":
    main()
