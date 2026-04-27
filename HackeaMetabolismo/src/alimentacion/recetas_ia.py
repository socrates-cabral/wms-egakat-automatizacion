"""
recetas_ia.py — Generación de recetas con Claude AI + lista de compras
Sprint S9
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
import sys as _sys; _sys.stdout.reconfigure(encoding="utf-8") if hasattr(_sys.stdout, "reconfigure") and _sys.platform == "win32" else None

import os
import json
from dotenv import load_dotenv
from src.utils.helpers import setup_logging
from src.utils.secrets import get_secret

load_dotenv(dotenv_path=Path(__file__).parent.parent.parent / ".env")
logger = setup_logging("recetas_ia")

PROMPT_RECETAS = """Eres un nutricionista experto. Genera {n} recetas con:
- Objetivo calórico: ~{kcal} kcal por receta
- Proteína mínima: {proteina_min}g
- Ingredientes disponibles: {ingredientes}
- Preferencias: {preferencias}
- Restricciones: {restricciones}

REGLAS:
- Los macros deben ser coherentes: kcal ≈ proteina_g×4 + cho_g×4 + grasa_g×9 (±5%).
- La proteína real de la receta debe ser ≥ {proteina_min}g.
- NUNCA copies los valores del ejemplo. Calcula los macros reales de los ingredientes.

Responde SOLO en JSON con este formato (sin explicaciones adicionales):
[
  {{
    "nombre": "Nombre real del plato",
    "tiempo_min": <minutos reales de preparación>,
    "kcal": <kcal calculadas de los ingredientes>,
    "proteina_g": <proteína real calculada>,
    "cho_g": <carbohidratos reales calculados>,
    "grasa_g": <grasa real calculada>,
    "ingredientes": [
      {{"nombre": "ingrediente", "cantidad": "Xg o unidades"}}
    ],
    "pasos": ["Paso 1...", "Paso 2..."],
    "lista_compras": ["ingrediente cantidad"]
  }}
]"""


def generar_recetas(
    kcal_objetivo: float,
    proteina_min_g: float,
    ingredientes: list[str] | None = None,
    preferencias: str = "variado",
    restricciones: str = "ninguna",
    n_recetas: int = 3,
) -> list[dict] | None:
    api_key = get_secret("ANTHROPIC_API_KEY")
    if not api_key or api_key.startswith("sk-ant-TUKEY"):
        logger.warning("API key no configurada. Retornando recetas demo.")
        return _recetas_demo(n_recetas, kcal_objetivo, proteina_min_g)

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key, timeout=45.0)

        prompt = PROMPT_RECETAS.format(
            n=n_recetas,
            kcal=round(kcal_objetivo, 0),
            proteina_min=round(proteina_min_g, 0),
            ingredientes=", ".join(ingredientes) if ingredientes else "cualquiera",
            preferencias=preferencias,
            restricciones=restricciones,
        )

        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )

        texto = resp.content[0].text.strip()
        if "```" in texto:
            texto = texto.split("```")[1].replace("json", "").strip()

        recetas = json.loads(texto)
        logger.info(f"Generadas {len(recetas)} recetas IA.")
        return recetas

    except Exception as e:
        logger.error(f"Error generando recetas: {e}")
        return _recetas_demo(n_recetas, kcal_objetivo, proteina_min_g)


def _recetas_demo(n: int, kcal: float, prot: float) -> list[dict]:
    demos = [
        {
            "nombre": "Pollo con batata y espinacas",
            "tiempo_min": 25,
            "kcal": 480, "proteina_g": 42, "cho_g": 38, "grasa_g": 11,
            "ingredientes": [
                {"nombre": "Pechuga de pollo", "cantidad": "200g"},
                {"nombre": "Batata", "cantidad": "150g"},
                {"nombre": "Espinacas", "cantidad": "100g"},
                {"nombre": "Aceite de oliva", "cantidad": "1 cda"},
            ],
            "pasos": [
                "Cocinar batata al horno a 200°C por 20 min.",
                "Saltear pollo en plancha con aceite de oliva 6 min por lado.",
                "Saltear espinacas 2 min. Servir todo junto.",
            ],
            "lista_compras": ["pechuga de pollo 200g", "batata 150g", "espinacas 100g"],
        },
        {
            "nombre": "Salmón con quinoa y brócoli",
            "tiempo_min": 30,
            "kcal": 510, "proteina_g": 44, "cho_g": 40, "grasa_g": 14,
            "ingredientes": [
                {"nombre": "Salmón", "cantidad": "180g"},
                {"nombre": "Quinoa cocida", "cantidad": "120g"},
                {"nombre": "Brócoli", "cantidad": "150g"},
                {"nombre": "Limón", "cantidad": "1/2"},
            ],
            "pasos": [
                "Cocinar quinoa según instrucciones.",
                "Hornear salmón a 180°C por 15 min con limón.",
                "Cocer brócoli al vapor 8 min. Servir.",
            ],
            "lista_compras": ["salmón 180g", "quinoa 120g", "brócoli 150g"],
        },
        {
            "nombre": "Tortilla de claras con avena y fruta",
            "tiempo_min": 15,
            "kcal": 390, "proteina_g": 35, "cho_g": 42, "grasa_g": 7,
            "ingredientes": [
                {"nombre": "Claras de huevo", "cantidad": "6 unidades"},
                {"nombre": "Avena", "cantidad": "50g"},
                {"nombre": "Plátano", "cantidad": "1 mediano"},
                {"nombre": "Canela", "cantidad": "al gusto"},
            ],
            "pasos": [
                "Mezclar claras con avena y canela.",
                "Cocinar en sartén antiadherente.",
                "Servir con plátano cortado.",
            ],
            "lista_compras": ["claras de huevo 6u", "avena 50g", "plátano 1u"],
        },
    ]
    return demos[:n]


def consolidar_lista_compras(recetas: list[dict]) -> list[str]:
    """Une todas las listas de compras de un conjunto de recetas."""
    items = []
    for receta in recetas:
        items.extend(receta.get("lista_compras", []))
    return sorted(set(items))
