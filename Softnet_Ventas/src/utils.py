import sys
sys.stdout.reconfigure(encoding="utf-8")

import os
import subprocess
from datetime import date, timedelta
from calendar import monthrange
from pathlib import Path

MESES_ES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
}


def meses_en_ventana(fecha_ref: date, ventana_dias: int = 60, año_inicio: int | None = None) -> list[tuple[int, int]]:
    """Retorna lista de (año, mes) abiertos según regla de ventana.
    Un mes está abierto si: último_día_mes + ventana_dias >= fecha_ref.
    Si año_inicio está definido, no retrocede más allá de enero de ese año.
    """
    abiertos = []
    año, mes = fecha_ref.year, fecha_ref.month
    while True:
        if año_inicio and año < año_inicio:
            break
        ultimo_dia = monthrange(año, mes)[1]
        fecha_cierre = date(año, mes, ultimo_dia) + timedelta(days=ventana_dias)
        if fecha_cierre < fecha_ref:
            break
        abiertos.append((año, mes))
        mes -= 1
        if mes == 0:
            mes = 12
            año -= 1
    return sorted(abiertos)


def nombre_archivo_sp(año: int, mes: int) -> str:
    return f"{mes}.0 Ventas {MESES_ES[mes]} {año}.xlsx"


def mes_a_nombre_softnet(mes: int) -> str:
    return MESES_ES[mes].upper()


def adquirir_lock(lockfile: Path) -> bool:
    """PID check idéntico al patrón de run_todos.py."""
    if lockfile.exists():
        try:
            pid = int(lockfile.read_text().strip())
            result = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV"],
                capture_output=True, text=True,
            )
            if str(pid) in result.stdout:
                print(f"[LOCK] Ya hay una instancia corriendo (PID {pid}). Abortando.")
                return False
            print(f"[LOCK] Lock obsoleto (PID {pid} no existe). Limpiando y continuando.")
        except Exception:
            pass
    lockfile.parent.mkdir(parents=True, exist_ok=True)
    lockfile.write_text(str(os.getpid()))
    return True


def liberar_lock(lockfile: Path) -> None:
    try:
        if lockfile.exists():
            lockfile.unlink()
    except Exception:
        pass


def limpiar_downloads(downloads_dir: Path) -> None:
    """Elimina todos los .xlsx en downloads/ para evitar sufijos '(1)', '(2)'."""
    if downloads_dir.exists():
        for f in downloads_dir.glob("*.xlsx"):
            try:
                f.unlink()
            except Exception:
                pass


def snapshot_existe(snapshot_dir: Path, año: int, mes: int) -> bool:
    nombre = nombre_archivo_sp(año, mes).replace(".xlsx", "_cierre.xlsx")
    return (snapshot_dir / str(año) / nombre).exists()


def guardar_snapshot_cierre(snapshot_dir: Path, año: int, mes: int, contenido: bytes) -> Path:
    nombre = nombre_archivo_sp(año, mes).replace(".xlsx", "_cierre.xlsx")
    destino = snapshot_dir / str(año) / nombre
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(contenido)
    return destino


# ─── CHECKPOINT ───────────────────────────────────────────────────────────────

def checkpoint_path(logs_dir: Path) -> Path:
    from datetime import datetime
    return logs_dir / f"softnet_checkpoint_{datetime.now().strftime('%Y%m%d')}.json"


def cargar_checkpoint(logs_dir: Path) -> set[str]:
    """Retorna el set de mes_labels ya completados exitosamente hoy ('2026-02', ...)."""
    path = checkpoint_path(logs_dir)
    if not path.exists():
        return set()
    try:
        import json
        return set(json.loads(path.read_text(encoding="utf-8")).get("completados", []))
    except Exception:
        return set()


def guardar_checkpoint(logs_dir: Path, mes_label: str) -> None:
    """Registra un mes como completado en el checkpoint del día."""
    import json
    path = checkpoint_path(logs_dir)
    completados = cargar_checkpoint(logs_dir)
    completados.add(mes_label)
    path.write_text(
        json.dumps({"completados": sorted(completados)}, ensure_ascii=False),
        encoding="utf-8",
    )
