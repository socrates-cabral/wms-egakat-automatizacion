"""
sharepoint_upload.py — Fase 2: Subida de reportes WMS a SharePoint
Sube los archivos descargados por wms_descarga.py a SharePoint Online.
Autenticación: Azure App Registration (client_id + client_secret).
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from office365.runtime.auth.client_credential import ClientCredential
from office365.sharepoint.client_context import ClientContext

# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------

load_dotenv(dotenv_path=Path(__file__).parent / ".env")

SHAREPOINT_URL = "https://egakatcom.sharepoint.com/sites/DatosparaDashboard"
SHAREPOINT_CLIENT_ID = os.getenv("SHAREPOINT_CLIENT_ID")
SHAREPOINT_CLIENT_SECRET = os.getenv("SHAREPOINT_CLIENT_SECRET")

# Mapeo: carpeta local → ruta relativa en la librería de documentos de SharePoint
CARPETAS = {
    r"C:\ClaudeWork\Reportes\Quilicura": "Documentos compartidos/Inventario/Stock WMS Semanal/Quilicura",
    r"C:\ClaudeWork\Reportes\Pudahuel": "Documentos compartidos/Inventario/Stock WMS Semanal/Pudahuel",
    r"C:\ClaudeWork\Reportes\Pudahuel_Unitario": "Documentos compartidos/Inventario/Stock WMS Semanal/Pudahuel",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def validar_credenciales():
    if not SHAREPOINT_CLIENT_ID or not SHAREPOINT_CLIENT_SECRET:
        print("ERROR: SHAREPOINT_CLIENT_ID y/o SHAREPOINT_CLIENT_SECRET no están en .env")
        print("Registra una App en Azure AD y agrega las variables al .env")
        sys.exit(1)


def conectar() -> ClientContext:
    credentials = ClientCredential(SHAREPOINT_CLIENT_ID, SHAREPOINT_CLIENT_SECRET)
    ctx = ClientContext(SHAREPOINT_URL).with_credentials(credentials)
    # Verificar conexión
    web = ctx.web
    ctx.load(web)
    ctx.execute_query()
    print(f"Conectado a SharePoint: {web.properties['Title']}\n")
    return ctx


def asegurar_carpeta_sp(ctx: ClientContext, ruta_relativa: str):
    """Crea la carpeta en SharePoint si no existe (incluye subcarpetas anidadas)."""
    folder = ctx.web.ensure_folder_path(ruta_relativa)
    ctx.execute_query()
    return folder


def subir_archivo(ctx: ClientContext, ruta_sp: str, archivo_local: Path) -> bool:
    """Sube un archivo a SharePoint y retorna True si tuvo éxito."""
    try:
        with open(archivo_local, "rb") as f:
            contenido = f.read()

        folder = ctx.web.get_folder_by_server_relative_url(ruta_sp)
        folder.upload_file(archivo_local.name, contenido)
        ctx.execute_query()
        return True
    except Exception as e:
        print(f"  ERROR subiendo {archivo_local.name}: {e}")
        return False


# ---------------------------------------------------------------------------
# Lógica principal
# ---------------------------------------------------------------------------

def procesar_carpetas(ctx: ClientContext) -> dict:
    resumen = {}

    for carpeta_local_str, ruta_sp in CARPETAS.items():
        carpeta_local = Path(carpeta_local_str)
        nombre_carpeta = carpeta_local.name
        subidos = 0
        errores = 0

        if not carpeta_local.exists():
            print(f"[{nombre_carpeta}] Carpeta local no encontrada: {carpeta_local} — omitiendo.\n")
            resumen[nombre_carpeta] = {"subidos": 0, "errores": 0}
            continue

        archivos = [f for f in carpeta_local.iterdir() if f.is_file()]

        if not archivos:
            print(f"[{nombre_carpeta}] Sin archivos para subir.\n")
            resumen[nombre_carpeta] = {"subidos": 0, "errores": 0}
            continue

        print(f"[{nombre_carpeta}] Procesando {len(archivos)} archivo(s) → {ruta_sp}")

        # Asegurar que la carpeta existe en SharePoint
        try:
            asegurar_carpeta_sp(ctx, ruta_sp)
        except Exception as e:
            print(f"  ERROR creando carpeta en SharePoint: {e}")
            resumen[nombre_carpeta] = {"subidos": 0, "errores": len(archivos)}
            continue

        for archivo in archivos:
            print(f"  Subiendo: {archivo.name} ...", end=" ", flush=True)
            ok = subir_archivo(ctx, ruta_sp, archivo)
            if ok:
                print("OK")
                archivo.unlink()  # Eliminar archivo local tras subida exitosa
                subidos += 1
            else:
                errores += 1

        resumen[nombre_carpeta] = {"subidos": subidos, "errores": errores}
        print()

    return resumen


def imprimir_resumen(resumen: dict):
    print("=" * 50)
    print("RESUMEN DE SUBIDA")
    print("=" * 50)
    total_subidos = 0
    total_errores = 0
    for carpeta, datos in resumen.items():
        s = datos["subidos"]
        e = datos["errores"]
        total_subidos += s
        total_errores += e
        estado = "OK" if e == 0 else f"{e} error(es)"
        print(f"  {carpeta:<22} {s} subido(s)  [{estado}]")
    print("-" * 50)
    print(f"  TOTAL                  {total_subidos} subido(s)  [{total_errores} error(es)]")
    print("=" * 50)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    validar_credenciales()
    ctx = conectar()
    resumen = procesar_carpetas(ctx)
    imprimir_resumen(resumen)
