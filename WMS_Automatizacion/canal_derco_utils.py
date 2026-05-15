"""Funciones compartidas para clasificacion de ubicaciones y canales DERCO.

Usadas por:
  - canal_derco_auto.py        (recalcula columna Canal en data Derco.xlsx)
  - generar_resumen_kpi_ops.py (resumen para el bot de Telegram WMS Ops)

Mantener una sola fuente garantiza que data Derco y el bot reporten
splits AP_R / AP_E / CES coherentes.

Reglas de ubicacion (auditoria 2026-05-14, 511.938 lineas MovDerco):
    P-EST-, I-BBR-, QE + digito         -> Estanteria
    Q + digito (no QE)                   -> Rack
    QP, MAQ, PISOD, ANDEN, INV1          -> Piso (zonas ficticias / transito / andén)
    resto                                -> Rack (default catch-all monitoreado)

Reglas de canal por (Comprobante externo, Destino):
    46AP00                               -> AP
    31SODI | 31WALM | 31EASY |
    31REND | 31HIPE                      -> GT
    55LO B                               -> LB
    46SG00                               -> SG
    91SG00 | 91AP00 | 91CORO             -> CAP
    resto                                -> MY

Resolucion final del canal (regla de negocio DERCO):
    AP + Rack >= Est                     -> AP_R
    AP + Est > Rack                      -> AP_E
    MY + destino en Base CES             -> CES
    resto                                -> canal_ppal (GT/SG/CAP/MY/LB)
"""

from __future__ import annotations

import re
from typing import Any, Callable, Iterable, Optional


# ============================================================================
# UBICACIONES
# ============================================================================

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


# ============================================================================
# CANALES
# ============================================================================

def norm_str_canal(s: Any) -> str:
    """Normaliza texto para comparaciones de canal/CES.

    Mayusculas, trim, colapsa puntuacion y espacios.
    """
    s = str(s).upper().strip()
    s = re.sub(r"[.,/]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def canal_principal_derco(comprobante_externo: Any, destino: Any) -> str:
    """Canal principal segun la clave de 2+4 chars del Comprobante externo + Destino.

    Retorna: AP | GT | LB | SG | CAP | MY.
    AP se afina luego a AP_R/AP_E via resolver_canal_con_ces().
    MY se afina luego a CES via resolver_canal_con_ces() si el Destino esta en Base CES.
    """
    comp = str(comprobante_externo).strip().upper()
    dest = str(destino).strip().upper()
    clave = comp[:2] + dest[:4]
    if clave == "46AP00":
        return "AP"
    if clave in ("31SODI", "31WALM", "31EASY", "31REND", "31HIPE"):
        return "GT"
    if clave == "55LO B":
        return "LB"
    if clave == "46SG00":
        return "SG"
    if clave in ("91SG00", "91AP00", "91CORO"):
        return "CAP"
    return "MY"


def resolver_canal_con_ces(
    canal_ppal: str,
    rack_lines: int,
    est_lines: int,
    es_ces: bool,
) -> str:
    """Aplica las reglas finales de negocio para el canal DERCO.

    AP + Est > Rack          -> AP_E
    AP + Rack >= Est         -> AP_R (incluye empate)
    MY + es_ces=True         -> CES
    resto                     -> canal_ppal (GT/SG/CAP/MY/LB)
    """
    if canal_ppal == "AP":
        return "AP_E" if est_lines > rack_lines else "AP_R"
    if canal_ppal == "MY" and es_ces:
        return "CES"
    return canal_ppal


# ============================================================================
# BASE CES
# ============================================================================

def cargar_base_ces(
    path: str,
    log_callback: Optional[Callable[[str], None]] = None,
) -> tuple[set[str], Callable[[Any], Optional[str]]]:
    """Lee Base CES (base 1 y base 2) desde el archivo Excel.

    base 1 es la fuente solida. base 2 se valida contenida en base 1
    (los faltantes se reportan via log_callback y se agregan al set).

    Args:
        path: Path al archivo Base CES.xlsx.
        log_callback: callable opcional para reportar progreso/validaciones.
                      Si es None, no se reporta nada.

    Returns:
        (ces_set, matcher) donde matcher(destino) -> nombre_ces | None.
    """
    import pandas as pd  # import diferido: solo si se carga CES

    def _log(msg: str) -> None:
        if log_callback is not None:
            log_callback(msg)

    excluir = {
        norm_str_canal("Nombre del solicitante"),
        norm_str_canal("Nombre del Destinatario"),
        norm_str_canal("nan"),
        "",
    }

    b1 = pd.read_excel(path, sheet_name="base 1", header=2)
    b2 = pd.read_excel(path, sheet_name="base 2", header=1)

    base1_nombres: set[str] = set()
    for col_idx in (1, 2):  # solicitante + destinatario
        if col_idx < b1.shape[1]:
            base1_nombres.update(b1.iloc[:, col_idx].dropna().astype(str).tolist())
    base1_norm = {norm_str_canal(n) for n in base1_nombres} - excluir

    base2_nombres: set[str] = set()
    if b2.shape[1] > 0:
        base2_nombres.update(b2.iloc[:, 0].dropna().astype(str).tolist())
    base2_norm = {norm_str_canal(n) for n in base2_nombres} - excluir

    faltantes = sorted(base2_norm - base1_norm)
    _log(f"  Base CES base 1: {len(base1_norm)} concesionarios")
    _log(f"  Base CES base 2: {len(base2_norm)} concesionarios")
    if faltantes:
        _log(f"  [!] {len(faltantes)} de base 2 NO estan en base 1 (se agregan al set):")
        for f in faltantes:
            _log(f"        - {f}")
    else:
        _log("  base 2 esta totalmente contenida en base 1.")

    ces_set = base1_norm | base2_norm
    ces_list = sorted(ces_set, key=len, reverse=True)

    def matcher(destino: Any) -> Optional[str]:
        d = norm_str_canal(str(destino).split("/")[0])  # parte empresa antes del /
        if len(d) < 6:
            return None
        if d in ces_set:
            return d
        for c in ces_list:
            n = min(len(d), len(c))
            if n >= 10 and d[:n] == c[:n]:
                return c
        return None

    return ces_set, matcher
