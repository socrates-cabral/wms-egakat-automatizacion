"""
Configuracion central del modulo Productividad.

Reglas confirmadas:
- La lista de empresas sale del historico real de archivos.
- El nombre oficial se respeta como `Mov<AliasEmpresa>.xlsx`.
- No se agregan fechas al nombre del archivo.
- La hora operativa oficial de inicio es 08:00:00.
- La hora operativa oficial de cierre es 06:00:00.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List


WMS_LOGIN_URL = "https://egakatwms.cl/sglwms_EGA_prod/hinicio.aspx"
WMS_MENU_URL = "https://egakatwms.cl/sglwms_EGA_prod/trabajarconwms.aspx"
WMS_PRODUCTIVIDAD_URL = ""

PROJECT_DIR = str(Path(__file__).resolve().parent)
LOG_DIR = rf"{PROJECT_DIR}\logs"
DOWNLOAD_DIR = rf"{LOG_DIR}\downloads"
NORMALIZED_DIR = rf"{LOG_DIR}\normalized"
QUARANTINE_DIR = rf"{LOG_DIR}\quarantine"
SHAREPOINT_VERIFY_DIR = rf"{LOG_DIR}\sharepoint_verify"

LOCAL_HISTORICAL_REFERENCE_ROOT = (
    r"C:\Users\Socrates Cabral\OneDrive - EGA KAT LOGISTICA SPA\datos para Dashboard EK\Productividad"
)

OFFICIAL_DESTINATION_MODE = "sharepoint"
SHAREPOINT_SITE_NAME = "DatosparaDashboard"
SHAREPOINT_DOCUMENT_LIBRARY = "Documentos compartidos"
SHAREPOINT_PRODUCTIVIDAD_ROOT = "Productividad"
SHAREPOINT_BACKUP_ROOT = "_backups"

RANGE_START_TIME = "08:00:00"
RANGE_END_TIME = "06:00:00"

DERCO_HEAVY_CHUNK_DAYS = (7, 3, 1)
DERCO_HEAVY_RETRY_ATTEMPTS = 2
DERCO_HEAVY_RETRY_PAUSE_SECONDS = 60
DERCO_HEAVY_DOWNLOAD_TIMEOUT_MS = 360_000  # 6 min: DERCO genera Excel grande en servidor

VALID_SHEET_NAMES = (
    "Reporte de Movimientos",
    "Hoja1",
)

EXPECTED_HEADERS = (
    "Comprobante",
    "Artículo",
    "Serie",
    "Saldo Inicial",
    "Contenedor",
    "Ubicación",
    "Fecha Vto.",
    "Lote",
    "Fecha",
    "Hora",
    "Tipo de operación",
    "Naturaleza",
    "Número",
    "Registró",
    "Salida",
    "Entrada",
    "Saldo",
    "Comprobante externo",
)

MONTH_FOLDERS = {
    1: "01. Enero",
    2: "02. Febrero",
    3: "03. Marzo",
    4: "04. Abril",
    5: "05. Mayo",
    6: "06. Junio",
    7: "07. Julio",
    8: "08. Agosto",
    9: "09. Septiembre",
    10: "10. Octubre",
    11: "11. Noviembre",
    12: "12. Diciembre",
}

CONTROLLED_LIGHTWEIGHT_CLIENTS = {
    "abinbev": {
        "cd": "CD QUILICURA",
        "alias_archivo": "MovABInbev",
        "empresa_wms": "CERVECERIA ABI",
        "deposito_wms_origen": "QUILICURA",
        "carpeta_destino_historica": "CD QUILICURA",
        "historical_reference": (
            r"C:\Users\Socrates Cabral\OneDrive - EGA KAT LOGISTICA SPA\datos para Dashboard EK\Productividad\CD QUILICURA\2026\03. Marzo\MovABInbev.xlsx"
        ),
        "test_from": "01/04/26",
        "test_to": "10/04/26",
    },
    "bha": {
        "cd": "CD QUILICURA",
        "alias_archivo": "MovBha",
        "empresa_wms": "BHA",
        "deposito_wms_origen": "QUILICURA",
        "carpeta_destino_historica": "CD QUILICURA",
        "historical_reference": (
            r"C:\Users\Socrates Cabral\OneDrive - EGA KAT LOGISTICA SPA\datos para Dashboard EK\Productividad\CD QUILICURA\2026\03. Marzo\MovBha.xlsx"
        ),
        "test_from": "01/04/26",
        "test_to": "10/04/26",
    },
    "daikin": {
        "cd": "CD QUILICURA",
        "alias_archivo": "MovDaikin",
        "empresa_wms": "DAIKIN",
        "deposito_wms_origen": "QUILICURA",
        "carpeta_destino_historica": "CD QUILICURA",
        "historical_reference": (
            r"C:\Users\Socrates Cabral\OneDrive - EGA KAT LOGISTICA SPA\datos para Dashboard EK\Productividad\CD QUILICURA\2026\03. Marzo\MovDaikin.xlsx"
        ),
        "test_from": "01/04/26",
        "test_to": "10/04/26",
    },
    "pochteca": {
        "cd": "CD QUILICURA",
        "alias_archivo": "MovPochteca",
        "empresa_wms": "POCHTECA",
        "deposito_wms_origen": "QUILICURA",
        "carpeta_destino_historica": "CD QUILICURA",
        "historical_reference": (
            r"C:\Users\Socrates Cabral\OneDrive - EGA KAT LOGISTICA SPA\datos para Dashboard EK\Productividad\CD QUILICURA\2026\03. Marzo\MovPochteca.xlsx"
        ),
        "test_from": "01/04/26",
        "test_to": "10/04/26",
    },
    "mascota_quilicura": {
        "cd": "CD QUILICURA",
        "alias_archivo": "MovMascota",
        "empresa_wms": "MASCOTAS LATINAS",
        "deposito_wms_origen": "QUILICURA",
        "carpeta_destino_historica": "CD QUILICURA",
        "historical_reference": (
            r"C:\Users\Socrates Cabral\OneDrive - EGA KAT LOGISTICA SPA\datos para Dashboard EK\Productividad\CD QUILICURA\2026\03. Marzo\MovMascota.xlsx"
        ),
        "test_from": "01/04/26",
        "test_to": "10/04/26",
    },
    "barentz": {
        "cd": "CD PUDAHUEL",
        "alias_archivo": "MovBarentz",
        "empresa_wms": "BARENTZ",
        "deposito_wms_origen": "PUDAHUEL",
        "carpeta_destino_historica": "CD PUDAHUEL",
        "historical_reference": (
            r"C:\Users\Socrates Cabral\OneDrive - EGA KAT LOGISTICA SPA\datos para Dashboard EK\Productividad\CD PUDAHUEL\2026\01. Enero\MovBarentz.xlsx"
        ),
        "test_from": "01/04/26",
        "test_to": "10/04/26",
    },
    "buraschi": {
        "cd": "CD PUDAHUEL",
        "alias_archivo": "MovBuraschi",
        "empresa_wms": "BURASCHI",
        "deposito_wms_origen": "PUDAHUEL",
        "carpeta_destino_historica": "CD PUDAHUEL",
        "historical_reference": (
            r"C:\Users\Socrates Cabral\OneDrive - EGA KAT LOGISTICA SPA\datos para Dashboard EK\Productividad\CD PUDAHUEL\2026\03. Marzo\MovBuraschi.xlsx"
        ),
        "test_from": "01/04/26",
        "test_to": "10/04/26",
    },
    "cepas_chile": {
        "cd": "CD PUDAHUEL",
        "alias_archivo": "MovCepas Chile",
        "empresa_wms": "CEPAS CHILE",
        "deposito_wms_origen": "PUDAHUEL",
        "carpeta_destino_historica": "CD PUDAHUEL",
        "historical_reference": (
            r"C:\Users\Socrates Cabral\OneDrive - EGA KAT LOGISTICA SPA\datos para Dashboard EK\Productividad\CD PUDAHUEL\2026\03. Marzo\MovCepas Chile.xlsx"
        ),
        "test_from": "01/04/26",
        "test_to": "10/04/26",
    },
    "collico": {
        "cd": "CD PUDAHUEL",
        "alias_archivo": "MovCollico",
        "empresa_wms": "COLLICO",
        "deposito_wms_origen": "PUDAHUEL",
        "carpeta_destino_historica": "CD PUDAHUEL",
        "historical_reference": (
            r"C:\Users\Socrates Cabral\OneDrive - EGA KAT LOGISTICA SPA\datos para Dashboard EK\Productividad\CD PUDAHUEL\2026\03. Marzo\MovCollico.xlsx"
        ),
        "test_from": "01/04/26",
        "test_to": "10/04/26",
    },
    "delibest": {
        "cd": "CD PUDAHUEL",
        "alias_archivo": "MovDelibest",
        "empresa_wms": "DELIBEST",
        "deposito_wms_origen": "PUDAHUEL",
        "carpeta_destino_historica": "CD PUDAHUEL",
        "historical_reference": (
            r"C:\Users\Socrates Cabral\OneDrive - EGA KAT LOGISTICA SPA\datos para Dashboard EK\Productividad\CD PUDAHUEL\2026\03. Marzo\MovDelibest.xlsx"
        ),
        "test_from": "01/04/26",
        "test_to": "10/04/26",
    },
    "intime": {
        "cd": "CD PUDAHUEL",
        "alias_archivo": "Movintime",
        "empresa_wms": "INTIME",
        "deposito_wms_origen": "PUDAHUEL",
        "carpeta_destino_historica": "CD PUDAHUEL",
        "historical_reference": (
            r"C:\Users\Socrates Cabral\OneDrive - EGA KAT LOGISTICA SPA\datos para Dashboard EK\Productividad\CD PUDAHUEL\2026\02. Febrero\Movintime.xlsx"
        ),
        "test_from": "01/04/26",
        "test_to": "10/04/26",
    },
    "tresmontes": {
        "cd": "CD PUDAHUEL",
        "alias_archivo": "Movtresmontes",
        "empresa_wms": "TRES MONTES",
        "deposito_wms_origen": "PUDAHUEL",
        "carpeta_destino_historica": "CD PUDAHUEL",
        "historical_reference": (
            r"C:\Users\Socrates Cabral\OneDrive - EGA KAT LOGISTICA SPA\datos para Dashboard EK\Productividad\CD PUDAHUEL\2026\03. Marzo\Movtresmontes.xlsx"
        ),
        "test_from": "01/04/26",
        "test_to": "10/04/26",
    },
    "unilever": {
        "cd": "CD PUDAHUEL",
        "alias_archivo": "MovUnilever",
        "empresa_wms": "UNILEVER",
        "deposito_wms_origen": "PUDAHUEL",
        "carpeta_destino_historica": "CD PUDAHUEL",
        "historical_reference": (
            r"C:\Users\Socrates Cabral\OneDrive - EGA KAT LOGISTICA SPA\datos para Dashboard EK\Productividad\CD PUDAHUEL\2026\03. Marzo\MovUnilever.xlsx"
        ),
        "test_from": "01/04/26",
        "test_to": "10/04/26",
    },
    "runo": {
        "cd": "CD PUDAHUEL",
        "alias_archivo": "MovRuno",
        "empresa_wms": "RUNO SPA",
        "deposito_wms_origen": "PUDAHUEL UNITARIO",
        "internal_cd_expected": "PUDAHUEL UNITARIO",
        "carpeta_destino_historica": "CD PUDAHUEL",
        "historical_reference": (
            r"C:\Users\Socrates Cabral\OneDrive - EGA KAT LOGISTICA SPA\datos para Dashboard EK\Productividad\CD PUDAHUEL\2026\03. Marzo\MovRuno.xlsx"
        ),
        "test_from": "01/04/26",
        "test_to": "10/04/26",
    },
}

CONTROLLED_HEAVY_CLIENTS = {
    "derco": {
        "cd": "CD QUILICURA",
        "alias_archivo": "MovDerco",
        "empresa_wms": "DERCO",
        "deposito_wms_origen": "QUILICURA",
        "carpeta_destino_historica": "CD QUILICURA",
        "historical_reference": (
            r"C:\Users\Socrates Cabral\OneDrive - EGA KAT LOGISTICA SPA\datos para Dashboard EK\Productividad\CD QUILICURA\2026\03. Marzo\MovDerco.xlsx"
        ),
        "heavy_client": True,
        "chunk_days": DERCO_HEAVY_CHUNK_DAYS,
        "chunk_retry_attempts": DERCO_HEAVY_RETRY_ATTEMPTS,
        "chunk_retry_pause_seconds": DERCO_HEAVY_RETRY_PAUSE_SECONDS,
        "download_timeout_ms": DERCO_HEAVY_DOWNLOAD_TIMEOUT_MS,
        "runtime_notes": (
            "Cliente heavy: requiere chunking exacto por rango operativo, "
            "deduplicacion deterministica y consolidacion previa a SharePoint."
        ),
    },
}

CONTROLLED_EXECUTION_CLIENTS = {
    **CONTROLLED_LIGHTWEIGHT_CLIENTS,
    **CONTROLLED_HEAVY_CLIENTS,
}

PRODUCTION_LIGHTWEIGHT_CLIENTS = (
    "daikin",
    "pochteca",
    "barentz",
    "abinbev",
    "bha",
    "mascota_quilicura",
    "buraschi",
    "cepas_chile",
    "collico",
    "delibest",
    "intime",
    "tresmontes",
    "unilever",
    "runo",
)

# Compatibilidad temporal con la corrida controlada inicial de DAIKIN.
CONTROLLED_LIGHTWEIGHT_CLIENT = CONTROLLED_LIGHTWEIGHT_CLIENTS["daikin"]

CatalogRow = Dict[str, Any]


CLIENTS: List[CatalogRow] = [
    {
        "cd": "CD PUDAHUEL",
        "alias_archivo": "MovBarentz",
        "empresa_wms": "BARENTZ",
        "deposito_wms_origen": "PUDAHUEL",
        "carpeta_destino_historica": "CD PUDAHUEL",
        "active": True,
        "runtime_notes": "Validar texto exacto del dropdown WMS antes de automatizar seleccion.",
    },
    {
        "cd": "CD PUDAHUEL",
        "alias_archivo": "MovBuraschi",
        "empresa_wms": "BURASCHI",
        "deposito_wms_origen": "PUDAHUEL",
        "carpeta_destino_historica": "CD PUDAHUEL",
        "active": True,
        "runtime_notes": "Cliente historico activo. Validar disponibilidad real en dropdown WMS.",
    },
    {
        "cd": "CD PUDAHUEL",
        "alias_archivo": "MovCepas Chile",
        "empresa_wms": "CEPAS CHILE",
        "deposito_wms_origen": "PUDAHUEL",
        "carpeta_destino_historica": "CD PUDAHUEL",
        "active": True,
        "runtime_notes": "Validar texto exacto del dropdown WMS antes de automatizar seleccion.",
    },
    {
        "cd": "CD PUDAHUEL",
        "alias_archivo": "MovCollico",
        "empresa_wms": "COLLICO",
        "deposito_wms_origen": "PUDAHUEL",
        "carpeta_destino_historica": "CD PUDAHUEL",
        "active": True,
        "runtime_notes": "Cliente historico activo. Validar disponibilidad real en dropdown WMS.",
    },
    {
        "cd": "CD PUDAHUEL",
        "alias_archivo": "MovDelibest",
        "empresa_wms": "DELIBEST",
        "deposito_wms_origen": "PUDAHUEL",
        "carpeta_destino_historica": "CD PUDAHUEL",
        "active": True,
        "runtime_notes": "Cliente historico activo. Validar disponibilidad real en dropdown WMS.",
    },
    {
        "cd": "CD PUDAHUEL",
        "alias_archivo": "MovMascota Latina",
        "empresa_wms": "MASCOTAS LATINAS",
        "deposito_wms_origen": "PUDAHUEL",
        "carpeta_destino_historica": "CD PUDAHUEL",
        "active": False,
        "runtime_notes": "Historico mantenido en catalogo, inactivo por instruccion explicita.",
    },
    {
        "cd": "CD PUDAHUEL",
        "alias_archivo": "MovRuno",
        "empresa_wms": "RUNO SPA",
        "deposito_wms_origen": "PUDAHUEL UNITARIO",
        "carpeta_destino_historica": "CD PUDAHUEL",
        "active": True,
        "runtime_notes": "Caso especial confirmado: deposito origen distinto de la carpeta destino.",
    },
    {
        "cd": "CD PUDAHUEL",
        "alias_archivo": "Movtresmontes",
        "empresa_wms": "TRES MONTES",
        "deposito_wms_origen": "PUDAHUEL",
        "carpeta_destino_historica": "CD PUDAHUEL",
        "active": True,
        "runtime_notes": "Alias historico usa minuscula en 'tresmontes'; no normalizar.",
    },
    {
        "cd": "CD PUDAHUEL",
        "alias_archivo": "MovUnilever",
        "empresa_wms": "UNILEVER",
        "deposito_wms_origen": "PUDAHUEL",
        "carpeta_destino_historica": "CD PUDAHUEL",
        "active": True,
        "runtime_notes": "Validar texto exacto del dropdown WMS antes de automatizar seleccion.",
    },
    {
        "cd": "CD PUDAHUEL",
        "alias_archivo": "Movintime",
        "empresa_wms": "INTIME",
        "deposito_wms_origen": "PUDAHUEL",
        "carpeta_destino_historica": "CD PUDAHUEL",
        "active": True,
        "runtime_notes": "Confirmado activo por instruccion explicita.",
    },
    {
        "cd": "CD PUDAHUEL",
        "alias_archivo": "MovWildFoods Moderno",
        "empresa_wms": "WILD FOODS",
        "deposito_wms_origen": "PUDAHUEL",
        "carpeta_destino_historica": "CD PUDAHUEL",
        "active": False,
        "runtime_notes": "Historico inactivo por instruccion explicita. Mantener en catalogo, no descargar.",
    },
    {
        "cd": "CD PUDAHUEL",
        "alias_archivo": "MovwildFoods Tradicional",
        "empresa_wms": "WILD FOODS",
        "deposito_wms_origen": "PUDAHUEL UNITARIO",
        "carpeta_destino_historica": "CD PUDAHUEL",
        "active": False,
        "runtime_notes": "Historico inactivo por instruccion explicita. Respetar casing historico del alias.",
    },
    {
        "cd": "CD PUDAHUEL",
        "alias_archivo": "MovNotCompany",
        "empresa_wms": "THE NOT COMPANY",
        "deposito_wms_origen": "PUDAHUEL",
        "carpeta_destino_historica": "CD PUDAHUEL",
        "active": False,
        "runtime_notes": "Historico inactivo por instruccion explicita. Mantener en catalogo, no descargar.",
    },
    {
        "cd": "CD QUILICURA",
        "alias_archivo": "MovABInbev",
        "empresa_wms": "CERVECERIA ABI",
        "deposito_wms_origen": "QUILICURA",
        "carpeta_destino_historica": "CD QUILICURA",
        "active": True,
        "runtime_notes": "Alias historico difiere del nombre interno; validar consistencia post-descarga.",
    },
    {
        "cd": "CD QUILICURA",
        "alias_archivo": "MovBha",
        "empresa_wms": "BHA",
        "deposito_wms_origen": "QUILICURA",
        "carpeta_destino_historica": "CD QUILICURA",
        "active": True,
        "runtime_notes": "Cliente historico activo. Validar disponibilidad real en dropdown WMS.",
    },
    {
        "cd": "CD QUILICURA",
        "alias_archivo": "MovDaikin",
        "empresa_wms": "DAIKIN",
        "deposito_wms_origen": "QUILICURA",
        "carpeta_destino_historica": "CD QUILICURA",
        "active": True,
        "runtime_notes": "Validar texto exacto del dropdown WMS antes de automatizar seleccion.",
    },
    {
        "cd": "CD QUILICURA",
        "alias_archivo": "MovDerco",
        "empresa_wms": "DERCO",
        "deposito_wms_origen": "QUILICURA",
        "carpeta_destino_historica": "CD QUILICURA",
        "active": True,
        "runtime_notes": "Caso de riesgo: existe historico con descalce interno observado en abril 2026.",
    },
    {
        "cd": "CD QUILICURA",
        "alias_archivo": "MovMascota",
        "empresa_wms": "MASCOTAS LATINAS",
        "deposito_wms_origen": "QUILICURA",
        "carpeta_destino_historica": "CD QUILICURA",
        "active": True,
        "runtime_notes": "Alias historico de Quilicura difiere del usado en Pudahuel.",
    },
    {
        "cd": "CD QUILICURA",
        "alias_archivo": "MovPochteca",
        "empresa_wms": "POCHTECA",
        "deposito_wms_origen": "QUILICURA",
        "carpeta_destino_historica": "CD QUILICURA",
        "active": True,
        "runtime_notes": "Cliente historico activo. Validar disponibilidad real en dropdown WMS.",
    },
]


def get_all_clients() -> List[CatalogRow]:
    return list(CLIENTS)


def get_active_clients() -> List[CatalogRow]:
    return [client for client in CLIENTS if client.get("active")]
