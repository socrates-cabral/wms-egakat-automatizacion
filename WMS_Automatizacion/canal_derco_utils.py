"""Funciones compartidas para clasificacion de ubicaciones y canales DERCO.

Usadas por:
  - canal_derco_auto.py        (recalcula columna Canal en data Derco.xlsx)
  - generar_resumen_kpi_ops.py (resumen para el bot de Telegram WMS Ops)

Mantener una sola fuente garantiza que data Derco y el bot reporten
splits AP_R / AP_E coherentes.

Reglas confirmadas con el usuario (auditoria 2026-05-14, 511.938 lineas MovDerco):
    P-EST-, I-BBR-, QE + digito         -> Estanteria
    Q + digito (no QE)                   -> Rack
    QP, MAQ, PISOD, ANDEN, INV1          -> Piso (zonas ficticias / transito / andén)
    resto                                -> Rack (default catch-all monitoreado)
"""

from __future__ import annotations

import re


_PREFIJOS_EST = ("P-EST-", "I-BBR-")
_PREFIJOS_PISO = ("QP", "MAQ", "PISOD", "ANDEN", "INV1")
_RE_QE = re.compile(r"^QE\d")
_RE_Q_NUM = re.compile(r"^Q\d")


def clasificar_ubicacion(ubic) -> str:
    """Devuelve 'EST' | 'RACK' | 'PISO'. Default: 'RACK'."""
    u = str(ubic).strip().upper()
    if u.startswith(_PREFIJOS_EST) or _RE_QE.match(u) or u.startswith("QE"):
        return "EST"
    if u.startswith(_PREFIJOS_PISO):
        return "PISO"
    if _RE_Q_NUM.match(u):
        return "RACK"
    return "RACK"


def clasificar_ubicacion_estricta(ubic) -> str | None:
    """Como clasificar_ubicacion pero retorna None si cae en el default catch-all.

    Util para auditar la aparicion de ubicaciones nuevas no contempladas en las reglas.
    """
    u = str(ubic).strip().upper()
    if u.startswith(_PREFIJOS_EST) or _RE_QE.match(u) or u.startswith("QE"):
        return "EST"
    if u.startswith(_PREFIJOS_PISO):
        return "PISO"
    if _RE_Q_NUM.match(u):
        return "RACK"
    return None


_DIM = {"EST": "ESTANTERIA", "RACK": "RACK", "PISO": "PISO"}


def clasificar_ubicacion_dim(ubic) -> str:
    """Variante con etiquetas RACK / ESTANTERIA / PISO (compatible con la nomenclatura
    que usa generar_resumen_kpi_ops.py para Tipo_Ubicacion_Dim)."""
    return _DIM[clasificar_ubicacion(ubic)]
