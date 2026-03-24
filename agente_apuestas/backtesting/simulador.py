import sys
sys.stdout.reconfigure(encoding="utf-8")

"""
simulador.py
Registra apuestas "virtuales" a partir de las recomendaciones del agente.
Soporta dos estrategias de sizing:
  - flat:  monto fijo por apuesta (default $5.000 CLP)
  - kelly: Kelly Criterion fraccional (quarter Kelly, más conservador)

Cada apuesta se guarda en historico_apuestas.json con resultado_real=null.
resultado_checker.py lo completa después del partido.
"""

import json
import uuid
from datetime import datetime
from pathlib import Path

# ── Rutas ────────────────────────────────────────────────────────────────────
BACKTESTING_DIR  = Path(__file__).parent
HISTORICO_PATH   = BACKTESTING_DIR / "historico_apuestas.json"

# ── Configuración bankroll ────────────────────────────────────────────────────
BANKROLL_INICIAL = 100_000   # CLP
MONTO_FLAT       = 5_000     # CLP por apuesta flat
KELLY_FRACCION   = 0.25      # Quarter Kelly — más seguro que Kelly completo
KELLY_MAX_PCT    = 0.10      # Nunca más del 10% del bankroll en una apuesta


# ─────────────────────────────────────────────────────────────────────────────
# GESTIÓN DEL HISTORICO JSON
# ─────────────────────────────────────────────────────────────────────────────

def leer_historico() -> list[dict]:
    """Lee el JSON de apuestas. Retorna lista vacía si no existe."""
    if not HISTORICO_PATH.exists():
        return []
    with open(HISTORICO_PATH, encoding="utf-8") as f:
        return json.load(f)


def guardar_historico(apuestas: list[dict]) -> None:
    """Persiste la lista completa de apuestas al JSON."""
    HISTORICO_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(HISTORICO_PATH, "w", encoding="utf-8") as f:
        json.dump(apuestas, f, ensure_ascii=False, indent=2)


def get_bankroll_actual(apuestas: list[dict]) -> float:
    """
    Calcula el bankroll actual sumando retornos de apuestas ya resueltas.
    Las apuestas pendientes (resultado_real=None) no afectan el cálculo.
    """
    bankroll = BANKROLL_INICIAL
    for a in sorted(apuestas, key=lambda x: x.get("fecha_registro", "")):
        if a.get("retorno") is not None:
            bankroll += a["retorno"]
    return bankroll


# ─────────────────────────────────────────────────────────────────────────────
# CÁLCULO DE SIZING
# ─────────────────────────────────────────────────────────────────────────────

def calcular_kelly(prob_modelo: float, cuota: float, bankroll: float) -> float:
    """
    Kelly Criterion fraccional.
    f* = (p*b - q) / b   donde b = cuota - 1, p = prob, q = 1 - p
    Aplicamos KELLY_FRACCION (quarter Kelly) y cap de KELLY_MAX_PCT.
    Retorna 0 si el Kelly es negativo (no hay value).
    """
    b = cuota - 1
    p = prob_modelo
    q = 1 - p

    kelly_completo = (p * b - q) / b
    if kelly_completo <= 0:
        return 0.0   # Sin value — no apostar

    kelly_frac   = kelly_completo * KELLY_FRACCION
    kelly_monto  = bankroll * kelly_frac
    monto_maximo = bankroll * KELLY_MAX_PCT

    return round(min(kelly_monto, monto_maximo), 0)


# ─────────────────────────────────────────────────────────────────────────────
# FUNCIÓN PRINCIPAL: registrar apuesta
# ─────────────────────────────────────────────────────────────────────────────

def registrar_apuesta(recomendacion: dict, estrategia: str = "flat") -> dict | None:
    """
    Registra una apuesta virtual en historico_apuestas.json.

    Args:
        recomendacion: dict con los campos del agente (ver estructura abajo)
        estrategia:    "flat" | "kelly"

    Estructura esperada de recomendacion:
        {
          "fixture_id":    int,
          "fecha_partido": str (ISO),
          "liga":          str,
          "home":          str,
          "away":          str,
          "tipo_apuesta":  str,   # "1X2" | "BTTS" | "OVER_UNDER" | "DOUBLE_CHANCE"
          "seleccion":     str,   # "HOME" | "DRAW" | "AWAY" | "SI" | "NO" | "Over 2.5" | etc
          "cuota":         float,
          "prob_modelo":   float, # probabilidad estimada (0-1)
        }

    Returns:
        El dict de la apuesta guardada, o None si no hay value positivo con Kelly.
    """
    prob   = recomendacion["prob_modelo"]
    cuota  = recomendacion["cuota"]
    prob_i = round(1 / cuota, 4)   # probabilidad implícita del bookmaker
    value  = round(prob - prob_i, 4)

    apuestas = leer_historico()
    bankroll = get_bankroll_actual(apuestas)

    # Calcular monto según estrategia
    if estrategia == "kelly":
        monto = calcular_kelly(prob, cuota, bankroll)
        if monto == 0:
            print(f"[INFO] Kelly=0 — sin value positivo para "
                  f"{recomendacion['home']} vs {recomendacion['away']} "
                  f"({recomendacion['tipo_apuesta']} {recomendacion['seleccion']})")
            return None
    else:
        monto = MONTO_FLAT

    apuesta = {
        "id":                uuid.uuid4().hex[:12],
        "fixture_id":        recomendacion["fixture_id"],
        "fecha_partido":     recomendacion["fecha_partido"],
        "fecha_registro":    datetime.now().isoformat(timespec="seconds"),
        "liga":              recomendacion.get("liga", ""),
        "home":              recomendacion["home"],
        "away":              recomendacion["away"],
        "tipo_apuesta":      recomendacion["tipo_apuesta"],
        "seleccion":         recomendacion["seleccion"],
        "cuota":             cuota,
        "prob_modelo":       prob,
        "prob_implicita":    prob_i,
        "value":             value,
        "monto_apostado":    monto,
        "estrategia":        estrategia,
        "bankroll_antes":    bankroll,
        # Campos a completar por resultado_checker.py
        "resultado_real":    None,
        "score_final":       None,
        "ganado":            None,
        "retorno":           None,
    }

    apuestas.append(apuesta)
    guardar_historico(apuestas)

    print(f"[OK] Apuesta registrada | {apuesta['home']} vs {apuesta['away']} | "
          f"{apuesta['tipo_apuesta']} → {apuesta['seleccion']} @ {cuota} | "
          f"Value: {value:+.1%} | Monto: ${monto:,.0f} | Bankroll: ${bankroll:,.0f}")

    return apuesta


def listar_pendientes() -> list[dict]:
    """Retorna apuestas que aún no tienen resultado_real."""
    return [a for a in leer_historico() if a.get("resultado_real") is None]


# ─────────────────────────────────────────────────────────────────────────────
# TEST / USO MANUAL
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("TEST — simulador.py")
    print("=" * 60)
    print()

    # Ejemplo de recomendación (como la generaría el agente en Sprint 3)
    recomendacion_ejemplo = {
        "fixture_id":    1234567,
        "fecha_partido": "2026-03-22T20:00:00+00:00",
        "liga":          "Premier League",
        "home":          "Arsenal",
        "away":          "Chelsea",
        "tipo_apuesta":  "BTTS",
        "seleccion":     "SI",
        "cuota":         1.85,
        "prob_modelo":   0.64,   # El modelo dice 64% de probabilidad
    }

    print("--- Apuesta FLAT ---")
    a1 = registrar_apuesta(recomendacion_ejemplo, estrategia="flat")

    print()
    print("--- Apuesta KELLY ---")
    a2 = registrar_apuesta(recomendacion_ejemplo, estrategia="kelly")

    print()
    apuestas = leer_historico()
    bankroll = get_bankroll_actual(apuestas)
    pendientes = listar_pendientes()
    print(f"Total apuestas en historico: {len(apuestas)}")
    print(f"Apuestas pendientes:         {len(pendientes)}")
    print(f"Bankroll actual:             ${bankroll:,.0f} CLP")
