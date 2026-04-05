import sys
if sys.stdout:
    sys.stdout.reconfigure(encoding="utf-8")

"""
multi_llm_analyst.py — Sprint 11
Consulta 3 LLMs en paralelo (Claude + Gemini + GPT-4o-mini)
y genera consenso sobre cada apuesta recomendada.
"""

import os
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

TIMEOUT_LLM = 15  # segundos por modelo (Gemini 2.5 puede tardar ~10-12s)


def _log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


# ─────────────────────────────────────────────────────────────────────────────
# FUNCIÓN 1 — Gemini
# ─────────────────────────────────────────────────────────────────────────────

def llamar_gemini(prompt: str) -> tuple[str, int]:
    """Llama a Gemini 2.0 Flash. Retorna (texto, tokens_usados) o ('NEUTRAL', 0) si falla."""
    try:
        # Usamos google-genai (nuevo SDK — google.generativeai está deprecado)
        from google import genai
        client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
        response = client.models.generate_content(
            model="models/gemini-2.5-flash",
            contents=prompt,
        )
        tokens = getattr(response.usage_metadata, "total_token_count", 0) or 0
        return response.text, tokens
    except Exception as e:
        _log(f"[WARN] Gemini falló: {e}")
        return "NEUTRAL", 0


# ─────────────────────────────────────────────────────────────────────────────
# FUNCIÓN 2 — GPT-4o-mini
# ─────────────────────────────────────────────────────────────────────────────

def llamar_gpt(prompt: str) -> tuple[str, int]:
    """Llama a GPT-4o-mini. Retorna (texto, tokens_usados) o ('NEUTRAL', 0) si falla."""
    try:
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=150,
            temperature=0.3,
        )
        tokens = getattr(resp.usage, "total_tokens", 0) or 0
        return resp.choices[0].message.content, tokens
    except Exception as e:
        _log(f"[WARN] GPT-4o-mini falló: {e}")
        return "NEUTRAL", 0


# ─────────────────────────────────────────────────────────────────────────────
# FUNCIÓN 3 — Claude
# ─────────────────────────────────────────────────────────────────────────────

def llamar_claude(prompt: str) -> tuple[str, int]:
    """Llama a Claude Haiku. Retorna (texto, tokens_usados) o ('NEUTRAL', 0) si falla."""
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        msg = client.messages.create(
            model="claude-haiku-4-5-latest",
            max_tokens=150,
            messages=[{"role": "user", "content": prompt}],
        )
        tokens = (msg.usage.input_tokens or 0) + (msg.usage.output_tokens or 0)
        return msg.content[0].text, tokens
    except Exception as e:
        _log(f"[WARN] Claude falló: {e}")
        return "NEUTRAL", 0


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _parsear_voto(texto: str) -> tuple[str, str]:
    """
    Extrae voto (CONFIRMAR/RECHAZAR/NEUTRAL) y justificación del texto.
    Retorna (voto, justificacion).
    """
    lineas = [l.strip() for l in texto.strip().split("\n") if l.strip()]
    primera = lineas[0].upper() if lineas else ""
    if "CONFIRMAR" in primera:
        voto = "CONFIRMAR"
    elif "RECHAZAR" in primera:
        voto = "RECHAZAR"
    else:
        voto = "NEUTRAL"
    # Justificación = líneas siguientes (máx 1)
    just = lineas[1] if len(lineas) > 1 else ""
    # Limpiar prefijos comunes
    for pref in ["justificación:", "justificacion:", "razon:", "razón:"]:
        if just.lower().startswith(pref):
            just = just[len(pref):].strip()
    return voto, just[:120]  # máx 120 chars


def _llamar_con_timeout(fn, prompt: str, nombre: str) -> tuple[str, int]:
    """Llama a fn(prompt) con timeout de TIMEOUT_LLM segundos. Retorna (texto, tokens)."""
    with ThreadPoolExecutor(max_workers=1) as ex:
        fut = ex.submit(fn, prompt)
        try:
            return fut.result(timeout=TIMEOUT_LLM)
        except FuturesTimeout:
            _log(f"[WARN] {nombre} timeout ({TIMEOUT_LLM}s) — NEUTRAL")
            return "NEUTRAL", 0
        except Exception as e:
            _log(f"[WARN] {nombre} error — {e} — NEUTRAL")
            return "NEUTRAL", 0


# ─────────────────────────────────────────────────────────────────────────────
# FUNCIÓN 4 — analizar_apuesta
# ─────────────────────────────────────────────────────────────────────────────

def analizar_apuesta(partido: dict, prediccion: dict) -> dict:
    """
    Consulta los 3 LLMs en paralelo sobre una apuesta recomendada.

    Parámetros:
        partido:    dict con 'home', 'away' (puede ser el mismo rec dict)
        prediccion: dict con liga, fecha, hora, seleccion_legible, confianza,
                    value, cuota, pi_diff, xg_diff_home, bajas_criticas,
                    lineup_confirmado, monto_autonomo

    Retorna dict con: decision, confirmaciones, rechazos, factor_monto,
                      monto_ajustado, votos, tiempo_analisis
    """
    t0 = time.time()

    home = partido.get("home", prediccion.get("home", "Local"))
    away = partido.get("away", prediccion.get("away", "Visitante"))

    prompt = f"""Eres un analista deportivo experto. Analiza esta apuesta:

PARTIDO: {home} vs {away}
LIGA: {prediccion.get('liga', 'Serie A')}
FECHA: {prediccion.get('fecha', '')} {prediccion.get('hora', '')}

PREDICCIÓN DEL MODELO ESTADÍSTICO:
  Selección: {prediccion.get('seleccion_legible', prediccion.get('seleccion', ''))}
  Confianza: {prediccion.get('confianza', 0)*100:.0f}%
  Value vs bookmaker: +{prediccion.get('value', 0)*100:.1f}%
  Cuota Betano: {prediccion.get('cuota', 0)}

DATOS ESTADÍSTICOS:
  Pi-Rating diferencial: {prediccion.get('pi_diff', 0):+.2f}
  xG diferencial: {prediccion.get('xg_diff_home', 0):+.2f}
  Bajas críticas: {', '.join(prediccion.get('bajas_criticas', [])) or 'Ninguna'}
  Lineup confirmado: {'Sí' if prediccion.get('lineup_confirmado', False) else 'No'}

INSTRUCCIÓN:
Responde SOLO con una de estas 3 palabras en la primera línea:
CONFIRMAR / RECHAZAR / NEUTRAL

Luego una justificación de máximo 2 líneas.
Considera solo factores que el modelo estadístico podría haber ignorado
(noticias recientes, contexto táctico, motivación del equipo).
"""

    _log(f"[INFO] Consultando 3 LLMs para {home} vs {away}...")

    # Llamar en paralelo (3 threads simultáneos)
    with ThreadPoolExecutor(max_workers=3) as executor:
        fut_claude = executor.submit(_llamar_con_timeout, llamar_claude, prompt, "Claude")
        fut_gemini = executor.submit(_llamar_con_timeout, llamar_gemini, prompt, "Gemini")
        fut_gpt    = executor.submit(_llamar_con_timeout, llamar_gpt,    prompt, "GPT")

        resp_claude, tok_claude = fut_claude.result()
        resp_gemini, tok_gemini = fut_gemini.result()
        resp_gpt,    tok_gpt    = fut_gpt.result()

    tokens_usados = tok_claude + tok_gemini + tok_gpt

    # Parsear votos
    voto_claude, just_claude = _parsear_voto(resp_claude)
    voto_gemini, just_gemini = _parsear_voto(resp_gemini)
    voto_gpt,    just_gpt    = _parsear_voto(resp_gpt)

    votos_lista    = [voto_claude, voto_gemini, voto_gpt]
    confirmaciones = votos_lista.count("CONFIRMAR")
    rechazos       = votos_lista.count("RECHAZAR")

    # Detectar diminishing returns: todos NEUTRAL = APIs fallaron, gasto sin retorno
    # Patrón spec/01 token budget — señal de que la llamada no aportó valor
    todos_neutral_por_fallo = all(v == "NEUTRAL" for v in votos_lista)
    if todos_neutral_por_fallo:
        _log(f"[BUDGET] {home} vs {away}: los 3 LLMs retornaron NEUTRAL (APIs caídas/timeout) "
             f"— {tokens_usados} tokens gastados sin retorno. Considerar skip en próxima iteración.")

    # Calcular decisión y factor de monto
    if confirmaciones >= 2:
        decision = "CONFIRMAR"
        factor_monto = 1.0 if confirmaciones == 3 else 0.75
    elif rechazos >= 2:
        decision = "RECHAZAR"
        factor_monto = 0.0
    else:
        decision = "NEUTRAL"
        factor_monto = 0.50

    monto_base     = prediccion.get("monto_autonomo", 0)
    monto_ajustado = int(monto_base * factor_monto)
    tiempo_total   = round(time.time() - t0, 2)

    _log(f"[OK] Consenso {home} vs {away}: {decision} "
         f"({confirmaciones}/3 confirmar, {rechazos}/3 rechazar) "
         f"| factor={factor_monto} | {tiempo_total}s")

    return {
        "decision":            decision,
        "confirmaciones":      confirmaciones,
        "rechazos":            rechazos,
        "factor_monto":        factor_monto,
        "monto_ajustado":      monto_ajustado,
        "votos": {
            "claude": {"voto": voto_claude, "justificacion": just_claude},
            "gemini": {"voto": voto_gemini, "justificacion": just_gemini},
            "gpt":    {"voto": voto_gpt,    "justificacion": just_gpt},
        },
        "tiempo_analisis":     tiempo_total,
        # Telemetría spec/01 token budget
        "tokens_usados":       tokens_usados,
        "diminishing_returns": todos_neutral_por_fallo,
    }
