"""
cleanup_orphaned.py — Limpia niveles buy_open sin respaldo en Kraken spot.

Caso de uso: el usuario movió BTC/ETH a Staking, Earn u otra cuenta y el bot
quedó con niveles buy_open que no puede vender (EOrder:Insufficient).

El script calcula el deficit (esperado - real en spot) y limpia los niveles
necesarios ordenados de menor precio hacia arriba (menor pérdida potencial).

Uso:
    py crypto_bot/cleanup_orphaned.py              # detecta y limpia deficit
    py crypto_bot/cleanup_orphaned.py --dry-run    # solo muestra, no modifica
    py crypto_bot/cleanup_orphaned.py --all        # limpia todos los buy_open
    py crypto_bot/cleanup_orphaned.py --par ETH_USDT  # solo un par
"""

import sys
import json
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

from crypto_bot import config, notifier
from crypto_bot.exchange_client import get_exchange

KRAKEN_BALANCE_KEYS = {
    "BTC_USDT": ["XXBT", "XBT"],
    "ETH_USDT": ["XETH", "ETH"],
}

_TOLERANCE = 0.000001  # 1 satoshi


def _load_estado(par: str) -> dict:
    path = config.PARES_CONFIG[par]["estado_path"]
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _save_estado(par: str, estado: dict):
    path = config.PARES_CONFIG[par]["estado_path"]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(estado, f, indent=2, ensure_ascii=False)


def cleanup_par(exchange, par: str, dry_run: bool, force_all: bool) -> list[dict]:
    """
    Limpia niveles huérfanos para un par.
    Retorna lista de dicts con los niveles limpiados.
    """
    estado = _load_estado(par)
    if not estado:
        print(f"[{par}] Sin estado_grid.json — saltando")
        return []

    coin = par.split("_")[0]
    open_niveles = [n for n in estado["niveles"] if n["estado"] == "buy_open"]

    if not open_niveles:
        print(f"[{par}] Sin niveles buy_open — nada que limpiar")
        return []

    expected = round(sum(n["btc_qty"] for n in open_niveles), 8)

    if force_all:
        deficit = expected
        print(f"[{par}] --all: limpiando {len(open_niveles)} niveles ({expected:.8f} {coin})")
    else:
        try:
            balance = exchange.get_balance()
            bkeys = KRAKEN_BALANCE_KEYS.get(par, [])
            real = round(sum(balance.get(k, 0.0) for k in bkeys), 8)
        except Exception as e:
            print(f"[{par}] Error obteniendo balance Kraken: {e}")
            return []

        deficit = round(expected - real, 8)
        print(f"[{par}] {coin} esperado={expected:.8f} | real={real:.8f} | deficit={deficit:.8f}")

        if deficit <= _TOLERANCE:
            print(f"[{par}] Sin deficit — niveles OK")
            return []

    # Candidatos ordenados por precio ascendente (precio más bajo = menor pérdida al limpiar)
    candidatos = sorted(open_niveles, key=lambda n: n["precio"])

    a_limpiar = []
    cubierto = 0.0
    for nivel in candidatos:
        if not force_all and cubierto >= deficit - _TOLERANCE:
            break
        a_limpiar.append({
            "precio":   nivel["precio"],
            "btc_qty":  nivel["btc_qty"],
            "order_id": nivel.get("order_id"),
        })
        cubierto = round(cubierto + nivel["btc_qty"], 8)

    print(f"\n[{par}] {len(a_limpiar)} nivel(es) a limpiar:")
    for n in a_limpiar:
        print(f"  Nivel ${n['precio']:>10,.0f} | {n['btc_qty']:.8f} {coin} | order_id: {n['order_id']}")

    if dry_run:
        print(f"\n[{par}] DRY-RUN — no se modificó nada")
        return a_limpiar

    # Aplicar limpieza al JSON
    precios = {n["precio"] for n in a_limpiar}
    for nivel in estado["niveles"]:
        if nivel["precio"] in precios:
            nivel["estado"]    = "idle"
            nivel["btc_qty"]   = 0.0
            nivel["order_id"]  = None

    _save_estado(par, estado)
    print(f"[{par}] estado_grid.json actualizado — {len(a_limpiar)} niveles → idle")

    return a_limpiar


def main():
    parser = argparse.ArgumentParser(description="Limpia niveles buy_open sin respaldo spot en Kraken")
    parser.add_argument("--dry-run",  action="store_true",
                        help="Solo muestra deficit, no modifica archivos")
    parser.add_argument("--all",      dest="force_all", action="store_true",
                        help="Limpia TODOS los buy_open sin verificar balance real")
    parser.add_argument("--par",      default=None,
                        help="Limitar a un par (ej: BTC_USDT). Default: todos los activos")
    args = parser.parse_args()

    pares = [args.par] if args.par else config.PARES_ACTIVOS

    exchange = get_exchange()
    total_limpiados = []

    for par in pares:
        if par not in config.PARES_CONFIG:
            print(f"Par {par} no está en PARES_CONFIG — saltando")
            continue
        print(f"\n{'='*55}")
        limpiados = cleanup_par(exchange, par, dry_run=args.dry_run, force_all=args.force_all)
        total_limpiados.extend([(par, n) for n in limpiados])

    print(f"\n{'='*55}")

    if not total_limpiados:
        print("Sin niveles huérfanos detectados.")
        return

    if args.dry_run:
        print(f"DRY-RUN completado — {len(total_limpiados)} nivel(es) serían limpiados.")
        return

    print(f"Limpieza completada: {len(total_limpiados)} nivel(es) → idle")

    lineas = []
    for par, n in total_limpiados:
        coin = par.split("_")[0]
        lineas.append(f"  ${n['precio']:,.0f} | {n['btc_qty']:.8f} {coin}")
    notifier.enviar_texto(
        f"🧹 <b>Limpieza niveles huérfanos</b>\n"
        f"{len(total_limpiados)} nivel(es) → idle (sin respaldo en spot):\n"
        + "\n".join(lineas)
    )


if __name__ == "__main__":
    main()
