"""
openfoodfacts.py — Búsqueda de alimentos por texto y barcode
Open Food Facts API v2 (gratuita, sin key)
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

import requests
from src.utils.helpers import setup_logging

logger = setup_logging("openfoodfacts")

import re

BASE_URL    = "https://world.openfoodfacts.org"
SEARCH_URL  = f"{BASE_URL}/cgi/search.pl"
PRODUCT_URL = f"{BASE_URL}/api/v2/product"
TIMEOUT     = 8


def _parsear_porcion_g(serving_size_str: str) -> float | None:
    """Extrae los gramos de strings como '30g', '1 barra (30g)', '30 g', '1 portion (55g)'."""
    if not serving_size_str:
        return None
    # Busca el último número seguido de 'g' en el string
    matches = re.findall(r"(\d+(?:[.,]\d+)?)\s*g", serving_size_str, re.IGNORECASE)
    if matches:
        try:
            return float(matches[-1].replace(",", "."))
        except ValueError:
            return None
    return None


def _extraer_nutrientes(producto: dict) -> dict:
    n = producto.get("nutriments", {})
    serving_str = producto.get("serving_size", "") or ""
    porcion_ref = _parsear_porcion_g(serving_str)

    return {
        "alimento":        producto.get("product_name", "Sin nombre"),
        "marca":           producto.get("brands", ""),
        "porcion_g":       porcion_ref or 100.0,           # numérico, default 100g
        "porcion_str":     serving_str,                    # texto original del envase
        "kcal":            round(float(n.get("energy-kcal_100g") or n.get("energy_100g", 0) / 4.184 or 0), 1),
        "proteina_g":      round(float(n.get("proteins_100g", 0)), 1),
        "cho_g":           round(float(n.get("carbohydrates_100g", 0)), 1),
        "grasa_g":         round(float(n.get("fat_100g", 0)), 1),
        "fibra_g":         round(float(n.get("fiber_100g", 0)), 1),
        "azucar_g":        round(float(n.get("sugars_100g", 0)), 1),
        "sodio_mg":        round(float(n.get("sodium_100g", 0)) * 1000, 1),
        "barcode":         producto.get("code", ""),
        "fuente":          "openfoodfacts",
    }


def buscar_por_texto(query: str, max_resultados: int = 8) -> list[dict]:
    """Busca alimentos por nombre. Retorna lista de dicts con nutrientes por 100g."""
    try:
        resp = requests.get(SEARCH_URL, params={
            "search_terms": query,
            "search_simple": 1,
            "action": "process",
            "json": 1,
            "page_size": max_resultados,
            "fields": "product_name,brands,nutriments,serving_size,code",
            "lc": "es",
        }, timeout=TIMEOUT)
        resp.raise_for_status()
        productos = resp.json().get("products", [])
        resultados = []
        for p in productos:
            if p.get("product_name") and p.get("nutriments"):
                resultados.append(_extraer_nutrientes(p))
        logger.info(f"Búsqueda '{query}': {len(resultados)} resultados")
        return resultados
    except requests.Timeout:
        logger.warning("Open Food Facts timeout")
        return []
    except Exception as e:
        logger.error(f"Error búsqueda OFF: {e}")
        return []


def buscar_por_barcode(barcode: str) -> dict | None:
    """Busca un producto por código de barras."""
    try:
        resp = requests.get(
            f"{PRODUCT_URL}/{barcode}.json",
            params={"fields": "product_name,brands,nutriments,serving_size,code"},
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") == 1 and data.get("product"):
            return _extraer_nutrientes(data["product"])
        return None
    except Exception as e:
        logger.error(f"Error barcode {barcode}: {e}")
        return None


def ajustar_por_porcion(nutrientes_100g: dict, gramos: float) -> dict:
    """Escala los valores nutricionales a la porción indicada."""
    factor = gramos / 100
    campos_numericos = ["kcal", "proteina_g", "cho_g", "grasa_g", "fibra_g", "azucar_g", "sodio_mg"]
    resultado = nutrientes_100g.copy()
    for campo in campos_numericos:
        if campo in resultado:
            resultado[campo] = round(resultado[campo] * factor, 1)
    resultado["porcion_g"] = gramos
    return resultado
