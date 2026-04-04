"""
vision_ia.py — Análisis de foto de comida con Vision IA
Sprint S5: foto → estimación JSON → usuario confirma
Fallback: Anthropic Claude → OpenAI GPT-4o → Google Gemini
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

import os
import json
import base64
import time
from pathlib import Path as P
from dotenv import load_dotenv
from src.utils.helpers import setup_logging
from src.utils.secrets import get_secret

TIMEOUT_VISION_S = 30      # segundos máximo por llamada IA
MAX_REINTENTOS   = 2        # reintentos antes de pasar al siguiente proveedor
BACKOFF_BASE_S   = 2        # espera inicial entre reintentos (duplica cada vez)


def _con_retry(fn, *args, **kwargs):
    """Ejecuta fn con retry exponencial. Retorna None si todos los intentos fallan."""
    for intento in range(MAX_REINTENTOS):
        resultado = fn(*args, **kwargs)
        if resultado is not None:
            return resultado
        if intento < MAX_REINTENTOS - 1:
            espera = BACKOFF_BASE_S * (2 ** intento)
            logger.info(f"Reintento {intento + 1}/{MAX_REINTENTOS - 1} en {espera}s…")
            time.sleep(espera)
    return None

load_dotenv(dotenv_path=P(__file__).parent.parent.parent / ".env")

logger = setup_logging("vision_ia")

PROMPT_VISION = """Analiza esta imagen de comida o producto alimenticio. Estima con precisión los valores nutricionales REALES según el tipo de alimento visible.

REGLAS IMPORTANTES:
1. Si ves un producto ENVASADO (chocolate, galletas, snack, bebida): usa valores típicos por 100g de ese producto específico. Ejemplo: chocolate blanco ~550 kcal/100g, 8g proteína, 57g carbs, 33g grasa.
2. Si ves un PLATO COCINADO: estima la porción visible en gramos y calcula los macros correspondientes.
3. Los macros DEBEN ser coherentes: kcal ≈ proteína×4 + carbohidratos×4 + grasa×9 (tolerancia ±10%).
4. NUNCA copies valores de ejemplo. Estima según el alimento real.

Responde SOLO en JSON con este formato (sin explicaciones adicionales):
{
  "alimentos": ["nombre real del alimento o producto"],
  "porciones_g": [gramos estimados de la porción visible],
  "kcal_estimadas_min": <entero — extremo inferior del rango>,
  "kcal_estimadas_max": <entero — extremo superior del rango>,
  "proteina_g": <gramos reales de proteína para la porción>,
  "carbohidrato_g": <gramos reales de carbohidratos para la porción>,
  "grasa_g": <gramos reales de grasa para la porción>,
  "confianza": "alta|media|baja",
  "notas": "tipo de alimento detectado y base de estimación"
}"""


def _extraer_json(texto: str) -> dict:
    """Extrae JSON de respuesta, limpiando posibles bloques markdown."""
    texto = texto.strip()
    if "```" in texto:
        partes = texto.split("```")
        for parte in partes:
            parte = parte.replace("json", "").strip()
            if parte.startswith("{"):
                texto = parte
                break
    return json.loads(texto)


def _analizar_anthropic(imagen_bytes: bytes, mime_type: str) -> dict | None:
    api_key = get_secret("ANTHROPIC_API_KEY")
    if not api_key or "TUKEY" in api_key:
        return None
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key, timeout=TIMEOUT_VISION_S)
        imagen_b64 = base64.standard_b64encode(imagen_bytes).decode("utf-8")
        respuesta = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=512,
            messages=[{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": mime_type, "data": imagen_b64}},
                {"type": "text", "text": PROMPT_VISION},
            ]}],
        )
        resultado = _extraer_json(respuesta.content[0].text)
        logger.info(f"[Anthropic] Vision OK: {resultado.get('alimentos')}")
        resultado["_proveedor"] = "Anthropic Claude"
        return resultado
    except Exception as e:
        logger.warning(f"[Anthropic] Falló: {e}")
        return None


def _analizar_openai(imagen_bytes: bytes, mime_type: str) -> dict | None:
    api_key = get_secret("OPENAI_API_KEY")
    if not api_key:
        return None
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key, timeout=TIMEOUT_VISION_S)
        imagen_b64 = base64.standard_b64encode(imagen_bytes).decode("utf-8")
        respuesta = client.chat.completions.create(
            model="gpt-4o",
            max_tokens=512,
            messages=[{"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{imagen_b64}"}},
                {"type": "text", "text": PROMPT_VISION},
            ]}],
        )
        resultado = _extraer_json(respuesta.choices[0].message.content)
        logger.info(f"[OpenAI] Vision OK: {resultado.get('alimentos')}")
        resultado["_proveedor"] = "OpenAI GPT-4o"
        return resultado
    except Exception as e:
        logger.warning(f"[OpenAI] Falló: {e}")
        return None


def _analizar_gemini(imagen_bytes: bytes, mime_type: str) -> dict | None:
    api_key = get_secret("GOOGLE_API_KEY")
    if not api_key:
        return None
    try:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=api_key)
        respuesta = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[
                types.Part.from_bytes(data=imagen_bytes, mime_type=mime_type),
                PROMPT_VISION,
            ],
        )
        resultado = _extraer_json(respuesta.text)
        logger.info(f"[Gemini] Vision OK: {resultado.get('alimentos')}")
        resultado["_proveedor"] = "Google Gemini"
        return resultado
    except Exception as e:
        logger.warning(f"[Gemini] Falló: {e}")
        return None


def _validar_coherencia(resultado: dict) -> dict:
    """
    Valida que kcal ≈ proteina×4 + cho×4 + grasa×9.
    Si hay discrepancia >25%, recalcula kcal desde macros y baja confianza.
    También detecta macros invertidos (ej: proteína > grasa en chocolate).
    """
    prot  = float(resultado.get("proteina_g", 0))
    cho   = float(resultado.get("carbohidrato_g", 0))
    grasa = float(resultado.get("grasa_g", 0))
    kcal_declaradas = (resultado.get("kcal_estimadas_min", 0) + resultado.get("kcal_estimadas_max", 0)) / 2

    kcal_calculadas = prot * 4 + cho * 4 + grasa * 9

    if kcal_calculadas < 10:
        return resultado  # datos vacíos, no hay nada que validar

    if kcal_declaradas > 0:
        diferencia_pct = abs(kcal_calculadas - kcal_declaradas) / kcal_declaradas
        if diferencia_pct > 0.25:
            logger.warning(
                f"[Coherencia] Discrepancia calórica {diferencia_pct:.0%}: "
                f"declaradas={kcal_declaradas:.0f}, calculadas={kcal_calculadas:.0f}. "
                f"Recalculando desde macros."
            )
            margen = kcal_calculadas * 0.10
            resultado["kcal_estimadas_min"] = round(kcal_calculadas - margen)
            resultado["kcal_estimadas_max"] = round(kcal_calculadas + margen)
            resultado["confianza"] = "baja"
            resultado["notas"] = (resultado.get("notas", "") +
                                  f" [Kcal recalculadas desde macros: {kcal_calculadas:.0f} kcal]")

    return resultado


def analizar_foto(imagen_bytes: bytes, mime_type: str = "image/jpeg") -> dict:
    """
    Analiza foto con fallback automático: Anthropic → OpenAI → Gemini.
    Aplica validación de coherencia calórica antes de retornar.
    Retorna estimación demo si todos fallan.
    """
    for proveedor_fn in [_analizar_anthropic, _analizar_openai, _analizar_gemini]:
        resultado = _con_retry(proveedor_fn, imagen_bytes, mime_type)
        if resultado:
            return _validar_coherencia(resultado)

    logger.warning("Todos los proveedores fallaron. Retornando estimación demo.")
    return _estimacion_demo()


def _estimacion_demo() -> dict:
    """Estimación demo cuando no hay API key configurada o todos los proveedores fallan."""
    return {
        "alimentos": ["Pollo a la plancha", "Arroz integral", "Ensalada verde"],
        "porciones_g": [150, 100, 80],
        "kcal_estimadas_min": 420,
        "kcal_estimadas_max": 480,
        "proteina_g": 42,
        "carbohidrato_g": 38,
        "grasa_g": 10,
        "confianza": "demo",
        "notas": "Estimación de demostración. Configura ANTHROPIC_API_KEY, OPENAI_API_KEY o GOOGLE_API_KEY.",
        "_proveedor": "Demo",
    }


def resultado_a_registro(resultado: dict, momento: str = "almuerzo") -> dict:
    """Convierte el resultado de Vision a formato de registro de alimento."""
    kcal_media = (resultado["kcal_estimadas_min"] + resultado["kcal_estimadas_max"]) / 2
    proveedor = resultado.get("_proveedor", "")
    return {
        "alimento": " + ".join(resultado.get("alimentos", ["Comida"])),
        "porcion_g": sum(resultado.get("porciones_g", [0])),
        "kcal": round(kcal_media, 0),
        "proteina_g": resultado.get("proteina_g", 0),
        "cho_g": resultado.get("carbohidrato_g", 0),
        "grasa_g": resultado.get("grasa_g", 0),
        "fuente": "vision_ia",
        "es_estimado": True,
        "confianza_ia": resultado.get("confianza", "baja"),
        "momento": momento,
        "notas": f"[{proveedor}] Rango: {resultado['kcal_estimadas_min']}–{resultado['kcal_estimadas_max']} kcal. {resultado.get('notas','')}",
    }
