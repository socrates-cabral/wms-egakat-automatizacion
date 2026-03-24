import sys
sys.stdout.reconfigure(encoding="utf-8")

"""
nombre_normalizer.py — Sprint 9
Normaliza nombres de equipos para hacer join entre:
  football-data.co.uk: "Man United", "Nott'm Forest"
  Understat:           "Manchester United", "Nottingham Forest"
  api-sports:          "Manchester United"

Instalar: py -m pip install fuzzywuzzy python-levenshtein
"""

import re
import json
from pathlib import Path
from datetime import datetime

try:
    from fuzzywuzzy import fuzz, process
    FUZZY_OK = True
except ImportError:
    FUZZY_OK = False

BASE_DIR  = Path(__file__).parent.parent
DATOS_DIR = BASE_DIR / "datos_historicos"
MAPA_FILE = DATOS_DIR / "mapa_nombres.json"
DATOS_DIR.mkdir(parents=True, exist_ok=True)

FUZZY_THRESHOLD = 85   # score mínimo para match fuzzy


def log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


# ══════════════════════════════════════════════════════════════════════════════
# DICCIONARIO DE ALIAS
# ══════════════════════════════════════════════════════════════════════════════

ALIASES: dict[str, str] = {
    # ── Premier League ────────────────────────────────────────────────────────
    "man united":               "manchester united",
    "man city":                 "manchester city",
    "man utd":                  "manchester united",
    "spurs":                    "tottenham",
    "tottenham hotspur":        "tottenham",
    "wolves":                   "wolverhampton wanderers",
    "wolverhampton":            "wolverhampton wanderers",
    "brighton & hove albion":   "brighton",
    "bha":                      "brighton",
    "sheffield utd":            "sheffield united",
    "sheffield weds":           "sheffield wednesday",
    "sheffield wed":            "sheffield wednesday",
    "qpr":                      "queens park rangers",
    "west brom":                "west bromwich albion",
    "wba":                      "west bromwich albion",
    "norwich":                  "norwich city",
    "nottm forest":             "nottingham forest",
    "nott'm forest":            "nottingham forest",
    "notts forest":             "nottingham forest",
    "newcastle":                "newcastle united",
    "newcastle utd":            "newcastle united",
    "leicester":                "leicester city",
    "leeds":                    "leeds united",
    "luton":                    "luton town",
    "ipswich":                  "ipswich town",
    "bolton":                   "bolton wanderers",
    "hull":                     "hull city",
    "stoke":                    "stoke city",
    "sunderland afc":           "sunderland",
    "swansea":                  "swansea city",
    "cardiff":                  "cardiff city",
    "middlesbrough":            "middlesbrough",
    "boro":                     "middlesbrough",
    "wigan":                    "wigan athletic",
    "blackburn":                "blackburn rovers",
    "charlton":                 "charlton athletic",
    "derby":                    "derby county",
    "portsmouth":               "portsmouth",
    # ── La Liga ──────────────────────────────────────────────────────────────
    "atletico":                 "atletico madrid",
    "atletico de madrid":       "atletico madrid",
    "atl. madrid":              "atletico madrid",
    "betis":                    "real betis",
    "r. betis":                 "real betis",
    "celta":                    "celta vigo",
    "rc celta":                 "celta vigo",
    "alaves":                   "deportivo alaves",
    "d. alaves":                "deportivo alaves",
    "sociedad":                 "real sociedad",
    "r. sociedad":              "real sociedad",
    "valladolid":               "real valladolid",
    "r. valladolid":            "real valladolid",
    "vallecano":                "rayo vallecano",
    "las palmas":               "ud las palmas",
    "osasuna":                  "ca osasuna",
    "espanol":                  "espanyol",
    "espanyol":                 "espanyol",
    "athletic club":            "athletic bilbao",
    "ath. bilbao":              "athletic bilbao",
    "ath bilbao":               "athletic bilbao",
    "granada cf":               "granada",
    "levante ud":               "levante",
    "getafe cf":                "getafe",
    "cadiz cf":                 "cadiz",
    "almeria":                  "ud almeria",
    "ud almeria":               "almeria",
    # ── Serie A ──────────────────────────────────────────────────────────────
    "inter":                    "inter milan",
    "internazionale":           "inter milan",
    "fc internazionale":        "inter milan",
    "ac milan":                 "milan",
    "lazio":                    "lazio",
    "ss lazio":                 "lazio",
    "roma":                     "roma",
    "as roma":                  "roma",
    "napoli":                   "napoli",
    "ssc napoli":               "napoli",
    "fiorentina":               "fiorentina",
    "acf fiorentina":           "fiorentina",
    "hellas verona":            "verona",
    "hellas verona fc":         "verona",
    "genoa cfc":                "genoa",
    "cagliari calcio":          "cagliari",
    "torino fc":                "torino",
    "udinese calcio":           "udinese",
    "bologna fc":               "bologna",
    "atalanta bc":              "atalanta",
    "lecce":                    "lecce",
    "us lecce":                 "lecce",
    "monza":                    "monza",
    "frosinone":                "frosinone",
    "salernitana":              "salernitana",
    "empoli":                   "empoli",
    "fc empoli":                "empoli",
    "parma":                    "parma",
    "spezia":                   "spezia",
    "venezia":                  "venezia",
    "cremonese":                "cremonese",
    # ── Bundesliga ───────────────────────────────────────────────────────────
    "dortmund":                 "borussia dortmund",
    "bvb":                      "borussia dortmund",
    "leverkusen":               "bayer leverkusen",
    "b. leverkusen":            "bayer leverkusen",
    "bayer 04 leverkusen":      "bayer leverkusen",
    "gladbach":                 "borussia monchengladbach",
    "m'gladbach":               "borussia monchengladbach",
    "mgladbach":                "borussia monchengladbach",
    "borussia mgladbach":       "borussia monchengladbach",
    "eintr frankfurt":          "eintracht frankfurt",
    "sge":                      "eintracht frankfurt",
    "hertha":                   "hertha berlin",
    "hertha bsc":               "hertha berlin",
    "hertha bsc berlin":        "hertha berlin",
    "hoffenheim":               "hoffenheim",
    "tsg hoffenheim":           "hoffenheim",
    "tsg 1899 hoffenheim":      "hoffenheim",
    "augsburg":                 "augsburg",
    "fc augsburg":              "augsburg",
    "freiburg":                 "freiburg",
    "sc freiburg":              "freiburg",
    "mainz":                    "mainz",
    "1. fsv mainz 05":          "mainz",
    "1. fc mainz":              "mainz",
    "wolfsburg":                "wolfsburg",
    "vfl wolfsburg":            "wolfsburg",
    "stuttgart":                "stuttgart",
    "vfb stuttgart":            "stuttgart",
    "union berlin":             "union berlin",
    "1. fc union berlin":       "union berlin",
    "rb leipzig":               "rb leipzig",
    "rasenballsport leipzig":   "rb leipzig",
    "leipzig":                  "rb leipzig",
    "bremen":                   "werder bremen",
    "werder":                   "werder bremen",
    "sv werder bremen":         "werder bremen",
    "bochum":                   "bochum",
    "vfl bochum":               "bochum",
    "cologne":                  "fc cologne",
    "koln":                     "fc cologne",
    "fc koln":                  "fc cologne",
    "1. fc koln":               "fc cologne",
    "nurnberg":                 "fc nurnberg",
    "1. fc nurnberg":           "fc nurnberg",
    "hamburg":                  "hamburger sv",
    "hsv":                      "hamburger sv",
    "hannover":                 "hannover 96",
    "darmstadt":                "sv darmstadt 98",
    "darmstadt 98":             "sv darmstadt 98",
    "paderborn":                "sc paderborn 07",
    "greuther furth":           "greuther furth",
    "heidenheim":               "1. fc heidenheim",
    # ── Ligue 1 ──────────────────────────────────────────────────────────────
    "psg":                      "paris saint-germain",
    "paris sg":                 "paris saint-germain",
    "paris saint germain":      "paris saint-germain",
    "paris s-g":                "paris saint-germain",
    "marseille":                "marseille",
    "olympique de marseille":   "marseille",
    "olympique marseille":      "marseille",
    "om":                       "marseille",
    "lyon":                     "lyon",
    "olympique lyonnais":       "lyon",
    "ol":                       "lyon",
    "st etienne":               "saint-etienne",
    "saint etienne":            "saint-etienne",
    "as saint-etienne":         "saint-etienne",
    "nice":                     "nice",
    "ogc nice":                 "nice",
    "rennes":                   "rennes",
    "stade rennais":            "rennes",
    "stade rennais fc":         "rennes",
    "lille":                    "lille",
    "losc lille":               "lille",
    "losc":                     "lille",
    "monaco":                   "monaco",
    "as monaco":                "monaco",
    "lens":                     "lens",
    "rc lens":                  "lens",
    "nantes":                   "nantes",
    "fc nantes":                "nantes",
    "toulouse":                 "toulouse",
    "toulouse fc":              "toulouse",
    "brest":                    "brest",
    "stade brest":              "brest",
    "stade brestois 29":        "brest",
    "metz":                     "metz",
    "fc metz":                  "metz",
    "strasbourg":               "strasbourg",
    "rc strasbourg":            "strasbourg",
    "lorient":                  "lorient",
    "fc lorient":               "lorient",
    "reims":                    "reims",
    "stade de reims":           "reims",
    "montpellier":              "montpellier",
    "mhsc":                     "montpellier",
    "angers":                   "angers",
    "angers sco":               "angers",
    "troyes":                   "troyes",
    "estac troyes":             "troyes",
    "clermont":                 "clermont",
    "clermont foot":            "clermont",
    "auxerre":                  "auxerre",
    "aj auxerre":               "auxerre",
    "ajaccio":                  "ajaccio",
    "ac ajaccio":               "ajaccio",
    "bordeaux":                 "bordeaux",
    "girondins de bordeaux":    "bordeaux",
    "dijon":                    "dijon fco",
    "nimes":                    "nimes olympique",
    "caen":                     "stade malherbe caen",
}


# ══════════════════════════════════════════════════════════════════════════════
# FUNCIÓN PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════

def normalizar_nombre(nombre_raw: str) -> str:
    """
    Normaliza un nombre de equipo.

    Pasos:
      1. Lowercase + strip + quitar puntuación redundante
      2. Buscar en ALIASES
      3. Fuzzy match si no hay coincidencia exacta (score >= 85)

    Returns:
        Nombre normalizado en minúsculas.
    """
    if not nombre_raw or not isinstance(nombre_raw, str):
        return ""

    # Paso 1: limpiar
    nombre = nombre_raw.strip().lower()
    nombre = re.sub(r"['\"]", "", nombre)    # quitar comillas
    nombre = re.sub(r"\s+", " ", nombre)     # espacios múltiples → uno

    # Paso 2: alias directo
    if nombre in ALIASES:
        return ALIASES[nombre]

    # Paso 3: fuzzy (si fuzzywuzzy disponible)
    if FUZZY_OK:
        match, score = process.extractOne(
            nombre,
            list(ALIASES.keys()),
            scorer=fuzz.token_sort_ratio
        )
        if score >= FUZZY_THRESHOLD:
            return ALIASES[match]

    return nombre


def normalizar_df(df, col_home: str = "home", col_away: str = "away"):
    """
    Normaliza las columnas de nombre de equipo en un DataFrame.
    Devuelve una copia con columnas normalizadas.
    """
    df = df.copy()
    if col_home in df.columns:
        df[col_home] = df[col_home].apply(normalizar_nombre)
    if col_away in df.columns:
        df[col_away] = df[col_away].apply(normalizar_nombre)
    return df


# ══════════════════════════════════════════════════════════════════════════════
# CREACIÓN DE MAPA ENTRE FUENTES
# ══════════════════════════════════════════════════════════════════════════════

def crear_mapa_nombres(lista_a: list, lista_b: list, guardar: bool = True) -> dict:
    """
    Dado dos listados de nombres (ej: football-data vs Understat),
    crea un mapa {nombre_a → nombre_b} por normalización.

    Returns:
        Dict con el mapa y estadísticas de cobertura.
    """
    norm_a = {n: normalizar_nombre(n) for n in lista_a}
    norm_b = {normalizar_nombre(n): n for n in lista_b}

    mapa        = {}
    sin_resolver = []

    for nombre_orig, nombre_norm in norm_a.items():
        if nombre_norm in norm_b:
            mapa[nombre_orig] = norm_b[nombre_norm]
        else:
            # Intentar fuzzy directo contra lista_b normalizada
            if FUZZY_OK and lista_b:
                match, score = process.extractOne(
                    nombre_norm,
                    list(norm_b.keys()),
                    scorer=fuzz.token_sort_ratio
                )
                if score >= FUZZY_THRESHOLD:
                    mapa[nombre_orig] = norm_b[match]
                else:
                    sin_resolver.append(nombre_orig)
                    mapa[nombre_orig] = nombre_orig  # usar original
            else:
                sin_resolver.append(nombre_orig)
                mapa[nombre_orig] = nombre_orig

    resultado = {
        "mapa":           mapa,
        "n_total":        len(lista_a),
        "n_resueltos":    len(lista_a) - len(sin_resolver),
        "n_sin_resolver": len(sin_resolver),
        "sin_resolver":   sin_resolver,
    }

    if guardar:
        with open(MAPA_FILE, "w", encoding="utf-8") as f:
            json.dump(resultado, f, ensure_ascii=False, indent=2)
        log(f"[OK] Mapa guardado: {len(lista_a)-len(sin_resolver)}/{len(lista_a)} matcheados → {MAPA_FILE.name}")

    if sin_resolver:
        log(f"[WARN] Nombres sin resolver ({len(sin_resolver)}): {sin_resolver[:10]}")

    return resultado


# ══════════════════════════════════════════════════════════════════════════════
# TEST
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 60)
    print("TEST — nombre_normalizer.py")
    print("=" * 60)

    casos_test = [
        # football-data → esperado
        ("Man United",      "manchester united"),
        ("Man City",        "manchester city"),
        ("Nott'm Forest",   "nottingham forest"),
        ("Wolves",          "wolverhampton wanderers"),
        ("Spurs",           "tottenham"),
        ("Newcastle",       "newcastle united"),
        ("Atletico",        "atletico madrid"),
        ("PSG",             "paris saint-germain"),
        ("Dortmund",        "borussia dortmund"),
        ("Inter",           "inter milan"),
        ("AC Milan",        "milan"),
        ("Lyon",            "lyon"),
    ]

    print("\nTests normalización directa:")
    ok = 0
    for raw, esperado in casos_test:
        resultado = normalizar_nombre(raw)
        estado = "✓" if resultado == esperado else "✗"
        if resultado == esperado:
            ok += 1
        print(f"  {estado}  '{raw}' → '{resultado}' (esperado: '{esperado}')")

    print(f"\n{ok}/{len(casos_test)} tests pasados")

    # Test mapa entre fuentes
    print("\nTest crear_mapa_nombres:")
    lista_fd = ["Man United", "Man City", "Newcastle", "Nott'm Forest", "Wolves"]
    lista_us = ["Manchester United", "Manchester City", "Newcastle United",
                "Nottingham Forest", "Wolverhampton Wanderers"]
    mapa = crear_mapa_nombres(lista_fd, lista_us, guardar=False)
    print(f"  Resueltos: {mapa['n_resueltos']}/{mapa['n_total']}")
    for k, v in mapa["mapa"].items():
        print(f"    '{k}' → '{v}'")

    print("\n[OK] nombre_normalizer.py listo")
