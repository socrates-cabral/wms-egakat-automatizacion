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

from typing import Any, Dict, List


WMS_LOGIN_URL = "https://egakatwms.cl/sglwms_EGA_prod/hinicio.aspx"
WMS_MENU_URL = "https://egakatwms.cl/sglwms_EGA_prod/trabajarconwms.aspx"
WMS_PRODUCTIVIDAD_URL = ""

PROJECT_DIR = r"C:\ClaudeWork\Productividad_Automatizacion"
LOG_DIR = rf"{PROJECT_DIR}\logs"
DOWNLOAD_DIR = rf"{LOG_DIR}\downloads"

PRODUCTIVIDAD_ROOT = (
    r"C:\Users\Socrates Cabral\OneDrive - EGA KAT LOGISTICA SPA\datos para Dashboard EK\Productividad"
)

RANGE_START_TIME = "08:00:00"
RANGE_END_TIME = "06:00:00"

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
        "active": True,
        "runtime_notes": "Alias historico confirmado para Pudahuel.",
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
