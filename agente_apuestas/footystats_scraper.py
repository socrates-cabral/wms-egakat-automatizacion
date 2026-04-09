import sys
sys.stdout.reconfigure(encoding="utf-8")

"""
footystats_scraper.py  v2.0
Descarga CSVs de FootyStats usando las cookies de tu Chrome real.
NO usa Playwright — evita Cloudflare completamente.

Requisitos:
  - Estar logueado en footystats.org en tu Chrome normal (no necesita estar abierto)
  - pip install browser-cookie3 requests beautifulsoup4

Uso:
    py agente_apuestas/footystats_scraper.py              # descarga todo
    py agente_apuestas/footystats_scraper.py --liga "Serie A"
    py agente_apuestas/footystats_scraper.py --debug      # muestra links encontrados sin descargar

Output:
    agente_apuestas/datos_footystats/{slug}_{season}_{tipo}.csv

Frecuencia recomendada: 1 vez por semana.
"""

import os
import re
import logging
import argparse
from datetime import datetime
from pathlib import Path

import json
import requests
from dotenv import load_dotenv

# ── Config ────────────────────────────────────────────────────────────────────
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

BASE_DIR  = Path(__file__).parent
DATOS_DIR = BASE_DIR / "datos_footystats"
DATOS_DIR.mkdir(exist_ok=True)

LOG_DIR = BASE_DIR.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
log_path  = LOG_DIR / f"footystats_scraper_{timestamp}.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.FileHandler(log_path, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)

URL_DOWNLOAD  = "https://footystats.org/download-stats-csv"
COOKIES_FILE  = BASE_DIR / "footystats_cookies.json"   # exportado con Cookie-Editor

# comp IDs de FootyStats para cada liga objetivo
# Verificados 2026-04-09 desde footystats.org/download-stats-csv
LIGAS_COMP = {
    "Premier League":      {"comp": "15050", "slug": "premier-league"},
    "La Liga":             {"comp": "14956", "slug": "la-liga"},
    "Serie A":             {"comp": "15068", "slug": "serie-a"},
    "Bundesliga":          {"comp": "14968", "slug": "bundesliga"},
    "Ligue 1":             {"comp": "2426",  "slug": "ligue-1"},
    "Primera Division CL": {"comp": "16615", "slug": "primera-division-cl"},
    # Gratis (sin Premium):
    "EPL 2018-2019":       {"comp": "1625",  "slug": "epl-2018-2019"},
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def nombre_archivo(slug: str, tipo: str, comp_id: str) -> Path:
    return DATOS_DIR / f"{slug}_{tipo}.csv"


def ya_descargado(slug: str, tipo: str, comp_id: str) -> bool:
    path = nombre_archivo(slug, tipo, comp_id)
    return path.exists() and path.stat().st_size > 1000



# ── Sesión con cookies exportadas ────────────────────────────────────────────

def obtener_sesion_chrome() -> requests.Session:
    """
    Carga cookies desde footystats_cookies.json (exportado con Cookie-Editor en Chrome).
    Para exportar:
      1. Ve a footystats.org en Chrome (logueado)
      2. Abre Cookie-Editor → Export → Export as JSON
      3. Guarda como: agente_apuestas/footystats_cookies.json
    """
    if not COOKIES_FILE.exists():
        log.error(f"[FALLO] No se encontró: {COOKIES_FILE}")
        log.error("")
        log.error("Para crear el archivo de cookies:")
        log.error("  1. Instala la extensión 'Cookie-Editor' en Chrome")
        log.error("  2. Ve a footystats.org (logueado)")
        log.error("  3. Clic en Cookie-Editor → Export → Export as JSON")
        log.error(f"  4. Guarda el archivo en: {COOKIES_FILE}")
        raise FileNotFoundError(COOKIES_FILE)

    log.info(f"Cargando cookies desde {COOKIES_FILE.name}...")
    with open(COOKIES_FILE, "r", encoding="utf-8") as f:
        raw = json.load(f)

    session = requests.Session()

    # Cookie-Editor exporta lista de objetos con campos "name", "value", "domain", etc.
    for c in raw:
        name  = c.get("name") or c.get("key", "")
        value = c.get("value", "")
        if name and value:
            session.cookies.set(name, value, domain=c.get("domain", ".footystats.org"))

    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "es-419,es;q=0.9,en;q=0.8",
        "Referer": "https://footystats.org/",
    })
    log.info(f"[OK] {len(raw)} cookies cargadas")
    return session


# ── Scraping de links ─────────────────────────────────────────────────────────

def obtener_links(session: requests.Session, debug: bool = False) -> list[dict]:
    """
    Genera la lista de links de descarga directamente desde LIGAS_COMP (comp IDs conocidos).
    No necesita parsear HTML — los IDs fueron verificados el 2026-04-09.
    """
    links = []
    for liga, meta in LIGAS_COMP.items():
        comp = meta["comp"]
        slug = meta["slug"]
        for tipo in ("matches", "league"):
            href = f"https://footystats.org/c-dl.php?type={tipo}&comp={comp}"
            links.append({
                "liga":    liga,
                "slug":    slug,
                "tipo":    tipo,
                "comp_id": comp,
                "href":    href,
            })

    log.info(f"Links a descargar: {len(links)} ({len(LIGAS_COMP)} ligas × 2 tipos)")
    if debug:
        for lnk in links:
            skip = " [YA EXISTE]" if ya_descargado(lnk["slug"], lnk["tipo"], lnk["comp_id"]) else ""
            log.info(f"  → {lnk['liga']:25} [{lnk['tipo']:7}] comp={lnk['comp_id']}{skip}")
    return links


# ── Descarga ──────────────────────────────────────────────────────────────────

def descargar_csv(session: requests.Session, link: dict) -> bool:
    destino = nombre_archivo(link["slug"], link["tipo"], link["comp_id"])

    if ya_descargado(link["slug"], link["tipo"], link["comp_id"]):
        log.info(f"[SKIP] Ya existe: {destino.name}")
        return True

    log.info(f"Descargando {link['liga']} ({link['tipo']})...")

    try:
        resp = session.get(link["href"], timeout=60, stream=True)
        if resp.status_code != 200:
            log.warning(f"[FALLO] HTTP {resp.status_code} — {link['liga']}")
            return False

        # FootyStats envía content-type: text/html incluso para CSVs — no confiar en él
        # Detectar si es HTML real (página de error/upgrade) vs CSV
        inicio = resp.text[:200].strip()
        if inicio.startswith("<") or "<!DOCTYPE" in inicio.upper():
            log.warning(f"[FALLO] Respuesta es HTML — requiere Premium o sesión expirada")
            return False

        with open(destino, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)

        size = destino.stat().st_size
        if size < 500:
            destino.unlink()
            log.warning(f"[FALLO] Archivo muy pequeño ({size} bytes) — probablemente Premium")
            return False

        log.info(f"[OK] {destino.name} ({size:,} bytes)")
        return True

    except Exception as e:
        log.warning(f"[FALLO] {link['liga']}: {e}")
        return False


# ── Main ──────────────────────────────────────────────────────────────────────

def run(solo_liga: str | None = None, debug: bool = False):
    log.info("=" * 60)
    log.info(f"FootyStats Scraper v2.0  [cookies Chrome]")
    log.info("=" * 60)

    session = obtener_sesion_chrome()

    links = obtener_links(session, debug=debug)
    if not links:
        log.warning("No se encontraron links descargables.")
        log.warning("  → Verifica que estés logueado en footystats.org en Chrome")
        log.warning("  → Navega a footystats.org/download-stats-csv y recarga")
        return

    if solo_liga:
        links = [l for l in links if solo_liga.lower() in l["liga"].lower()]
        log.info(f"Filtro '{solo_liga}': {len(links)} links")

    if debug:
        log.info("[DEBUG] Modo debug — no se descargan archivos.")
        return

    ok = fail = 0
    for link in links:
        if descargar_csv(session, link):
            ok += 1
        else:
            fail += 1

    log.info("")
    log.info(f"Resumen: {ok} OK | {fail} fallidos")
    log.info(f"CSVs en: {DATOS_DIR}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FootyStats CSV Scraper v2.0")
    parser.add_argument("--liga", type=str, default=None,
                        help='Filtrar por liga. Ej: "Serie A"')
    parser.add_argument("--debug", action="store_true",
                        help="Muestra links encontrados sin descargar")
    args = parser.parse_args()
    run(solo_liga=args.liga, debug=args.debug)
