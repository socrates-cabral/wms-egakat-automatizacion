import sys
sys.stdout.reconfigure(encoding="utf-8")

"""
transfermarkt_collector.py — Sprint 7
Descarga valor de mercado de plantillas desde Transfermarkt.
Validado por PLOS One 2023 como la feature individual más predictiva.

Cache local de 30 días — no hace requests innecesarios.
Instalar: py -m pip install requests beautifulsoup4 lxml
"""

import re
import json
import math
import time
import requests
from pathlib import Path
from datetime import datetime, date, timedelta
from bs4 import BeautifulSoup

# ── Rutas ─────────────────────────────────────────────────────────────────────
BASE_DIR   = Path(__file__).parent.parent          # agente_apuestas\
DATOS_DIR  = BASE_DIR / "datos_historicos"
DATOS_DIR.mkdir(parents=True, exist_ok=True)
CACHE_FILE = DATOS_DIR / "transfermarkt_cache.json"

HEADERS_TM = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/120.0.0.0"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.transfermarkt.com/",
}
SLEEP_TM   = 3    # segundos entre requests
CACHE_DIAS = 30   # días de validez del cache


def log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


# ══════════════════════════════════════════════════════════════════════════════
# CACHE
# ══════════════════════════════════════════════════════════════════════════════

def _cargar_cache() -> dict:
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _guardar_cache(cache: dict):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def _cache_valido(entrada: dict) -> bool:
    try:
        valido_hasta = datetime.strptime(entrada["valido_hasta"], "%Y-%m-%d").date()
        return date.today() <= valido_hasta
    except Exception:
        return False


# ══════════════════════════════════════════════════════════════════════════════
# PARSEO DE VALOR
# ══════════════════════════════════════════════════════════════════════════════

def _parsear_valor(texto: str) -> float | None:
    """
    Convierte texto de valor Transfermarkt a float en millones de euros.
    "€485.30m" → 485.30  |  "€85.50m" → 85.50  |  "€950k" → 0.95
    """
    if not texto:
        return None
    texto = texto.strip().replace(",", ".")
    texto = re.sub(r"[€$£]", "", texto).strip()

    try:
        if texto.lower().endswith("bn"):
            return float(texto[:-2]) * 1000
        elif texto.lower().endswith("m"):
            return float(texto[:-1])
        elif texto.lower().endswith("k"):
            return float(texto[:-1]) / 1000
        else:
            val = float(texto)
            # Si el número es mayor a 1000, probablemente está en miles
            return val / 1_000_000 if val > 1_000 else val
    except (ValueError, AttributeError):
        return None


# ══════════════════════════════════════════════════════════════════════════════
# FUNCIÓN 1: get_valor_plantilla
# ══════════════════════════════════════════════════════════════════════════════

def get_valor_plantilla(nombre_equipo: str, forzar_update: bool = False) -> dict | None:
    """
    Obtiene el valor de mercado total de la plantilla de un equipo.

    Usa cache local de 30 días para no sobrecargar Transfermarkt.

    Args:
        nombre_equipo:  Nombre del equipo (debe existir en TRANSFERMARKT_IDS en config.py)
        forzar_update:  Si True, ignora el cache y hace request nuevo

    Returns:
        Dict con valor_total_mill_eur, n_jugadores, valor_por_jugador, etc.
        o None si el equipo no está mapeado o falla el request.
    """
    # Importar IDs desde config
    try:
        sys.path.insert(0, str(BASE_DIR))
        from config import TRANSFERMARKT_IDS
    except ImportError:
        log("[FALLO] TRANSFERMARKT_IDS no encontrado en config.py")
        return None

    if nombre_equipo not in TRANSFERMARKT_IDS:
        log(f"[INFO] {nombre_equipo} no está en TRANSFERMARKT_IDS — valor = None")
        return None

    # Verificar cache
    cache = _cargar_cache()
    if not forzar_update and nombre_equipo in cache:
        entrada = cache[nombre_equipo]
        if _cache_valido(entrada):
            log(f"[OK] Cache válido para {nombre_equipo} (hasta {entrada['valido_hasta']})")
            return entrada

    # Hacer request a Transfermarkt
    team_id = TRANSFERMARKT_IDS[nombre_equipo]
    slug    = nombre_equipo.lower().replace(" ", "-").replace(".", "")
    url     = f"https://www.transfermarkt.com/{slug}/startseite/verein/{team_id}"

    try:
        time.sleep(SLEEP_TM)
        resp = requests.get(url, headers=HEADERS_TM, timeout=20)
        if resp.status_code != 200:
            log(f"[FALLO] Transfermarkt HTTP {resp.status_code} para {nombre_equipo}")
            return None

        soup = BeautifulSoup(resp.text, "lxml")

        # Buscar valor total de la plantilla
        valor_total = None
        n_jugadores = 0

        # Selector 1: data-value en span del valor total
        for tag in soup.find_all(["span", "div", "a"], {"class": re.compile(r"market.value|squad.value", re.I)}):
            texto = tag.get_text(strip=True)
            val = _parsear_valor(texto)
            if val and val > 0:
                valor_total = val
                break

        # Selector 2: buscar por texto "Total market value"
        if valor_total is None:
            for tag in soup.find_all(string=re.compile(r"total.market.value|squad.market.value", re.I)):
                parent = tag.parent
                if parent:
                    texto = parent.get_text(strip=True)
                    val = _parsear_valor(re.sub(r"[^\d.,kmbn€$£]", "", texto))
                    if val and val > 0:
                        valor_total = val
                        break

        # Selector 3: tabla de jugadores — sumar valores individuales
        if valor_total is None:
            valores_jugadores = []
            for tag in soup.find_all("td", {"class": re.compile(r"rechts hauptlink", re.I)}):
                texto = tag.get_text(strip=True)
                if "€" in texto or "m" in texto.lower():
                    val = _parsear_valor(texto)
                    if val and 0 < val < 500:
                        valores_jugadores.append(val)
            if valores_jugadores:
                valor_total = sum(valores_jugadores)
                n_jugadores = len(valores_jugadores)

        if valor_total is None:
            log(f"[FALLO] No se encontró valor de plantilla para {nombre_equipo}")
            return None

        # Número de jugadores si no fue determinado
        if n_jugadores == 0:
            squad_tag = soup.find(string=re.compile(r"\d+\s+players?", re.I))
            if squad_tag:
                m = re.search(r"(\d+)", str(squad_tag))
                if m:
                    n_jugadores = int(m.group(1))
            if n_jugadores == 0:
                n_jugadores = 25  # default típico

        resultado = {
            "equipo":               nombre_equipo,
            "valor_total_mill_eur": round(valor_total, 2),
            "n_jugadores":          n_jugadores,
            "valor_por_jugador":    round(valor_total / max(n_jugadores, 1), 2),
            "fecha_consulta":       str(date.today()),
            "valido_hasta":         str(date.today() + timedelta(days=CACHE_DIAS)),
            "fuente":               "transfermarkt",
        }

        # Guardar en cache
        cache[nombre_equipo] = resultado
        _guardar_cache(cache)
        log(f"[OK] {nombre_equipo}: €{valor_total:.1f}M ({n_jugadores} jugadores)")
        return resultado

    except Exception as e:
        log(f"[FALLO] Error scraping Transfermarkt para {nombre_equipo}: {e}")
        return None


# ══════════════════════════════════════════════════════════════════════════════
# FUNCIÓN 2: get_valor_once
# ══════════════════════════════════════════════════════════════════════════════

def get_valor_once(nombre_equipo: str, lineup: list = None) -> dict | None:
    """
    Estima el valor del once titular.
    El once titular representa ~72% del valor total (proporción documentada).

    Args:
        nombre_equipo: Nombre del equipo
        lineup:        Lista de jugadores titulares (para ajuste por bajas)

    Returns:
        Dict con valor_once_estimado, valor_once_ajustado, pct_valor_disponible
    """
    datos = get_valor_plantilla(nombre_equipo)
    if datos is None:
        return None

    valor_total = datos["valor_total_mill_eur"]

    # El once titular ≈ 72% del valor total (literatura académica)
    valor_once = valor_total * 0.72

    # Ajuste por bajas (si se proporcionan lineup/bajas)
    valor_once_ajustado = valor_once
    if lineup is not None:
        # Simplificación: si el lineup tiene menos de 11 → hay bajas
        n_titulares = len([p for p in lineup if p])
        if n_titulares < 11:
            bajas = 11 - n_titulares
            # Cada baja titular reduce ~4% del valor del once
            factor_bajas = 1.0 - (bajas * 0.04)
            valor_once_ajustado = valor_once * max(factor_bajas, 0.7)

    return {
        "valor_once_estimado":    round(valor_once, 2),
        "valor_once_ajustado":    round(valor_once_ajustado, 2),
        "pct_valor_disponible":   round(valor_once_ajustado / max(valor_total, 0.001) * 100, 1),
    }


# ══════════════════════════════════════════════════════════════════════════════
# FUNCIÓN 3: calcular_ratio_valor
# ══════════════════════════════════════════════════════════════════════════════

def calcular_ratio_valor(valor_home: float, valor_away: float) -> dict:
    """
    Calcula el ratio de valor de mercado entre los dos equipos.
    Feature directa para XGBoost — log_ratio es la mejor representación.

    Args:
        valor_home: Valor plantilla local en millones €
        valor_away: Valor plantilla visitante en millones €

    Returns:
        Dict con ratio_valor, diff_valor_mill, categoria_dominio, log_ratio
    """
    ratio = valor_home / max(valor_away, 0.001)
    diff  = valor_home - valor_away

    if ratio > 3.0:
        categoria = "dominio_claro"
    elif ratio > 1.5:
        categoria = "leve_favorito"
    elif ratio > 0.67:
        categoria = "equilibrado"
    elif ratio > 0.33:
        categoria = "underdog_home"
    else:
        categoria = "dominio_away"

    return {
        "ratio_valor":       round(ratio, 4),
        "diff_valor_mill":   round(diff, 2),
        "categoria_dominio": categoria,
        "log_ratio":         round(math.log(ratio + 0.001), 4),
    }


# ══════════════════════════════════════════════════════════════════════════════
# FUNCIÓN 4: cache_local (gestión manual)
# ══════════════════════════════════════════════════════════════════════════════

def cache_local(forzar_update: bool = False) -> dict:
    """
    Carga o actualiza el cache completo de valores Transfermarkt.
    Si forzar_update=True → refresca todos los equipos mapeados.

    Returns:
        Dict completo del cache.
    """
    try:
        sys.path.insert(0, str(BASE_DIR))
        from config import TRANSFERMARKT_IDS
    except ImportError:
        log("[FALLO] TRANSFERMARKT_IDS no encontrado en config.py")
        return {}

    cache = _cargar_cache()

    if forzar_update:
        log(f"[INFO] Actualizando cache para {len(TRANSFERMARKT_IDS)} equipos...")
        for equipo in TRANSFERMARKT_IDS:
            get_valor_plantilla(equipo, forzar_update=True)
        cache = _cargar_cache()

    validos   = sum(1 for e in cache.values() if _cache_valido(e))
    expirados = len(cache) - validos
    log(f"[INFO] Cache Transfermarkt: {validos} válidos, {expirados} expirados de {len(cache)} equipos")
    return cache


# ══════════════════════════════════════════════════════════════════════════════
# TEST
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 60)
    print("TEST — transfermarkt_collector.py")
    print("=" * 60)

    equipos_test = ["Arsenal", "Real Madrid", "Bayern Munich"]

    for equipo in equipos_test:
        print(f"\n[INFO] Consultando {equipo}...")
        datos = get_valor_plantilla(equipo)
        if datos:
            print(f"  Valor plantilla: €{datos['valor_total_mill_eur']:.1f}M")
            print(f"  Jugadores:       {datos['n_jugadores']}")
            print(f"  Valor/jugador:   €{datos['valor_por_jugador']:.1f}M")
            print(f"  Válido hasta:    {datos['valido_hasta']}")
        else:
            print(f"  [INFO] No disponible (verificar TRANSFERMARKT_IDS en config.py)")

    # Test ratio_valor
    print("\n[INFO] Test calcular_ratio_valor:")
    ratio = calcular_ratio_valor(485.0, 120.0)
    print(f"  Arsenal(485M) vs equipo(120M): {ratio}")

    print("\n[OK] transfermarkt_collector.py listo")
