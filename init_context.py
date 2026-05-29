#!/usr/bin/env python3
"""
init_context.py — Hook UserPromptSubmit (Claude Code harness)
Inyecta una linea de contexto real-time en cada mensaje:
fecha/hora Chile, git branch, crypto bot PnL, estado de logs.
Rapido (<1s), no bloquea, falla silenciosamente.
"""
import sys
import json
import sqlite3
import subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

BASE       = Path(r"C:\ClaudeWork")
CRYPTO_DB  = BASE / "crypto_bot" / "crypto_bot.db"
ESTADO_BTC = BASE / "crypto_bot" / "estado_grid.json"
ESTADO_ETH = BASE / "crypto_bot" / "estado_grid_ETH_USDT.json"
LOGS_DIR   = BASE / "logs"


def chile_now() -> tuple[str, str]:
    """Chile: UTC-3 permanente desde 2023 (eliminaron DST)."""
    utc  = datetime.now(timezone.utc)
    clt  = utc - timedelta(hours=3)
    return clt.strftime("%Y-%m-%d %H:%M"), clt.strftime("%Y-%m-%d")


def git_branch() -> str:
    try:
        b = subprocess.check_output(
            ["git", "branch", "--show-current"],
            cwd=str(BASE), text=True, timeout=2, stderr=subprocess.DEVNULL
        ).strip()
        return b or "main"
    except Exception:
        return "?"


def crypto_pnl(hoy: str) -> str:
    try:
        parts = []
        for path, coin in [(ESTADO_BTC, "BTC"), (ESTADO_ETH, "ETH")]:
            if path.exists():
                import json as _j
                eg     = _j.loads(path.read_text(encoding="utf-8"))
                precio = eg.get("precio_ultimo", 0)
                pnl    = eg.get("pnl_realizado_usdt", 0)
                parts.append(f"{coin}${precio:,.0f}(+${pnl:.2f})")
        if CRYPTO_DB.exists():
            conn = sqlite3.connect(str(CRYPTO_DB))
            row  = conn.execute(
                "SELECT COALESCE(SUM(pnl),0) FROM trades WHERE tipo='SELL' AND timestamp LIKE ?",
                (f"{hoy}%",)
            ).fetchone()
            conn.close()
            pnl_hoy = row[0] if row else 0.0
            parts.append(f"hoy+${pnl_hoy:.2f}")
        return " ".join(parts) if parts else "off"
    except Exception:
        return "err"


def log_status() -> str:
    try:
        cutoff = datetime.now().timestamp() - 1800  # última media hora
        for f in sorted(LOGS_DIR.glob("*.log"), key=lambda x: x.stat().st_mtime, reverse=True)[:6]:
            if f.stat().st_mtime < cutoff:
                continue
            text = f.read_text(encoding="utf-8", errors="ignore")
            if "ERROR" in text or "FALLO" in text or "SELL BLOCKED" in text:
                return "⚠️errores"
        return "OK"
    except Exception:
        return "?"


def main():
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except Exception:
        payload = {}

    hora, hoy = chile_now()
    branch    = git_branch()
    crypto    = crypto_pnl(hoy)
    logs      = log_status()

    # Una sola linea compacta — no satura contexto, pero me ancla a la realidad
    print(f"[{hora} CLT | git:{branch} | bot:{crypto} | logs:{logs}]")


if __name__ == "__main__":
    main()
