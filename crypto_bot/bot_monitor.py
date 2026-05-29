"""
Bot Monitor — reporte diario automatico via Telegram.
Compara estado real de Kraken vs lo que el bot rastrea en SQLite/JSON.
Detecta: untracked crypto, posiciones sin SELL, precios cerca del borde del grid.

Uso:
    py crypto_bot/bot_monitor.py           # envia reporte ahora
    py crypto_bot/bot_monitor.py --dry-run # imprime sin enviar Telegram
"""

import sys
import json
import sqlite3
import argparse
from pathlib import Path
from datetime import datetime, timezone, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

from crypto_bot import config, notifier
from crypto_bot.exchange_client import get_exchange

# Posibles keys en Kraken balance API para cada par (spot, sin Earn/.B)
KRAKEN_BALANCE_KEYS = {
    "BTC_USDT": ["XXBT", "XBT"],
    "ETH_USDT": ["XETH", "ETH"],
}

# Alerta si precio esta dentro del X% del borde del grid
BORDE_ALERTA_PCT = 8.0


def _leer_sqlite(db_path: Path) -> tuple[list, list]:
    """Retorna (trades_hoy, trades_total) como listas de dicts."""
    if not db_path.exists():
        return [], []
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    hoy = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    c.execute(
        "SELECT par, tipo, precio, qty, pnl, order_id, timestamp FROM trades "
        "WHERE timestamp LIKE ? ORDER BY timestamp",
        (f"{hoy}%",),
    )
    trades_hoy = [dict(r) for r in c.fetchall()]

    c.execute(
        "SELECT par, tipo, precio, qty, pnl, order_id, timestamp FROM trades ORDER BY timestamp"
    )
    trades_total = [dict(r) for r in c.fetchall()]

    conn.close()
    return trades_hoy, trades_total


def _pnl_por_par(trades: list) -> dict:
    """Suma pnl realizado por par."""
    totales = {}
    for t in trades:
        par = t["par"]
        totales[par] = totales.get(par, 0.0) + (t["pnl"] or 0.0)
    return totales


def _conteo_trades(trades: list) -> dict:
    """Retorna {par: {BUY: n, SELL: n}}."""
    conteo = {}
    for t in trades:
        par = t["par"]
        tipo = t["tipo"]
        if par not in conteo:
            conteo[par] = {"BUY": 0, "SELL": 0}
        conteo[par][tipo] = conteo[par].get(tipo, 0) + 1
    return conteo


def _leer_estado_grid(par: str) -> dict:
    """Lee el JSON de estado del grid para el par."""
    path = config.PARES_CONFIG[par]["estado_path"]
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _btc_esperado_en_cuenta(estado: dict) -> float:
    """Suma qty de todos los niveles buy_open."""
    return sum(
        n.get("btc_qty", 0.0)
        for n in estado.get("niveles", [])
        if n.get("estado") == "buy_open"
    )


def _verificar_ordenes_kraken(exchange, estado: dict) -> list[str]:
    """
    Consulta Kraken para cada buy_open y verifica que el order este filled.
    Retorna lista de advertencias.
    """
    warnings = []
    open_niveles = [
        n for n in estado.get("niveles", [])
        if n.get("estado") == "buy_open" and n.get("order_id")
    ]
    if not open_niveles:
        return []

    txids = ",".join(n["order_id"] for n in open_niveles)
    try:
        result = exchange._private("QueryOrders", {"txid": txids, "trades": "true"})
        for nivel in open_niveles:
            oid = nivel["order_id"]
            info = result.get(oid, {})
            if not info:
                # Kraken no devolvio la orden — probablemente es very old closed order.
                # No alertar: ordenes closed se purgan del historial activo de Kraken.
                continue
            kraken_status = info.get("status", "desconocido")
            if kraken_status == "open":
                warnings.append(
                    f"Nivel ${nivel['precio']:,.0f}: orden {oid} aun ABIERTA en Kraken "
                    f"(no filled) — bot no tiene BTC real en este nivel"
                )
            # closed/canceled = OK, no alertar
    except Exception:
        pass  # Fallo silencioso — no contaminar el reporte con errores de API
    return warnings


def _pnl_emoji(v: float) -> str:
    return "🟢" if v >= 0 else "🔴"


def _coin_symbol(par: str) -> str:
    return {"BTC_USDT": "₿", "ETH_USDT": "Ξ"}.get(par, "🪙")


def _alerta_borde_grid(estado: dict, precio_actual: float, par: str) -> str | None:
    """Retorna mensaje si el precio esta cerca del borde del grid."""
    lower = estado.get("grid_lower", 0)
    upper = estado.get("grid_upper", 0)
    if not lower or not upper:
        return None

    dist_lower_pct = (precio_actual - lower) / lower * 100
    dist_upper_pct = (upper - precio_actual) / upper * 100

    coin = par.split("_")[0]
    if dist_lower_pct <= BORDE_ALERTA_PCT:
        return (
            f"⚠️ {coin} al {dist_lower_pct:.1f}% del piso del grid "
            f"(${lower:,}). Considerar ajustar rango si sigue bajando."
        )
    if dist_upper_pct <= BORDE_ALERTA_PCT:
        return (
            f"⚠️ {coin} al {dist_upper_pct:.1f}% del techo del grid "
            f"(${upper:,}). Considerar ajustar rango si sigue subiendo."
        )
    return None


def generar_reporte(dry_run: bool = False) -> str:
    now_utc = datetime.now(timezone.utc)
    try:
        from zoneinfo import ZoneInfo
        now_cl = now_utc.astimezone(ZoneInfo("America/Santiago"))
    except Exception:
        now_cl = now_utc.astimezone(timezone(timedelta(hours=-4)))

    go_live = datetime(2026, 5, 27, tzinfo=timezone.utc)
    total_secs = (now_utc - go_live).total_seconds()
    dias_activo = int(total_secs // 86400)
    horas_activo = int((total_secs % 86400) // 3600)

    dias_es = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]
    meses_es = ["", "ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
    fecha_str = f"{dias_es[now_cl.weekday()]} {now_cl.day} {meses_es[now_cl.month]}, {now_cl.strftime('%H:%M')} CLT"

    exchange = get_exchange()
    db_path = config.BASE_DIR / "crypto_bot.db"

    trades_hoy, trades_total = _leer_sqlite(db_path)
    pnl_hoy = _pnl_por_par(trades_hoy)
    pnl_total = _pnl_por_par(trades_total)
    conteo_hoy = _conteo_trades(trades_hoy)
    conteo_total = _conteo_trades(trades_total)

    pnl_hoy_sum = sum(pnl_hoy.values())
    pnl_total_sum = sum(pnl_total.values())
    capital_total = sum(config.PARES_CONFIG[p]["capital_usdt"] for p in config.PARES_ACTIVOS)
    roi_total = pnl_total_sum / capital_total * 100 if capital_total else 0

    try:
        kraken_balance = exchange.get_balance()
    except Exception:
        kraken_balance = {}

    advertencias = []
    bloques_pares = []

    for par in config.PARES_ACTIVOS:
        cfg = config.PARES_CONFIG[par]
        capital = cfg["capital_usdt"]
        estado = _leer_estado_grid(par)
        coin = par.split("_")[0]
        symbol = _coin_symbol(par)

        precio_actual = estado.get("precio_ultimo", 0.0)
        pnl_par_total = round(pnl_total.get(par, 0.0), 4)
        pnl_par_hoy = round(pnl_hoy.get(par, 0.0), 4)
        roi_par = pnl_par_total / capital * 100 if capital else 0

        ct = conteo_total.get(par, {"BUY": 0, "SELL": 0})
        ct_hoy = conteo_hoy.get(par, {"BUY": 0, "SELL": 0})
        n_open = sum(1 for n in estado.get("niveles", []) if n.get("estado") == "buy_open")

        # Solo alertar exceso (crypto no rastreado); déficit puede ser falso positivo por timing.
        bkeys = KRAKEN_BALANCE_KEYS.get(par, [])
        real = round(sum(kraken_balance.get(k, 0.0) for k in bkeys), 8)
        esperado = round(_btc_esperado_en_cuenta(estado), 8)
        diff = round(real - esperado, 8)
        diff_usd = round(diff * precio_actual, 2) if precio_actual else 0

        if diff_usd >= 1.0:
            advertencias.append(
                f"{symbol} {diff:.8f} {coin} sin rastrear en bot (~${diff_usd:.2f})"
                f" — vender manualmente o dejar acumular"
            )

        alerta_borde = _alerta_borde_grid(estado, precio_actual, par)
        if alerta_borde:
            advertencias.append(alerta_borde)

        warns_ordenes = _verificar_ordenes_kraken(exchange, estado)
        advertencias.extend(warns_ordenes)

        lower = estado.get("grid_lower", 0)
        upper = estado.get("grid_upper", 0)
        pos_pct = (precio_actual - lower) / (upper - lower) * 100 if upper > lower else 0
        def _fmt_k(v: float) -> str:
            if v < 1000:
                return f"${v:,}"
            k = v / 1000
            return f"${k:.0f}k" if k == int(k) else f"${k:.1f}k"
        lower_k = _fmt_k(lower)
        upper_k = _fmt_k(upper)
        n_abiertas = f"{n_open} abierta{'s' if n_open != 1 else ''}"

        bloques_pares.append(
            f"{symbol} <b>{coin}/USDT</b>\n"
            f"├ 📍 <b>${precio_actual:,.0f}</b> · {pos_pct:.0f}% del rango [{lower_k}–{upper_k}]\n"
            f"├ Hoy: <b>{pnl_par_hoy:+.4f} USDT</b> {_pnl_emoji(pnl_par_hoy)} · {ct_hoy['BUY']}🟢 {ct_hoy['SELL']}🔴\n"
            f"└ Total: <b>{pnl_par_total:+.4f} USDT</b> ({roi_par:+.2f}%) · {ct['BUY']}🟢 {ct['SELL']}🔴 · {n_abiertas}"
        )

    prefijo = "[PAPER] " if config.MODO_PAPER_TRADING else ""
    lineas = []

    lineas.append(
        f"🤖 {prefijo}<b>Crypto Bot</b> · {fecha_str}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"⏱ {dias_activo}d {horas_activo}h activo · 💰 ${capital_total:,.0f} USDT"
    )

    lineas.append(
        f"💵 <b>Resultados</b>\n"
        f"├ Hoy: <b>{pnl_hoy_sum:+.4f} USDT</b> {_pnl_emoji(pnl_hoy_sum)}\n"
        f"└ Acumulado: <b>{pnl_total_sum:+.4f} USDT</b> · ROI <b>{roi_total:+.2f}%</b>"
    )

    lineas.extend(bloques_pares)

    if advertencias:
        n = len(advertencias)
        ads = "\n".join(f"• {a}" for a in advertencias)
        lineas.append(f"🔔 <b>{n} alerta{'s' if n != 1 else ''}</b>\n{ads}")
    else:
        lineas.append("✅ Sin alertas")

    msg = "\n\n".join(lineas)

    if dry_run:
        print(msg)
    else:
        notifier.enviar_texto(msg)

    return msg


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Crypto Bot Monitor")
    parser.add_argument("--dry-run", action="store_true", help="Imprime reporte sin enviar Telegram")
    args = parser.parse_args()
    generar_reporte(dry_run=args.dry_run)
