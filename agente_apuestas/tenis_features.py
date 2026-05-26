import sys
sys.stdout.reconfigure(encoding="utf-8")

"""
tenis_features.py
Fixtures ATP + features para xgboost_tenis_v2.pkl.
Fuente fixtures: api-sports Tennis (v1.tennis.api-sports.io)
Fuente lookups:  models/tenis_elo_state.json, tenis_rank_state.json,
                 tenis_h2h.json, tenis_winrate.json
"""

import json
import math
import requests
from datetime import date, datetime
from pathlib import Path

BASE_DIR  = Path(__file__).parent
MODELS    = BASE_DIR / "models"

# Encodings — mismos que entrenamiento (pd.factorize del dataset dissfya)
SURFACE_ENC = {"Hard": 0, "Clay": 1, "Grass": 2, "Carpet": 3, "hard": 0, "clay": 1, "grass": 2}
SERIES_ENC  = {"International": 0, "International Gold": 1, "Masters": 1,
               "Masters Cup": 3, "Grand Slam": 4, "ATP Finals": 3,
               "Masters 1000": 2, "250": 0, "500": 1, "1000": 2}
GRAND_SLAMS = {"Roland Garros", "Australian Open", "Wimbledon", "US Open",
               "French Open", "Roland-Garros"}

# api-sports Tennis
TENNIS_BASE = "https://v1.tennis.api-sports.io"


def _log(msg: str):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [TENIS] {msg}", flush=True)


# ─────────────────────────────────────────────────────────────────────────────
# CARGA DE LOOKUPS
# ─────────────────────────────────────────────────────────────────────────────

_elo_state   = None
_rank_state  = None
_h2h_lookup  = None
_wr_lookup   = None


def _cargar_lookups():
    global _elo_state, _rank_state, _h2h_lookup, _wr_lookup
    if _elo_state is not None:
        return
    for attr, fname in [("_elo_state", "tenis_elo_state.json"),
                        ("_rank_state", "tenis_rank_state.json"),
                        ("_h2h_lookup", "tenis_h2h.json"),
                        ("_wr_lookup",  "tenis_winrate.json")]:
        path = MODELS / fname
        if path.exists():
            with open(path, encoding="utf-8") as f:
                globals()[attr] = json.load(f)
        else:
            globals()[attr] = {}
    n_elo = len(_elo_state or {})
    _log(f"Lookups cargados: {n_elo} jugadores con ELO")


def _get_elo(player: str) -> float:
    _cargar_lookups()
    if player in _elo_state:
        return _elo_state[player]["elo"]
    # Búsqueda parcial por apellido
    for name, data in _elo_state.items():
        tok = player.split()[-1].lower()
        if len(tok) >= 4 and tok in name.lower():
            return data["elo"]
    return 1500.0


def _get_rank(player: str) -> tuple[int, int]:
    """Retorna (rank, pts). Default (999, 0) si no encontrado."""
    _cargar_lookups()
    if player in _rank_state:
        r = _rank_state[player]
        return r.get("rank", 999), r.get("pts", 0)
    tok = player.split()[-1].lower() if player else ""
    for name, data in _rank_state.items():
        if len(tok) >= 4 and tok in name.lower():
            return data.get("rank", 999), data.get("pts", 0)
    return 999, 0


def _get_h2h(p1: str, p2: str) -> dict:
    """Retorna {p1_wins, p2_wins, total}."""
    _cargar_lookups()
    key = "|".join(sorted([p1, p2]))
    if key not in _h2h_lookup:
        return {"p1_wins": 0, "p2_wins": 0, "total": 0}
    entry = _h2h_lookup[key]
    # Normalizar a p1/p2 en el orden solicitado
    if entry.get("p1") == p1:
        return {"p1_wins": entry["p1_wins"], "p2_wins": entry["p2_wins"], "total": entry["total"]}
    return {"p1_wins": entry["p2_wins"], "p2_wins": entry["p1_wins"], "total": entry["total"]}


def _get_winrate(player: str, surface_enc: int) -> tuple[float, float]:
    """Retorna (winrate_overall_10, winrate_surface_10)."""
    _cargar_lookups()
    data = _wr_lookup.get(player)
    if not data:
        tok = player.split()[-1].lower() if player else ""
        for name, d in _wr_lookup.items():
            if len(tok) >= 4 and tok in name.lower():
                data = d
                break
    if not data:
        return 0.5, 0.5
    wr_all  = data.get("overall", 0.5)
    wr_surf = data.get("by_surface", {}).get(str(surface_enc), wr_all)
    return wr_all, wr_surf


# ─────────────────────────────────────────────────────────────────────────────
# FIXTURES — api-sports Tennis
# ─────────────────────────────────────────────────────────────────────────────

def get_tenis_fixtures_hoy(fecha: str = None) -> list[dict]:
    """
    Obtiene partidos ATP del día via api-sports Tennis.
    Retorna lista de dicts con keys: p1, p2, surface, series_enc,
    is_best_of_5, round_enc, is_indoor, tournament, fixture_id, odds_p1, odds_p2.
    """
    from config import HEADERS_APISPORTS
    if fecha is None:
        fecha = date.today().isoformat()

    try:
        resp = requests.get(
            f"{TENNIS_BASE}/fixtures",
            headers=HEADERS_APISPORTS,
            params={"date": fecha, "type": "Singles", "league": "1"},  # ATP Singles
            timeout=15,
        )
        if resp.status_code != 200:
            _log(f"api-sports tennis HTTP {resp.status_code} — sin fixtures")
            return []
        data = resp.json()
        if data.get("errors"):
            _log(f"api-sports tennis error: {data['errors']}")
            return []
    except Exception as e:
        _log(f"Fixtures tenis no disponibles: {e}")
        return []

    partidos = []
    for f in data.get("response", []):
        estado = f.get("status", {}).get("short", "")
        if estado not in ("NS", "Not Started"):
            continue
        try:
            p1 = f["players"]["home"]["name"]
            p2 = f["players"]["away"]["name"]
        except (KeyError, TypeError):
            continue

        tournament = f.get("tournament", {}).get("name", "")
        surface_raw = f.get("tournament", {}).get("surface", "Hard")
        surface_enc = SURFACE_ENC.get(surface_raw, 0)

        is_best_of_5 = int(any(gs in tournament for gs in GRAND_SLAMS))
        series_enc = 4 if is_best_of_5 else SERIES_ENC.get(
            f.get("tournament", {}).get("type", "International"), 0)

        round_str = f.get("round", "")
        round_enc = _encode_round(round_str)
        is_indoor = int("indoor" in str(f.get("tournament", {}).get("type", "")).lower())

        partidos.append({
            "fixture_id":   f.get("id"),
            "p1":           p1,
            "p2":           p2,
            "tournament":   tournament,
            "surface":      surface_raw,
            "surface_enc":  surface_enc,
            "series_enc":   series_enc,
            "is_best_of_5": is_best_of_5,
            "round_enc":    round_enc,
            "is_indoor":    is_indoor,
            "fecha":        fecha,
        })

    _log(f"{len(partidos)} partidos ATP singles hoy ({fecha})")
    return partidos


def _encode_round(round_str: str) -> int:
    """Mapea nombre de ronda a entero (mayor = mas tarde en torneo)."""
    r = round_str.lower()
    if "final" in r and "semi" not in r and "quarter" not in r:
        return 7
    if "semi" in r:
        return 6
    if "quarter" in r:
        return 5
    if "round of 16" in r or "r16" in r:
        return 4
    if "round of 32" in r or "r32" in r:
        return 3
    if "round of 64" in r or "r64" in r:
        return 2
    if "round of 128" in r or "r128" in r:
        return 1
    return 1  # default 1ra ronda


# ─────────────────────────────────────────────────────────────────────────────
# CONSTRUIR FEATURES
# ─────────────────────────────────────────────────────────────────────────────

def construir_features_tenis(fixture: dict) -> dict | None:
    """
    Dado un fixture de get_tenis_fixtures_hoy(), construye el vector de features
    para xgboost_tenis_v2.pkl.

    El modelo fue entrenado con (favorito, underdog) donde favorito = mejor ranked.
    Retorna feats dict + metadata: {'features': {...}, 'fav': p1_o_p2, 'und': otro}.
    """
    _cargar_lookups()

    p1, p2 = fixture["p1"], fixture["p2"]
    surface_enc  = fixture.get("surface_enc", 0)
    series_enc   = fixture.get("series_enc", 0)
    is_best_of_5 = fixture.get("is_best_of_5", 0)
    round_enc    = fixture.get("round_enc", 1)
    is_indoor    = fixture.get("is_indoor", 0)

    # Rankings y ELO
    rank1, pts1 = _get_rank(p1)
    rank2, pts2 = _get_rank(p2)
    elo1 = _get_elo(p1)
    elo2 = _get_elo(p2)

    # Favorito = mejor ranked (menor número = mejor posición)
    if rank1 <= rank2:
        fav, und = p1, p2
        rank_fav, rank_und = rank1, rank2
        pts_fav, pts_und   = pts1, pts2
        elo_fav, elo_und   = elo1, elo2
    else:
        fav, und = p2, p1
        rank_fav, rank_und = rank2, rank1
        pts_fav, pts_und   = pts2, pts1
        elo_fav, elo_und   = elo2, elo1

    elo_diff  = elo_fav - elo_und
    proba_elo = 1.0 / (1.0 + 10.0 ** (-elo_diff / 400.0))

    rank_diff = rank_und - rank_fav  # positivo = fav mejor
    pts_diff  = pts_fav - pts_und
    log_rank_diff = math.log1p(abs(rank_diff)) * (1 if rank_diff >= 0 else -1)
    log_pts_diff  = math.log1p(abs(pts_diff)) * (1 if pts_diff >= 0 else -1)

    # Win rates
    wr_fav_all, wr_fav_surf = _get_winrate(fav, surface_enc)
    wr_und_all, wr_und_surf = _get_winrate(und, surface_enc)

    # H2H
    h2h = _get_h2h(fav, und)
    h2h_wins_fav = h2h["p1_wins"]
    h2h_wins_und = h2h["p2_wins"]
    h2h_n        = h2h["total"]
    h2h_diff     = h2h_wins_fav - h2h_wins_und

    # Días desde último partido (no disponible en tiempo real → 7 como default razonable)
    dias_fav = 7.0
    dias_und = 7.0

    feats = {
        "rank_fav":        float(rank_fav),
        "rank_und":        float(rank_und),
        "rank_diff":       float(rank_diff),
        "log_rank_diff":   float(log_rank_diff),
        "pts_fav":         float(pts_fav),
        "pts_und":         float(pts_und),
        "pts_diff":        float(pts_diff),
        "log_pts_diff":    float(log_pts_diff),
        "elo_fav":         float(elo_fav),
        "elo_und":         float(elo_und),
        "elo_diff":        float(elo_diff),
        "proba_elo_fav":   float(proba_elo),
        "surface_enc":     float(surface_enc),
        "series_enc":      float(series_enc),
        "is_best_of_5":    float(is_best_of_5),
        "round_enc":       float(round_enc),
        "is_indoor":       float(is_indoor),
        "winrate_fav_10":  float(wr_fav_all),
        "winrate_und_10":  float(wr_und_all),
        "winrate_diff_10": float(wr_fav_all - wr_und_all),
        "winrate_fav_surf_10": float(wr_fav_surf),
        "winrate_und_surf_10": float(wr_und_surf),
        "winrate_surf_diff":   float(wr_fav_surf - wr_und_surf),
        "h2h_wins_fav":    float(h2h_wins_fav),
        "h2h_wins_und":    float(h2h_wins_und),
        "h2h_n":           float(h2h_n),
        "h2h_diff":        float(h2h_diff),
        "dias_fav":        float(dias_fav),
        "dias_und":        float(dias_und),
        "dias_diff":       0.0,
    }

    return {"features": feats, "fav": fav, "und": und,
            "elo_fav": elo_fav, "elo_und": elo_und, "proba_elo_fav": proba_elo}
