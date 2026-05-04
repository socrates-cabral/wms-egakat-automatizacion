"""
Configuracion central del modulo FillRate.

Notas:
- Los textos `deposito_wms` y `empresa_wms` deben coincidir con el texto visible
  exacto del WMS en runtime.
- No se inventan labels de dropdown fuera de los ya documentados.
- `active=False` implica omitir el cliente sin tratarlo como error.
"""

from __future__ import annotations

from typing import Any, Dict, List


WMS_LOGIN_URL = "https://egakatwms.cl/sglwms_EGA_prod/hinicio.aspx"
WMS_MENU_URL = "https://egakatwms.cl/sglwms_EGA_prod/trabajarconwms.aspx"
WMS_FILLRATE_URL = "https://egakatwms.cl/sglwms_EGA_prod/seguimientopedidoswp.aspx"

SHAREPOINT_BASE_PATH = "NNSS/NNSS Operacional"
TARGET_SHEET_NAME = "seguimiento de pedidos"
FALLBACK_SHEET_POLICY = "first_sheet"
BASE_SHEET_NAME = "base"

WMS_OPERACION_LABEL = "ORDEN DE PREP. C/STOCK"
WMS_ESTADO_DEFAULT = "Todos los Estados"
WMS_FECHA_TIPO_DEFAULT = "Fecha de Generación"
DOWNLOAD_TIMEOUT_MS = 60_000
HEAVY_DOWNLOAD_TIMEOUT_MS = 120_000
DEFAULT_DOWNLOAD_ATTEMPTS = 1
DEFAULT_DOWNLOAD_BACKOFF_MULTIPLIER = 1.0

DOWNLOAD_BASENAME_PREFIXES = (
    "Reporte_Consulta_de_Fill_Rate",
    "Reporte Consulta de Fill Rate",
)
DOWNLOAD_SUFFIXES = (".xlsx", ".xls")

ESTADOS_ENTREGA = {
    "Remitido",
    "Remitidos",
    "Despachado",
    "Despachados",
    "Con Salida",
}

ESTADOS_ALERTA = {
    "En Preparacion",
    "En Preparación",
    "Preparado",
    "Preparados",
}

WARNING_MAX_DAYS = 7

MESES_CORTE = {
    1: "Ene",
    2: "Feb",
    3: "Mar",
    4: "Abr",
    5: "May",
    6: "Jun",
    7: "Jul",
    8: "Ago",
    9: "Sep",
    10: "Oct",
    11: "Nov",
    12: "Dic",
}


ClientConfig = Dict[str, Any]


CLIENTS: List[ClientConfig] = [
    {
        "nombre": "Cerveceria ABI",
        "deposito_wms": "QUILICURA",
        "empresa_wms": "CERVECERIA ABI",
        "cd": "Quilicura",
        "sp_file": "Data Abi.xlsx",
        "has_corte": True,
        "active": True,
        "runtime_notes": "Dropdown WMS Quilicura confirmado segun memoria de proyecto.",
    },
    {
        "nombre": "Daikin",
        "deposito_wms": "QUILICURA",
        "empresa_wms": "DAIKIN",
        "cd": "Quilicura",
        "sp_file": "data Daikin.xlsx",
        "has_corte": True,
        "active": True,
        "runtime_notes": "Existe tambien 'DAIKIN CLIENTES' en WMS; no seleccionar ese.",
    },
    {
        "nombre": "Derco",
        "deposito_wms": "QUILICURA",
        "empresa_wms": "DERCO",
        "cd": "Quilicura",
        "sp_file": "data Derco.xlsx",
        "has_corte": True,
        "active": True,
        "download_timeout_ms": HEAVY_DOWNLOAD_TIMEOUT_MS,
        "download_attempts": 1,
        "download_backoff_multiplier": 1.0,
        "runtime_notes": "Cliente pesado; usar timeout extendido y validar volumen real.",
    },
    {
        "nombre": "Mascotas Latinas (Quilicura)",
        "deposito_wms": "QUILICURA",
        "empresa_wms": "MASCOTAS LATINAS",
        "cd": "Quilicura",
        "sp_file": "data Mascotas Latinas.xlsx",
        "has_corte": True,
        "active": True,
        "runtime_notes": "Texto confirmado en memoria con plural y sin tilde.",
    },
    {
        "nombre": "Pochteca",
        "deposito_wms": "QUILICURA",
        "empresa_wms": "POCHTECA",
        "cd": "Quilicura",
        "sp_file": "data Pochteca.xlsx",
        "has_corte": True,
        "active": True,
        "runtime_notes": "Confirmar disponibilidad en dropdown real de Fill Rate.",
    },
    {
        "nombre": "Barentz",
        "deposito_wms": "PUDAHUEL",
        "empresa_wms": "BARENTZ",
        "cd": "Pudahuel",
        "sp_file": "data Barentz.xlsx",
        "has_corte": False,
        "active": True,
        "runtime_notes": "Confirmado segun memoria de dropdown Pudahuel.",
    },
    {
        "nombre": "Cepas Chile",
        "deposito_wms": "PUDAHUEL",
        "empresa_wms": "CEPAS CHILE",
        "cd": "Pudahuel",
        "sp_file": "data Cepas.xlsx",
        "has_corte": False,
        "active": True,
        "runtime_notes": "Confirmado segun memoria de dropdown Pudahuel.",
    },
    {
        "nombre": "Collico",
        "deposito_wms": "PUDAHUEL",
        "empresa_wms": "COLLICO",
        "cd": "Pudahuel",
        "sp_file": "data Collico.xlsx",
        "has_corte": False,
        "active": True,
        "runtime_notes": "Confirmado PUDAHUEL 2026-04-11. Empresa COLLICO no existe en QUILICURA.",
    },
    {
        "nombre": "Delibest",
        "deposito_wms": "PUDAHUEL",
        "empresa_wms": "DELIBEST",
        "cd": "Pudahuel",
        "sp_file": "data Delibest.xlsx",
        "has_corte": False,
        "active": True,
        "runtime_notes": "Confirmado PUDAHUEL 2026-04-11.",
    },
    {
        "nombre": "Intime",
        "deposito_wms": "PUDAHUEL",
        "empresa_wms": "INTIME",
        "cd": "Pudahuel",
        "sp_file": "data Intime.xlsx",
        "has_corte": False,
        "active": True,
        "runtime_notes": "Confirmado segun memoria de dropdown Pudahuel.",
    },
    {
        "nombre": "Mascotas Latinas (Pudahuel)",
        "deposito_wms": "PUDAHUEL",
        "empresa_wms": None,
        "cd": "Pudahuel",
        "sp_file": "data Mascotas.xlsx",
        "has_corte": False,
        "active": False,
        "runtime_notes": "No existe en dropdown Pudahuel; mantener omitido.",
    },
    {
        "nombre": "Nativo Drinks",
        "deposito_wms": "PUDAHUEL",
        "empresa_wms": "NATIVO DRINKS SPA",
        "cd": "Pudahuel",
        "sp_file": "data Nativo Drinks.xlsx",
        "has_corte": False,
        "active": True,
        "download_timeout_ms": 120_000,
        "download_attempts": 3,
        "download_backoff_multiplier": 1.5,
        "runtime_notes": "Nombre completo con 'SPA' segun memoria de proyecto.",
    },
    {
        "nombre": "Omnitech",
        "deposito_wms": "PUDAHUEL",
        "empresa_wms": "OMNITECH",
        "cd": "Pudahuel",
        "sp_file": "data Omnitech.xlsx",
        "has_corte": False,
        "active": True,
        "runtime_notes": "Confirmado PUDAHUEL 2026-05-04 segun captura WMS.",
    },
    {
        "nombre": "Runo SPA",
        "deposito_wms": "PUDAHUEL UNITARIO",
        "empresa_wms": "RUNO SPA",
        "cd": "Pudahuel",
        "sp_file": "data Runo Tradicional.xlsx",
        "has_corte": False,
        "active": True,
        "download_timeout_ms": 120_000,
        "download_attempts": 3,
        "download_backoff_multiplier": 1.5,
        "runtime_notes": "Deposito especial; validar dropdown en runtime.",
    },
    {
        "nombre": "Unilever",
        "deposito_wms": "PUDAHUEL",
        "empresa_wms": "UNILEVER",
        "cd": "Pudahuel",
        "sp_file": "data Unilever.xlsx",
        "has_corte": False,
        "active": True,
        "download_timeout_ms": 120_000,
        "download_attempts": 3,
        "download_backoff_multiplier": 1.5,
        "runtime_notes": "Confirmado segun memoria de dropdown Pudahuel.",
    },
]


def get_active_clients() -> List[ClientConfig]:
    """Retorna los clientes activos preservando el orden operativo."""
    return [client for client in CLIENTS if client.get("active")]


def get_all_clients() -> List[ClientConfig]:
    """Retorna todos los clientes configurados."""
    return list(CLIENTS)


def get_sharepoint_relative_path(client: ClientConfig) -> str:
    """Construye la ruta relativa del archivo del cliente dentro de SharePoint."""
    return f"{SHAREPOINT_BASE_PATH}/{client['cd']}/{client['sp_file']}"
