"""
actualizar_lookups_tenis.py
Descarga datos ATP de Jeff Sackmann (GitHub) y reconstruye los 4 JSON de lookup
que usa tenis_features.py / predictor_tiempo_real.py.

Archivos generados en agente_apuestas/models/:
    tenis_elo_state.json    — ELO actual por jugador (K=32, init=1500)
    tenis_rank_state.json   — Rank ATP + pts más recientes
    tenis_h2h.json          — H2H acumulado entre pares de jugadores
    tenis_winrate.json      — Win rate overall y por superficie (últimos 12 meses)

Uso:
    py agente_apuestas/actualizar_lookups_tenis.py            # 2015–año actual
    py agente_apuestas/actualizar_lookups_tenis.py 2020 2026  # rango personalizado
"""

import sys
import io
import json
import math
import requests
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).parent
MODELS   = BASE_DIR / "models"

SACKMANN_URL = "https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_{year}.csv"
DEFAULT_START = 2015
ELO_K    = 32
ELO_INIT = 1500.0

# Superficies en el mismo encoding que entrenamiento
SURFACE_ENC = {"Hard": 0, "Clay": 1, "Grass": 2, "Carpet": 3}


def _log(msg: str):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [TENIS-UPDATE] {msg}", flush=True)


def _descargar_csv(year: int) -> list[dict]:
    """Descarga atp_matches_{year}.csv y retorna lista de dicts."""
    url = SACKMANN_URL.format(year=year)
    try:
        r = requests.get(url, timeout=30)
        if r.status_code == 404:
            _log(f"  {year}: no disponible (404)")
            return []
        r.raise_for_status()
        lines = r.text.splitlines()
        if not lines:
            return []
        headers = [h.strip() for h in lines[0].split(",")]
        rows = []
        for line in lines[1:]:
            if not line.strip():
                continue
            vals = line.split(",")
            row = {headers[i]: vals[i].strip() if i < len(vals) else "" for i in range(len(headers))}
            rows.append(row)
        _log(f"  {year}: {len(rows)} partidos descargados")
        return rows
    except Exception as e:
        _log(f"  {year}: ERROR — {e}")
        return []


def _elo_expected(elo_a: float, elo_b: float) -> float:
    return 1.0 / (1.0 + 10.0 ** ((elo_b - elo_a) / 400.0))


def _parse_date(date_str: str):
    """Parsea tourney_date YYYYMMDD → date. Retorna None si inválido."""
    s = str(date_str).strip()
    if len(s) == 8:
        try:
            return date(int(s[:4]), int(s[4:6]), int(s[6:8]))
        except ValueError:
            pass
    return None


def construir_lookups(years: list[int]) -> tuple[dict, dict, dict, dict]:
    """
    Procesa partidos de todos los años y devuelve:
        elo_state, rank_state, h2h, winrate
    """
    elo_state:  dict[str, float] = defaultdict(lambda: ELO_INIT)
    rank_state: dict[str, dict]  = {}
    h2h:        dict[str, dict]  = {}
    # Para winrate: guardar historial de partidos por jugador
    historial:  dict[str, list]  = defaultdict(list)  # player → [{date, surface, win}]

    cutoff_wr = date.today() - timedelta(days=365)  # últimos 12 meses para win rate

    for year in years:
        rows = _descargar_csv(year)
        for row in rows:
            winner = row.get("winner_name", "").strip()
            loser  = row.get("loser_name",  "").strip()
            if not winner or not loser:
                continue

            surface_raw = row.get("surface", "Hard").strip()
            surface_enc = SURFACE_ENC.get(surface_raw, 0)
            tourney_date = _parse_date(row.get("tourney_date", ""))

            # ─── ELO update ───────────────────────────────────────────────
            elo_w = elo_state[winner]
            elo_l = elo_state[loser]
            expected_w = _elo_expected(elo_w, elo_l)
            elo_state[winner] = elo_w + ELO_K * (1.0 - expected_w)
            elo_state[loser]  = elo_l + ELO_K * (0.0 - (1.0 - expected_w))

            # ─── Rank state (más reciente) ────────────────────────────────
            try:
                wr_rank = int(float(row.get("winner_rank", 0) or 0))
                lr_rank = int(float(row.get("loser_rank",  0) or 0))
                wr_pts  = int(float(row.get("winner_rank_points", 0) or 0))
                lr_pts  = int(float(row.get("loser_rank_points",  0) or 0))
            except (ValueError, TypeError):
                wr_rank = lr_rank = wr_pts = lr_pts = 0

            if wr_rank > 0:
                rank_state[winner] = {"rank": wr_rank, "pts": wr_pts}
            if lr_rank > 0:
                rank_state[loser]  = {"rank": lr_rank, "pts": lr_pts}

            # ─── H2H ─────────────────────────────────────────────────────
            key = "|".join(sorted([winner, loser]))
            if key not in h2h:
                players = sorted([winner, loser])
                h2h[key] = {"p1": players[0], "p2": players[1],
                             "p1_wins": 0, "p2_wins": 0, "total": 0}
            entry = h2h[key]
            if winner == entry["p1"]:
                entry["p1_wins"] += 1
            else:
                entry["p2_wins"] += 1
            entry["total"] += 1

            # ─── Historial win rate ───────────────────────────────────────
            if tourney_date:
                historial[winner].append({"date": tourney_date, "surface": surface_enc, "win": 1})
                historial[loser].append( {"date": tourney_date, "surface": surface_enc, "win": 0})

    # ─── Construir winrate (últimos 12 meses) ─────────────────────────────────
    winrate: dict[str, dict] = {}
    for player, matches in historial.items():
        recent = [m for m in matches if m["date"] >= cutoff_wr]
        all_matches = matches  # overall = todo el historial

        def calc_wr(subset):
            if not subset:
                return 0.5
            return sum(m["win"] for m in subset) / len(subset)

        wr_overall = calc_wr(recent) if recent else calc_wr(all_matches[-50:])

        by_surface: dict[str, float] = {}
        for surf_enc in range(4):
            surf_matches = [m for m in recent if m["surface"] == surf_enc]
            if not surf_matches:
                # Fallback a historial completo si no hay recientes en esa superficie
                surf_all = [m for m in all_matches if m["surface"] == surf_enc]
                by_surface[str(surf_enc)] = calc_wr(surf_all[-20:]) if surf_all else wr_overall
            else:
                by_surface[str(surf_enc)] = calc_wr(surf_matches)

        winrate[player] = {"overall": round(wr_overall, 4), "by_surface": {k: round(v, 4) for k, v in by_surface.items()}}

    # Convertir elo_state a formato guardable
    elo_out: dict[str, dict] = {
        player: {"elo": round(elo, 1)} for player, elo in elo_state.items()
    }

    return elo_out, rank_state, h2h, winrate


def main():
    if len(sys.argv) >= 3:
        start_year = int(sys.argv[1])
        end_year   = int(sys.argv[2])
    elif len(sys.argv) == 2:
        start_year = int(sys.argv[1])
        end_year   = date.today().year
    else:
        start_year = DEFAULT_START
        end_year   = date.today().year

    years = list(range(start_year, end_year + 1))
    _log(f"Procesando años {years[0]}–{years[-1]} ({len(years)} temporadas)")

    elo_state, rank_state, h2h, winrate = construir_lookups(years)

    # Guardar los 4 archivos
    MODELS.mkdir(exist_ok=True)
    archivos = {
        "tenis_elo_state.json":  elo_state,
        "tenis_rank_state.json": rank_state,
        "tenis_h2h.json":        h2h,
        "tenis_winrate.json":    winrate,
    }
    for fname, data in archivos.items():
        path = MODELS / fname
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        _log(f"Guardado: {path} ({len(data)} entradas)")

    # Resumen
    top_elo = sorted(elo_state.items(), key=lambda x: x[1]["elo"], reverse=True)[:5]
    _log("Top 5 ELO:")
    for player, stats in top_elo:
        rk = rank_state.get(player, {}).get("rank", "?")
        _log(f"  {player}: ELO={stats['elo']:.0f} rank={rk}")

    _log("Listo. Lookups actualizados.")


if __name__ == "__main__":
    main()
