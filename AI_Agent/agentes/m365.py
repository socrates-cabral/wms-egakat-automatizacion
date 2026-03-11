"""
m365.py — Agente M365 Egakat
Lee, escribe y dispara Power Automate a través de OneDrive sincronizado.

Uso CLI:
    py AI_Agent/agentes/m365.py estado
    py AI_Agent/agentes/m365.py listar "Stock WMS"
    py AI_Agent/agentes/m365.py subir  "archivo.xlsx" --destino "Reportes VDR"
    py AI_Agent/agentes/m365.py mover  "archivo.xlsx" --origen "X" --destino "Y"
    py AI_Agent/agentes/m365.py notificar "mensaje" --flujo nps|vdr|wms
    py AI_Agent/agentes/m365.py limpiar "Reportes VDR" --dias 30

Uso como módulo:
    from agentes.m365 import subir_archivo, notificar_power_automate, listar_carpeta
"""
import sys
sys.stdout.reconfigure(encoding="utf-8")

import os
import shutil
import json
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent.parent.parent
load_dotenv(dotenv_path=BASE_DIR / ".env")

# ── Rutas OneDrive ─────────────────────────────────────────────────────────────
OD = Path(os.getenv(
    "ONEDRIVE_BASE",
    r"C:\Users\Socrates Cabral\OneDrive - EGA KAT LOGISTICA SPA"
))

# Carpetas del proyecto (alias → ruta relativa en OneDrive)
CARPETAS = {
    "stock wms":      OD / "Datos para Dashboard - Stock WMS Semanal",
    "posiciones":     OD / "Datos para Dashboard - Consulta de Posiciones",
    "staging":        OD / "Datos para Dashboard - Stagin IN- OUT",
    "vdr":            OD / "Reportes VDR",
    "nps":            OD / "Reportes NPS",
    "alertas nps":    OD / "Reportes NPS" / "Alertas",
}

# Carpetas que Power Automate vigila → acción automática
FLUJOS_PA = {
    "wms":  OD / "Datos para Dashboard - Stock WMS Semanal",
    "vdr":  OD / "Reportes VDR",
    "nps":  OD / "Reportes NPS",
    "alerta": OD / "Reportes NPS" / "Alertas",
}


# ══════════════════════════════════════════════════════════════════════════════
#  FUNCIONES PRINCIPALES
# ══════════════════════════════════════════════════════════════════════════════

def resolver_carpeta(termino: str) -> Path | None:
    """Resuelve alias o busca carpeta en OneDrive por nombre parcial."""
    t = termino.lower().strip()

    # Alias exacto
    if t in CARPETAS:
        return CARPETAS[t]

    # Búsqueda parcial en aliases
    for alias, ruta in CARPETAS.items():
        if t in alias:
            return ruta

    # Búsqueda directa en OneDrive
    for p in OD.iterdir():
        if p.is_dir() and t in p.name.lower():
            return p

    return None


def listar_carpeta(termino: str, dias: int = 7) -> dict:
    """Lista archivos recientes en una carpeta OneDrive."""
    carpeta = resolver_carpeta(termino)
    if not carpeta or not carpeta.exists():
        return {"error": f"Carpeta no encontrada: '{termino}'"}

    limite = datetime.now() - timedelta(days=dias)
    archivos = []

    for p in sorted(carpeta.rglob("*"), key=lambda x: x.stat().st_mtime, reverse=True):
        if p.is_file():
            mtime = datetime.fromtimestamp(p.stat().st_mtime)
            archivos.append({
                "nombre":   p.name,
                "ruta":     str(p),
                "tamaño":   f"{p.stat().st_size / 1024:.1f} KB",
                "fecha":    mtime.strftime("%d/%m/%Y %H:%M"),
                "reciente": mtime > limite,
            })

    recientes = [a for a in archivos if a["reciente"]]

    resumen = (
        f"Carpeta: {carpeta.name}\n"
        f"Ruta: {carpeta}\n"
        f"Total archivos: {len(archivos)} | Últimos {dias} días: {len(recientes)}\n\n"
    )

    if recientes:
        resumen += f"Archivos recientes ({len(recientes)}):\n"
        for a in recientes[:15]:
            resumen += f"  • {a['nombre']} — {a['tamaño']} — {a['fecha']}\n"
    else:
        resumen += f"Sin archivos nuevos en los últimos {dias} días.\n"

    return {
        "carpeta":   str(carpeta),
        "total":     len(archivos),
        "recientes": recientes,
        "todos":     archivos[:50],
        "resumen_texto": resumen,
    }


def subir_archivo(origen: str, destino_alias: str, renombrar: str = None) -> dict:
    """
    Copia un archivo local a una carpeta OneDrive.
    Esto dispara Power Automate automáticamente si la carpeta está vigilada.
    """
    origen_path = Path(origen)
    if not origen_path.exists():
        # buscar en ClaudeWork
        candidatos = list(BASE_DIR.rglob(origen_path.name))
        if candidatos:
            origen_path = candidatos[0]
        else:
            return {"error": f"Archivo no encontrado: {origen}"}

    destino_carpeta = resolver_carpeta(destino_alias)
    if not destino_carpeta:
        # Si se pasa ruta directa
        destino_carpeta = Path(destino_alias)
    if not destino_carpeta.exists():
        destino_carpeta.mkdir(parents=True, exist_ok=True)

    nombre_final = renombrar if renombrar else origen_path.name
    destino_path = destino_carpeta / nombre_final

    shutil.copy2(origen_path, destino_path)

    # Detectar si dispara Power Automate
    pa_activo = any(
        str(destino_carpeta).startswith(str(fp))
        for fp in FLUJOS_PA.values()
    )

    return {
        "origen":       str(origen_path),
        "destino":      str(destino_path),
        "tamaño":       f"{destino_path.stat().st_size / 1024:.1f} KB",
        "pa_disparado": pa_activo,
        "mensaje":      (
            f"✅ Archivo copiado a OneDrive.\n"
            f"   {origen_path.name} → {destino_path}\n"
            + ("   ⚡ Power Automate será disparado automáticamente." if pa_activo else "")
        ),
    }


def mover_archivo(nombre: str, origen_alias: str, destino_alias: str) -> dict:
    """Mueve un archivo entre carpetas OneDrive."""
    carpeta_origen = resolver_carpeta(origen_alias)
    if not carpeta_origen:
        return {"error": f"Carpeta origen no encontrada: '{origen_alias}'"}

    archivo = None
    for p in carpeta_origen.rglob(nombre):
        archivo = p
        break

    if not archivo:
        return {"error": f"Archivo '{nombre}' no encontrado en '{origen_alias}'"}

    carpeta_destino = resolver_carpeta(destino_alias)
    if not carpeta_destino:
        carpeta_destino = Path(destino_alias)
    carpeta_destino.mkdir(parents=True, exist_ok=True)

    destino = carpeta_destino / archivo.name
    shutil.move(str(archivo), str(destino))

    return {
        "archivo":  archivo.name,
        "origen":   str(carpeta_origen),
        "destino":  str(destino),
        "mensaje":  f"✅ Movido: {archivo.name}\n   {carpeta_origen.name} → {carpeta_destino.name}",
    }


def notificar_power_automate(mensaje: str, flujo: str = "alerta") -> dict:
    """
    Dispara un flujo Power Automate escribiendo un archivo .txt en la carpeta vigilada.
    Power Automate detecta el archivo nuevo y ejecuta el flujo (correo, Teams, etc.)
    """
    carpeta = FLUJOS_PA.get(flujo.lower())
    if not carpeta:
        return {"error": f"Flujo desconocido: '{flujo}'. Opciones: {list(FLUJOS_PA.keys())}"}

    carpeta.mkdir(parents=True, exist_ok=True)

    ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
    nombre   = f"trigger_{flujo}_{ts}.txt"
    ruta     = carpeta / nombre

    contenido = (
        f"Timestamp: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n"
        f"Flujo: {flujo}\n"
        f"Mensaje: {mensaje}\n"
        f"Origen: AI Safe Agent — Egakat SPA\n"
    )
    ruta.write_text(contenido, encoding="utf-8")

    return {
        "archivo_trigger": str(ruta),
        "flujo":           flujo,
        "mensaje":         f"⚡ Trigger escrito → Power Automate ejecutará el flujo '{flujo}'.\n   Archivo: {nombre}",
    }


def estado_general() -> dict:
    """Resumen del estado de todas las carpetas OneDrive del proyecto."""
    if not OD.exists():
        return {"error": f"OneDrive no encontrado en: {OD}"}

    resumen = f"Estado OneDrive — Egakat SPA\n{'═'*50}\n"
    resumen += f"Base: {OD}\n\n"

    for alias, carpeta in CARPETAS.items():
        if carpeta.exists():
            archivos = list(carpeta.rglob("*"))
            archivos_reales = [a for a in archivos if a.is_file()]
            ultimo = max(archivos_reales, key=lambda x: x.stat().st_mtime) if archivos_reales else None
            ultima_fecha = datetime.fromtimestamp(ultimo.stat().st_mtime).strftime("%d/%m/%Y %H:%M") if ultimo else "—"
            resumen += (
                f"  📁 {alias.upper():20} "
                f"{len(archivos_reales):4} archivos | "
                f"último: {ultima_fecha}\n"
            )
        else:
            resumen += f"  ❌ {alias.upper():20} carpeta no existe\n"

    resumen += f"\nFlujos Power Automate activos:\n"
    for flujo, carpeta in FLUJOS_PA.items():
        estado = "✅" if carpeta.exists() else "❌"
        resumen += f"  {estado} {flujo.upper():10} → {carpeta.name}\n"

    return {"resumen_texto": resumen}


def limpiar_antiguos(termino: str, dias: int = 30) -> dict:
    """Elimina archivos más antiguos que N días en una carpeta OneDrive."""
    carpeta = resolver_carpeta(termino)
    if not carpeta or not carpeta.exists():
        return {"error": f"Carpeta no encontrada: '{termino}'"}

    limite    = datetime.now() - timedelta(days=dias)
    eliminados = []

    for p in carpeta.rglob("*"):
        if p.is_file():
            mtime = datetime.fromtimestamp(p.stat().st_mtime)
            if mtime < limite:
                eliminados.append(p.name)
                p.unlink()

    return {
        "carpeta":    str(carpeta),
        "eliminados": eliminados,
        "mensaje":    (
            f"🗑️  Limpieza completada en '{carpeta.name}'.\n"
            f"   Eliminados: {len(eliminados)} archivo(s) con más de {dias} días."
        ),
    }


# ══════════════════════════════════════════════════════════════════════════════
#  CLI
# ══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Agente M365 Egakat — OneDrive + Power Automate")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("estado",   help="Estado general de todas las carpetas")

    p_list = sub.add_parser("listar", help="Listar archivos recientes")
    p_list.add_argument("carpeta")
    p_list.add_argument("--dias", type=int, default=7)

    p_sub = sub.add_parser("subir", help="Subir archivo a OneDrive")
    p_sub.add_argument("archivo")
    p_sub.add_argument("--destino", required=True)
    p_sub.add_argument("--nombre", default=None)

    p_mov = sub.add_parser("mover", help="Mover archivo entre carpetas")
    p_mov.add_argument("archivo")
    p_mov.add_argument("--origen",  required=True)
    p_mov.add_argument("--destino", required=True)

    p_not = sub.add_parser("notificar", help="Disparar flujo Power Automate")
    p_not.add_argument("mensaje")
    p_not.add_argument("--flujo", default="alerta", choices=list(FLUJOS_PA.keys()))

    p_lim = sub.add_parser("limpiar", help="Eliminar archivos antiguos")
    p_lim.add_argument("carpeta")
    p_lim.add_argument("--dias", type=int, default=30)

    args = parser.parse_args()

    # Ejecutar
    if args.cmd == "estado":
        resultado = estado_general()

    elif args.cmd == "listar":
        resultado = listar_carpeta(args.carpeta, args.dias)

    elif args.cmd == "subir":
        resultado = subir_archivo(args.archivo, args.destino, args.nombre)

    elif args.cmd == "mover":
        resultado = mover_archivo(args.archivo, args.origen, args.destino)

    elif args.cmd == "notificar":
        resultado = notificar_power_automate(args.mensaje, args.flujo)

    elif args.cmd == "limpiar":
        resultado = limpiar_antiguos(args.carpeta, args.dias)

    if "error" in resultado:
        print(f"[ERROR] {resultado['error']}")
        sys.exit(1)

    print(resultado.get("resumen_texto") or resultado.get("mensaje", json.dumps(resultado, ensure_ascii=False, indent=2, default=str)))


if __name__ == "__main__":
    main()
