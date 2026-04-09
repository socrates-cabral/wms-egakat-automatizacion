import sys
sys.stdout.reconfigure(encoding="utf-8")

"""
footystats_scraper.py  v1.1
Descarga CSVs de partidos desde footystats.org usando Playwright.

Requisitos en .env:
    FOOTYSTATS_EMAIL=tu@email.com
    FOOTYSTATS_PASSWORD=tu_password

Uso:
    py agente_apuestas/footystats_scraper.py              # headless (puede fallar Cloudflare)
    py agente_apuestas/footystats_scraper.py --headful    # abre ventana visible — recomendado
    py agente_apuestas/footystats_scraper.py --headful --liga "Serie A"

Modo headful:
    - Abre Chromium visible para que puedas resolver captchas/Cloudflare manualmente
    - Si hay Cloudflare: resuelve el challenge → el scraper continúa solo
    - Si hay login: el scraper lo intenta automático; si falla, loguéate tú
    - Pausa 10s antes del login para que veas la pantalla

Output:
    datos_footystats/{slug}_{season}_matches.csv
    datos_footystats/{slug}_{season}_teams.csv

Frecuencia recomendada: 1 vez por semana.
Costo de requests: 0 (no consume api-sports).
"""

import os
import re
import time
import logging
import argparse
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

# ── Config ────────────────────────────────────────────────────────────────────
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

FOOTYSTATS_EMAIL    = os.getenv("FOOTYSTATS_EMAIL", "")
FOOTYSTATS_PASSWORD = os.getenv("FOOTYSTATS_PASSWORD", "")

BASE_DIR      = Path(__file__).parent
DATOS_DIR     = BASE_DIR / "datos_footystats"
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

TIMEOUT = 30_000   # 30s para navegación
TIMEOUT_DL = 60_000  # 60s para descargas

# ── Ligas objetivo (nombres como aparecen en footystats.org) ──────────────────
# El scraper busca estas cadenas en el texto de los links de descarga.
# Ajustar si footystats usa nombres distintos.
LIGAS_OBJETIVO = {
    "Premier League":    "premier-league",
    "Serie A":           "serie-a",
    "La Liga":           "la-liga",
    "Bundesliga":        "bundesliga",
    "Ligue 1":           "ligue-1",
    "Champions League":  "champions-league",
    "Primera Division CL": "primera-division",   # Chile
}

URL_LOGIN    = "https://footystats.org/login"
URL_DOWNLOAD = "https://footystats.org/download-stats-csv"

# Perfil de browser persistente — guarda cookies/sesión entre ejecuciones
# Así no tienes que resolver Cloudflare cada vez
PROFILE_DIR  = BASE_DIR / ".footystats_profile"


# ── Helpers ───────────────────────────────────────────────────────────────────

def slug_from_url(href: str) -> str:
    """Extrae slug legible de la URL de descarga."""
    parts = href.rstrip("/").split("/")
    return parts[-1].replace(".csv", "").replace(".xlsx", "")


def nombre_archivo(liga_slug: str, tipo: str, season: str) -> Path:
    """
    Retorna Path destino para el CSV.
    Ejemplo: datos_footystats/serie-a_2024_matches.csv
    """
    season_clean = season.replace("/", "-")
    return DATOS_DIR / f"{liga_slug}_{season_clean}_{tipo}.csv"


def ya_descargado(liga_slug: str, tipo: str, season: str) -> bool:
    path = nombre_archivo(liga_slug, tipo, season)
    return path.exists() and path.stat().st_size > 1000


# ── Login ─────────────────────────────────────────────────────────────────────

def hacer_login(page, headful: bool = False) -> bool:
    """
    Navega a login y autentica.
    En modo headful: pausa para que el usuario resuelva Cloudflare/captcha si aparece.
    Retorna True si logramos estar logueados.
    """
    if not FOOTYSTATS_EMAIL or not FOOTYSTATS_PASSWORD:
        log.error("[FALLO] FOOTYSTATS_EMAIL / FOOTYSTATS_PASSWORD no configurados en .env")
        return False

    log.info("Navegando a login FootyStats...")
    page.goto(URL_LOGIN, timeout=TIMEOUT)

    if headful:
        log.info("Modo headful — esperando 8s para que cargue (resuelve Cloudflare si aparece)...")
        time.sleep(8)

    page.wait_for_load_state("domcontentloaded", timeout=TIMEOUT)

    # ── Detectar Cloudflare challenge ────────────────────────────────────────
    if "cloudflare" in page.title().lower() or "attention required" in page.title().lower():
        if headful:
            log.warning("[Cloudflare] Challenge detectado — tienes 30s para resolverlo en la ventana...")
            time.sleep(30)
            page.wait_for_load_state("domcontentloaded", timeout=TIMEOUT)
        else:
            log.error("[FALLO] Cloudflare bloqueó el acceso. Usa --headful para resolver manualmente.")
            return False

    # ── Verificar si ya estamos logueados (sesión guardada en perfil) ────────
    if "/login" not in page.url:
        log.info(f"[OK] Sesión activa detectada — {page.url}")
        return True

    # ── Intentar login automático ─────────────────────────────────────────────
    try:
        # Esperar a que aparezca el formulario
        page.wait_for_selector(
            'input[type="email"], input[name="email"], input[name="username"], #email',
            timeout=10_000
        )
        page.fill('input[type="email"], input[name="email"], input[name="username"], #email',
                  FOOTYSTATS_EMAIL)
        page.fill('input[type="password"], input[name="password"], #password',
                  FOOTYSTATS_PASSWORD)

        if headful:
            log.info("Credenciales ingresadas — esperando 3s antes de submit...")
            time.sleep(3)

        page.click('button[type="submit"], input[type="submit"], .login-btn, button:has-text("Login")')
        page.wait_for_load_state("domcontentloaded", timeout=TIMEOUT)

        if headful:
            time.sleep(3)

    except PWTimeout:
        if headful:
            log.warning("[AVISO] No se encontró formulario automáticamente.")
            log.warning("Tienes 30s para hacer login manualmente en la ventana...")
            time.sleep(30)
        else:
            log.error("[FALLO] Timeout buscando formulario de login")
            return False

    # ── Verificar resultado ───────────────────────────────────────────────────
    if "/login" in page.url:
        if headful:
            log.warning("Aún en /login — esperando 15s más (completa el login manualmente)...")
            time.sleep(15)
        if "/login" in page.url:
            log.error("[FALLO] Login fallido — verificar credenciales en .env")
            return False

    log.info(f"[OK] Login exitoso — {page.url}")
    return True


# ── Descarga de CSVs ──────────────────────────────────────────────────────────

def obtener_links_descarga(page) -> list[dict]:
    """
    Navega a la página de descargas y extrae todos los links de CSV/Excel.
    Retorna lista de dicts: {liga, slug, tipo, season, href}
    """
    log.info(f"Navegando a {URL_DOWNLOAD}...")
    page.goto(URL_DOWNLOAD, timeout=TIMEOUT)
    page.wait_for_load_state("networkidle", timeout=TIMEOUT)

    links = []

    # Buscar todos los <a> que apunten a CSVs
    anchors = page.query_selector_all("a[href*='.csv'], a[href*='download'], a[href*='csv']")

    for a in anchors:
        href = a.get_attribute("href") or ""
        texto = (a.inner_text() or "").strip().lower()

        if not href or not href.startswith("http"):
            if href.startswith("/"):
                href = "https://footystats.org" + href
            else:
                continue

        # Detectar liga por slug en URL
        liga_detectada = None
        slug_detectado = None
        for nombre_liga, slug in LIGAS_OBJETIVO.items():
            if slug in href.lower() or slug in texto:
                liga_detectada = nombre_liga
                slug_detectado = slug
                break

        if not liga_detectada:
            continue

        # Detectar tipo (matches / teams / league)
        tipo = "matches"
        if "team" in href.lower() or "team" in texto:
            tipo = "teams"
        elif "league" in href.lower() or "standing" in texto:
            tipo = "league"

        # Detectar temporada desde la URL o texto
        season_match = re.search(r"(20\d{2}[-/]20\d{2}|20\d{2})", href + texto)
        season = season_match.group(1) if season_match else "2024"

        links.append({
            "liga":  liga_detectada,
            "slug":  slug_detectado,
            "tipo":  tipo,
            "season": season,
            "href":  href,
        })

    log.info(f"Links encontrados: {len(links)}")
    return links


def descargar_csv(page, link: dict) -> bool:
    """Descarga un CSV y lo guarda en datos_footystats/."""
    destino = nombre_archivo(link["slug"], link["tipo"], link["season"])

    if ya_descargado(link["slug"], link["tipo"], link["season"]):
        log.info(f"[SKIP] Ya existe: {destino.name}")
        return True

    log.info(f"Descargando {link['liga']} {link['season']} ({link['tipo']})...")

    try:
        with page.expect_download(timeout=TIMEOUT_DL) as dl_info:
            page.goto(link["href"], timeout=TIMEOUT)

        download = dl_info.value
        download.save_as(str(destino))
        log.info(f"[OK] Guardado: {destino.name} ({destino.stat().st_size:,} bytes)")
        return True

    except PWTimeout:
        log.warning(f"[FALLO] Timeout descargando {link['liga']} {link['tipo']}")
        return False
    except Exception as e:
        log.warning(f"[FALLO] {link['liga']} {link['tipo']}: {e}")
        return False


# ── Main ──────────────────────────────────────────────────────────────────────

def run(solo_liga: str | None = None, headful: bool = False):
    log.info("=" * 60)
    log.info(f"FootyStats Scraper v1.1  [{'HEADFUL' if headful else 'headless'}]")
    log.info("=" * 60)

    if solo_liga:
        log.info(f"Modo filtro: solo '{solo_liga}'")

    if headful:
        log.info(f"Perfil persistente: {PROFILE_DIR}")
        log.info("La ventana del browser se abrirá — no la cierres.")

    ok = 0
    fail = 0

    with sync_playwright() as p:
        if headful:
            # Perfil persistente: guarda cookies/sesión entre ejecuciones
            # → la segunda vez no necesita resolver Cloudflare ni hacer login
            PROFILE_DIR.mkdir(exist_ok=True)
            context = p.chromium.launch_persistent_context(
                user_data_dir=str(PROFILE_DIR),
                headless=False,
                accept_downloads=True,
                args=["--start-maximized"],
                no_viewport=True,
            )
            page = context.new_page()
        else:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(accept_downloads=True)
            page    = context.new_page()

        # 1. Login
        if not hacer_login(page, headful=headful):
            context.close()
            return

        # 2. Obtener links
        links = obtener_links_descarga(page)

        if not links:
            log.warning("No se encontraron links de descarga.")
            log.warning("Posibles causas:")
            log.warning("  - Cuenta sin Premium (solo EPL 2018 gratis)")
            log.warning("  - FootyStats cambió el HTML de la página de descargas")
            if headful:
                log.info("La ventana sigue abierta — navega manualmente a la página de descargas")
                log.info("y descarga los CSVs. Luego ponlos en: datos_footystats/")
                time.sleep(20)
            context.close()
            return

        # 3. Filtrar si se pidió una liga específica
        if solo_liga:
            links = [l for l in links if solo_liga.lower() in l["liga"].lower()]
            log.info(f"Links tras filtro: {len(links)}")

        # 4. Descargar
        for link in links:
            resultado = descargar_csv(page, link)
            if resultado:
                ok += 1
            else:
                fail += 1
            time.sleep(2)

        context.close()

    log.info("")
    log.info(f"Resumen: {ok} OK | {fail} fallidos")
    log.info(f"CSVs en: {DATOS_DIR}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FootyStats CSV Scraper v1.1")
    parser.add_argument("--liga", type=str, default=None,
                        help='Filtrar por liga. Ej: "Serie A"')
    parser.add_argument("--headful", action="store_true",
                        help="Abre browser visible — necesario si Cloudflare bloquea")
    args = parser.parse_args()
    run(solo_liga=args.liga, headful=args.headful)
