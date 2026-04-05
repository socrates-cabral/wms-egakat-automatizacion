import sys
sys.stdout.reconfigure(encoding="utf-8")

"""
tavily_enricher.py — Sprint 17
Enriquece datos del agente de apuestas usando Tavily Search API.
Fallback web cuando api-sports no devuelve H2H, forma o lesiones.

Uso:
  from tavily_enricher import enriquecer_h2h, enriquecer_forma, enriquecer_lesiones

Requiere: TAVILY_API_KEY en .env
"""

import os
import re
import json
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
DISPONIBLE = bool(TAVILY_API_KEY)

# Cache en memoria para no repetir búsquedas en la misma ejecución
_cache: dict[str, dict] = {}


def _log(msg: str):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [TAVILY] {msg}", flush=True)


def _buscar(query: str, max_results: int = 5) -> list[dict]:
    """Búsqueda Tavily. Retorna lista de resultados o [] si falla."""
    if not DISPONIBLE:
        return []

    cache_key = query[:100]
    if cache_key in _cache:
        return _cache[cache_key].get("results", [])

    try:
        from tavily import TavilyClient
        client = TavilyClient(api_key=TAVILY_API_KEY)
        response = client.search(
            query=query,
            max_results=max_results,
            search_depth="basic",
            include_answer=True,
        )
        results = response.get("results", [])
        _cache[cache_key] = {"results": results, "answer": response.get("answer", "")}
        _log(f"OK: {len(results)} resultados para '{query[:60]}...'")
        return results
    except Exception as e:
        _log(f"FALLO: {e}")
        return []


def _buscar_con_respuesta(query: str, max_results: int = 5) -> str:
    """Búsqueda Tavily con respuesta directa (answer). Retorna string."""
    if not DISPONIBLE:
        return ""

    cache_key = query[:100]
    if cache_key in _cache:
        return _cache[cache_key].get("answer", "")

    _buscar(query, max_results)
    return _cache.get(cache_key, {}).get("answer", "")


# ─────────────────────────────────────────────────────────────────────────────
# H2H ENRICHMENT
# ─────────────────────────────────────────────────────────────────────────────

def enriquecer_h2h(home: str, away: str, stats: dict) -> dict:
    """
    Si el H2H de api-sports está vacío (total=0), busca en web.
    Parsea la respuesta de Tavily para extraer datos básicos de H2H.
    Modifica stats in-place y lo retorna.
    """
    h2h = stats.get("resumen_h2h", {})
    if h2h.get("total", 0) > 0:
        return stats  # Ya tenemos datos

    query = f"{home} vs {away} head to head last 10 matches results goals"
    answer = _buscar_con_respuesta(query)
    if not answer:
        return stats

    # Intentar parsear números de la respuesta
    # Patrones: "X wins for Home, Y draws, Z wins for Away"
    h_wins, draws, a_wins, total = _parsear_h2h_texto(answer, home, away)

    if total > 0:
        stats["resumen_h2h"] = {
            "total": total,
            "home_wins": h_wins,
            "away_wins": a_wins,
            "draws": draws,
        }
        stats["_h2h_fuente"] = "tavily_web"
        _log(f"H2H enriquecido: {home} {h_wins}-{draws}-{a_wins} {away} (total={total})")

    return stats


def _parsear_h2h_texto(texto: str, home: str, away: str) -> tuple[int, int, int, int]:
    """
    Extrae victorias home/draws/away de texto libre.
    Retorna (home_wins, draws, away_wins, total).
    """
    texto_lower = texto.lower()

    # Patrón 1: "X wins, Y draws, Z losses" o similar
    wins_pattern = re.findall(r'(\d+)\s*wins?', texto_lower)
    draws_pattern = re.findall(r'(\d+)\s*draws?', texto_lower)
    losses_pattern = re.findall(r'(\d+)\s*loss(?:es)?', texto_lower)

    if wins_pattern and draws_pattern:
        h_wins = int(wins_pattern[0])
        draws = int(draws_pattern[0])
        a_wins = int(losses_pattern[0]) if losses_pattern else 0
        total = h_wins + draws + a_wins
        if total > 0:
            return h_wins, draws, a_wins, total

    # Patrón 2: "W-D-L" como "5-2-3"
    wdl_pattern = re.findall(r'(\d+)\s*[-–]\s*(\d+)\s*[-–]\s*(\d+)', texto)
    if wdl_pattern:
        w, d, l = int(wdl_pattern[0][0]), int(wdl_pattern[0][1]), int(wdl_pattern[0][2])
        total = w + d + l
        if 2 <= total <= 20:
            return w, d, l, total

    # Patrón 3: "out of N meetings" + porcentajes
    total_pattern = re.findall(r'(\d+)\s*(?:meetings|matches|games|encounters)', texto_lower)
    if total_pattern:
        total = int(total_pattern[0])
        if total > 0:
            # Intentar extraer porcentajes
            pcts = re.findall(r'(\d+)%', texto)
            if len(pcts) >= 2:
                # Asumir primer % = home wins, segundo = draws o away wins
                h_pct = int(pcts[0]) / 100
                d_pct = int(pcts[1]) / 100 if len(pcts) >= 3 else 0
                h_wins = round(total * h_pct)
                draws = round(total * d_pct)
                a_wins = total - h_wins - draws
                return h_wins, draws, max(0, a_wins), total

    return 0, 0, 0, 0


# ─────────────────────────────────────────────────────────────────────────────
# FORMA ENRICHMENT
# ─────────────────────────────────────────────────────────────────────────────

def enriquecer_forma(equipo: str, stats: dict, lado: str = "home") -> dict:
    """
    Si la forma reciente tiene "?" en resultados, busca en web.
    lado: "home" o "away"
    """
    forma_key = f"forma_{lado}"
    forma = stats.get(forma_key, [])

    # Contar resultados desconocidos
    resultados = [p.get("resultado", "?") for p in forma] if forma else []
    desconocidos = resultados.count("?")

    if desconocidos < 3 and len(forma) >= 3:
        return stats  # Datos suficientes

    query = f"{equipo} last 5 matches results 2025 2026 football"
    answer = _buscar_con_respuesta(query, max_results=3)
    if not answer:
        return stats

    # Parsear W/D/L de la respuesta
    resultados_web = _parsear_forma_texto(answer)
    if resultados_web:
        # Construir partidos sintéticos con los resultados
        partidos_sinteticos = []
        for i, res in enumerate(resultados_web[:5]):
            partidos_sinteticos.append({
                "resultado": res,
                "rival": "web_data",
                "goles_favor": None,
                "goles_contra": None,
                "fecha": "",
            })

        if partidos_sinteticos:
            stats[forma_key] = partidos_sinteticos
            stats[f"_{lado}_forma_fuente"] = "tavily_web"
            _log(f"Forma {equipo}: {''.join(resultados_web[:5])}")

    return stats


def _parsear_forma_texto(texto: str) -> list[str]:
    """Extrae secuencia W/D/L de texto. Retorna lista como ['W','W','D','L','W']."""
    # Patrón 1: secuencia directa "W W D L W" o "WWDLW"
    seq = re.findall(r'\b([WDL])\b', texto.upper())
    if len(seq) >= 3:
        return seq[:5]

    # Patrón 2: "won X, drew Y, lost Z of last 5"
    texto_lower = texto.lower()
    won = re.findall(r'won\s+(\d+)', texto_lower)
    drew = re.findall(r'drew?\s+(\d+)', texto_lower)
    lost = re.findall(r'lost\s+(\d+)', texto_lower)

    if won:
        w = int(won[0])
        d = int(drew[0]) if drew else 0
        l = int(lost[0]) if lost else 0
        total = w + d + l
        if total >= 3:
            return ["W"] * w + ["D"] * d + ["L"] * l

    return []


# ─────────────────────────────────────────────────────────────────────────────
# LESIONES / BAJAS ENRICHMENT
# ─────────────────────────────────────────────────────────────────────────────

def enriquecer_lesiones(equipo: str, stats: dict, lado: str = "home") -> dict:
    """
    Busca noticias de lesiones recientes para enriquecer la info del lineup.
    Agrega campo 'bajas_web' al dict del equipo.
    """
    equipo_dict = stats.get(lado, {})
    bajas_actuales = equipo_dict.get("bajas_lista", [])

    if len(bajas_actuales) > 0:
        return stats  # Ya tenemos datos de api-sports

    query = f"{equipo} injury report today team news lineup"
    answer = _buscar_con_respuesta(query, max_results=3)
    if not answer:
        return stats

    # Buscar nombres de jugadores lesionados mencionados
    jugadores = _parsear_lesiones_texto(answer)
    if jugadores:
        equipo_dict["bajas_web"] = jugadores
        equipo_dict["_bajas_fuente"] = "tavily_web"
        stats[lado] = equipo_dict
        _log(f"Lesiones {equipo}: {', '.join(jugadores[:5])}")

    return stats


def _parsear_lesiones_texto(texto: str) -> list[str]:
    """Extrae nombres de jugadores lesionados mencionados en el texto."""
    patrones = [
        r'(?:injured|sidelined|ruled out|doubtful|questionable|absent|miss(?:es|ing)?)[:\s]+([A-Z][a-z]+ [A-Z][a-z]+)',
        r'([A-Z][a-z]+ [A-Z][a-z]+)\s+(?:is|are|remains?)\s+(?:injured|sidelined|out|doubtful|questionable)',
        r'without\s+([A-Z][a-z]+ [A-Z][a-z]+)',
    ]
    jugadores = set()
    for pat in patrones:
        for match in re.findall(pat, texto):
            if len(match.split()) >= 2:
                jugadores.add(match.strip())

    return list(jugadores)[:10]


# ─────────────────────────────────────────────────────────────────────────────
# FUNCIÓN INTEGRADA — enriquecer todo de una vez
# ─────────────────────────────────────────────────────────────────────────────

def enriquecer_stats(home: str, away: str, stats: dict) -> dict:
    """
    Enriquece las stats del partido con datos de Tavily cuando api-sports
    no devuelve información suficiente.
    Modifica stats in-place y lo retorna.
    """
    if not DISPONIBLE:
        _log("No disponible (TAVILY_API_KEY no configurada)")
        return stats

    stats = enriquecer_h2h(home, away, stats)
    stats = enriquecer_forma(home, stats, "home")
    stats = enriquecer_forma(away, stats, "away")
    stats = enriquecer_lesiones(home, stats, "home")
    stats = enriquecer_lesiones(away, stats, "away")

    return stats


# ─────────────────────────────────────────────────────────────────────────────
# TEST
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("TEST — tavily_enricher.py")
    print(f"Tavily disponible: {DISPONIBLE}")
    print("=" * 60)

    if DISPONIBLE:
        stats_vacio = {
            "resumen_h2h": {"total": 0, "home_wins": 0, "away_wins": 0, "draws": 0},
            "forma_home": [],
            "forma_away": [],
            "home": {},
            "away": {},
        }

        resultado = enriquecer_stats("Atletico Madrid", "Barcelona", stats_vacio)
        print(json.dumps(resultado.get("resumen_h2h", {}), indent=2))
    else:
        print("TAVILY_API_KEY no encontrada en .env — saltando test")
