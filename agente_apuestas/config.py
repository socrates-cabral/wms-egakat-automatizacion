import sys
sys.stdout.reconfigure(encoding="utf-8")

import os
from pathlib import Path
from dotenv import load_dotenv

# ── Carga .env desde C:\ClaudeWork\ (patron estandar del proyecto) ──────────
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

# ── API Keys (nombres reales en .env) ────────────────────────────────────────
API_SPORTS_KEY   = os.getenv("CLAVE_API")             # api-sports.io
ODDS_API_KEY     = os.getenv("ODDS_KEY")              # the-odds-api.com  (agregar ODDS_KEY= en .env)
ODDS_IO_KEY      = os.getenv("API_KEY_ODDS")          # odds-api.io v3    (apiKey query param)
BALLDONTLIE_KEY  = os.getenv("BBALL_KEY")             # balldontlie.io    (agregar BBALL_KEY= en .env)
# Sportmonks está en .env como URL completa; extraemos solo el token
_sportmonks_raw  = os.getenv("SPORTMONKS_KEY", "")
SPORTMONKS_KEY   = _sportmonks_raw.split("api_token=")[-1] if "api_token=" in _sportmonks_raw else _sportmonks_raw

# ── Base URLs ─────────────────────────────────────────────────────────────────
APISPORTS_BASE   = "https://v3.football.api-sports.io"
APISPORTS_BBALL  = "https://v2.basketball.api-sports.io"
ODDS_BASE        = "https://api.the-odds-api.com/v4"
ODDS_IO_BASE     = "https://api.odds-api.io/v3"
BALLDONTLIE_BASE = "https://api.balldontlie.io/v1"
SPORTMONKS_BASE  = "https://api.sportmonks.com/v3"

# ── Headers por API ───────────────────────────────────────────────────────────
HEADERS_APISPORTS = {
    "x-apisports-key": API_SPORTS_KEY
}
HEADERS_BALLDONTLIE = {
    "Authorization": BALLDONTLIE_KEY
}

# ── Ligas de interes (IDs estables en api-sports.io) ─────────────────────────
LIGAS_FUTBOL = {
    "Premier League":       39,
    "La Liga":              140,
    "Champions League":     2,
    "Ligue 1":              61,
    "Serie A":              135,
    "Bundesliga":           78,
    "Primera Division CL":  265,   # Chile
    "Copa Libertadores":    13,
}

# Ligas basketball api-sports.io
LIGAS_BASKETBALL = {
    "NBA":       12,
    "Euroliga":  120,
}

# Deportes adicionales — fuente: The Odds API (no api-sports)
# display_name → sport_key de The Odds API
OTROS_DEPORTES = {
    # Basketball
    "NBA":                 "basketball_nba",
    "Euroliga":            "basketball_euroleague",
    # American Football
    "NFL":                 "americanfootball_nfl",
    # Baseball
    "MLB":                 "baseball_mlb",
    # Tenis: se descubren dinámicamente en get_fixtures_otros_deportes_hoy()
    # (los sport_keys cambian cada semana según el torneo activo)
}

# ── Tipos de apuesta disponibles por deporte ─────────────────────────────────
BET_TYPES_FOOTBALL = [
    "1X2",          # Resultado final
    "DOUBLE_CHANCE", # 1X / X2 / 12
    "BTTS",          # Ambos anotan Si/No
    "OVER_UNDER",    # Total goles
    "ASIAN_HC",      # Handicap asiatico
    "HALF_TIME",     # Resultado al descanso
]

BET_TYPES_BASKETBALL = [
    "MONEYLINE",  # Ganador
    "SPREAD",     # Handicap puntos
    "TOTAL",      # Over/Under puntos
    "HALF_LINE",  # Primer tiempo
]

# ── Thresholds del modelo ─────────────────────────────────────────────────────
VALUE_THRESHOLD    = 0.05   # Minimo value positivo para recomendar (+5%)
MIN_CONFIDENCE     = 65     # Score minimo de confianza para mostrar apuesta (0-100) — subido 55→65 post-diagnóstico 2026-04-29
MAX_REQUESTS_DAILY = 90     # Dejar buffer de 10 de los 100 diarios gratuitos

# ── Transfermarkt IDs (verein/{id}) ──────────────────────────────────────────
# Fuente: URL https://www.transfermarkt.com/{slug}/startseite/verein/{id}
TRANSFERMARKT_IDS = {
    # Premier League
    "Arsenal":              11,
    "Chelsea":              631,
    "Liverpool":            31,
    "Manchester City":      281,
    "Manchester United":    985,
    "Tottenham":            148,
    "Newcastle":            762,
    "Aston Villa":          405,
    "West Ham":             379,
    "Brighton":             1237,
    # La Liga
    "Real Madrid":          418,
    "Barcelona":            131,
    "Atletico Madrid":      13,
    "Sevilla":              368,
    "Villarreal":           1050,
    "Real Sociedad":        681,
    "Athletic Bilbao":      621,
    "Betis":                150,
    # Serie A
    "Juventus":             506,
    "Inter Milan":          46,
    "AC Milan":             5,
    "Napoli":               6195,
    "AS Roma":              12,
    "Lazio":                398,
    "Atalanta":             800,
    "Fiorentina":           430,
    # Bundesliga
    "Bayern Munich":        27,
    "Borussia Dortmund":    16,
    "RB Leipzig":           23826,
    "Bayer Leverkusen":     15,
    "Eintracht Frankfurt":  24,
    "Borussia Monchengladbach": 23,
    # Ligue 1
    "PSG":                  583,
    "Olympique Marseille":  244,
    "Monaco":               162,
    "Olympique Lyonnais":   1041,
    "Lille":                1082,
    "Nice":                 417,

    # ── Aliases football-data.co.uk (nombres cortos usados en los CSVs históricos) ──
    "Man City":             281,    # = Manchester City
    "Man United":           985,    # = Manchester United
    "Inter":                46,     # = Inter Milan
    "Roma":                 12,     # = AS Roma
    "Dortmund":             16,     # = Borussia Dortmund
    "Ath Madrid":           13,     # = Atletico Madrid
    "Milan":                5,      # = AC Milan
    "Paris SG":             583,    # = PSG
    "Marseille":            244,    # = Olympique Marseille
    "Lyon":                 1041,   # = Olympique Lyonnais
    "Sociedad":             681,    # = Real Sociedad
    "Ath Bilbao":           621,    # = Athletic Bilbao
    "Leverkusen":           15,     # = Bayer Leverkusen
    "M'gladbach":           23,     # = Borussia Monchengladbach
    "Ein Frankfurt":        24,     # = Eintracht Frankfurt
    "Wolves":               543,    # Wolverhampton
    "Nott'm Forest":        703,    # Nottingham Forest
    "Leicester":            1003,   # Leicester City
    "Everton":              29,     # Everton
    "Brentford":            1148,   # Brentford
    "Crystal Palace":       873,    # Crystal Palace
    "Fulham":               931,    # Fulham
    "Bournemouth":          989,    # Bournemouth
}

# ── Temporada actual ──────────────────────────────────────────────────────────
SEASON_ACTUAL = 2024        # Plan gratuito api-sports: acceso hasta temporada 2024

# ── Ligas en modo OBSERVACIÓN ────────────────────────────────────────────────
# Detectan value bets y aparecen en reporte HTML, pero NO registran apuestas.
# Criterio de activación por liga:
#   UCL          → reentrenamiento con datos UCL (sept 2026) + backtesting n>=20 ROI>0
#   NBA          → modelo NBA propio (oct 2026) — Poisson retorna 0.5 para lineas >30
#   MLB / NFL    → fuera del foco principal — revisar Q3 2026
LIGAS_OBSERVACION = {
    "Champions League",
    "UEFA Champions League",
    "NBA",
    "MLB",
    "NFL",
}

# ── Modo Paper Trading ────────────────────────────────────────────────────────
# True  → apuestas ficticias, sin dinero real, mensajes Telegram con [PAPER]
# False → modo real (activar solo cuando el backtesting muestre ROI positivo
#         sostenido y tengas método de pago configurado en Betano)
MODO_PAPER_TRADING = True

# ── Telegram ──────────────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID", "")

# ── Límites de autonomía (CLP) ────────────────────────────────────────────────
# monto_automatico_max:   notifica directamente sin pedir permiso
# monto_requiere_permiso: espera SI/NO via Telegram antes de registrar
# monto_maximo_absoluto:  nunca superar este monto por apuesta
MONTO_AUTONOMO = int(os.getenv("MONTO_AUTONOMO", "1000"))

LIMITES_AUTONOMIA = {
    "monto_automatico_max":   1_000,   # CLP — notifica sin pedir permiso
    "monto_requiere_permiso": 5_000,   # CLP — espera tu SI/NO
    "monto_maximo_absoluto":  50_000,  # CLP — nunca superar
}
