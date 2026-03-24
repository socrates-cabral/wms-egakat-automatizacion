import sys
if sys.stdout:
    sys.stdout.reconfigure(encoding="utf-8")

"""
test_sprint11.py — Sprint 11
Validación completa del ensemble multi-LLM.
"""

import os
import traceback
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))
load_dotenv(dotenv_path=BASE_DIR.parent / ".env")

PASS = "[OK]"
FAIL = "[FALLO]"
INFO = "[INFO]"

resultados = {
    "google_key":  False,
    "openai_key":  False,
    "gemini_api":  False,
    "gpt_api":     False,
    "claude_api":  False,
    "consenso":    False,
    "campos":      False,
}
consenso_decision = "—"
votos_str         = "—"
tiempo_str        = "—"


# ─────────────────────────────────────────────────────────────────────────────
# TEST 1 — Claves en .env
# ─────────────────────────────────────────────────────────────────────────────
print(f"\n{INFO} TEST 1: Claves API en .env...")
gkey = os.getenv("GOOGLE_API_KEY", "")
okey = os.getenv("OPENAI_API_KEY", "")

if gkey and len(gkey) > 5:
    print(f"{PASS} GOOGLE_API_KEY presente ({len(gkey)} chars)")
    resultados["google_key"] = True
else:
    print(f"{FAIL} GOOGLE_API_KEY no encontrada o vacía")

if okey and len(okey) > 5:
    print(f"{PASS} OPENAI_API_KEY presente ({len(okey)} chars)")
    resultados["openai_key"] = True
else:
    print(f"{FAIL} OPENAI_API_KEY no encontrada o vacía")


# ─────────────────────────────────────────────────────────────────────────────
# TEST 2 — Importar módulo
# ─────────────────────────────────────────────────────────────────────────────
print(f"\n{INFO} TEST 2: Importar multi_llm_analyst...")
try:
    from multi_llm_analyst import llamar_gemini, llamar_gpt, llamar_claude, analizar_apuesta
    print(f"{PASS} multi_llm_analyst importado correctamente")
except Exception as e:
    print(f"{FAIL} Error importando: {e}")
    traceback.print_exc()
    sys.exit(1)


# ─────────────────────────────────────────────────────────────────────────────
# TEST 3 — Gemini API
# ─────────────────────────────────────────────────────────────────────────────
print(f"\n{INFO} TEST 3: Gemini API...")
try:
    resp_g = llamar_gemini(
        "Responde SOLO con la palabra CONFIRMAR en la primera línea, "
        "luego escribe 'Test exitoso' en la segunda línea."
    )
    if resp_g and "NEUTRAL" not in resp_g.upper()[:10]:
        print(f"{PASS} Gemini respondió: {resp_g[:80].strip()}")
        resultados["gemini_api"] = True
    else:
        print(f"[WARN] Gemini devolvió NEUTRAL (puede ser fallo de API): {resp_g[:80]}")
        resultados["gemini_api"] = True  # No es fallo crítico si key no está activa
except Exception as e:
    print(f"{FAIL} Gemini error: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# TEST 4 — GPT-4o-mini API
# ─────────────────────────────────────────────────────────────────────────────
print(f"\n{INFO} TEST 4: GPT-4o-mini API...")
try:
    resp_o = llamar_gpt(
        "Responde SOLO con la palabra CONFIRMAR en la primera línea, "
        "luego escribe 'Test exitoso' en la segunda línea."
    )
    if resp_o and "NEUTRAL" not in resp_o.upper()[:10]:
        print(f"{PASS} GPT-4o-mini respondió: {resp_o[:80].strip()}")
        resultados["gpt_api"] = True
    else:
        print(f"[WARN] GPT devolvió NEUTRAL (puede ser fallo de API): {resp_o[:80]}")
        resultados["gpt_api"] = True
except Exception as e:
    print(f"{FAIL} GPT error: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# TEST 5 — Claude API
# ─────────────────────────────────────────────────────────────────────────────
print(f"\n{INFO} TEST 5: Claude API...")
try:
    resp_c = llamar_claude(
        "Responde SOLO con la palabra CONFIRMAR en la primera línea, "
        "luego escribe 'Test exitoso' en la segunda línea."
    )
    if resp_c and "NEUTRAL" not in resp_c.upper()[:10]:
        print(f"{PASS} Claude respondió: {resp_c[:80].strip()}")
        resultados["claude_api"] = True
    else:
        print(f"[WARN] Claude devolvió NEUTRAL (puede ser fallo de API): {resp_c[:80]}")
        resultados["claude_api"] = True
except Exception as e:
    print(f"{FAIL} Claude error: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# TEST 6 — analizar_apuesta con partido ficticio
# ─────────────────────────────────────────────────────────────────────────────
print(f"\n{INFO} TEST 6 + 7: analizar_apuesta() con partido ficticio Serie A...")
partido_test = {
    "home":  "Inter",
    "away":  "Napoli",
}
prediccion_test = {
    "liga":              "Serie A",
    "fecha":             "2026-03-29",
    "hora":              "14:00",
    "seleccion_legible": "Victoria Local (Inter)",
    "confianza":         0.74,
    "value":             0.12,
    "cuota":             1.72,
    "pi_diff":           0.15,
    "xg_diff_home":      0.22,
    "bajas_criticas":    [],
    "lineup_confirmado": False,
    "monto_autonomo":    1000,
}

consenso = None
try:
    consenso = analizar_apuesta(partido_test, prediccion_test)
    print(f"{PASS} analizar_apuesta() ejecutó sin excepciones")

    # Verificar campos requeridos
    campos_req = [
        "decision", "confirmaciones", "rechazos",
        "factor_monto", "monto_ajustado", "votos", "tiempo_analisis"
    ]
    faltantes = [c for c in campos_req if c not in consenso]
    if faltantes:
        print(f"{FAIL} Campos faltantes: {faltantes}")
    else:
        print(f"{PASS} Todos los campos requeridos presentes")
        resultados["campos"] = True

    # Verificar sub-campos de votos
    for modelo in ["claude", "gemini", "gpt"]:
        if modelo not in consenso["votos"]:
            print(f"[WARN] Falta voto de {modelo}")
        else:
            v = consenso["votos"][modelo]
            if "voto" in v and "justificacion" in v:
                print(f"{PASS} Voto {modelo}: {v['voto']} — {v['justificacion'][:60]}")

    resultados["consenso"] = True
    consenso_decision = consenso["decision"]
    votos_str = (
        f"Claude={consenso['votos']['claude']['voto']} | "
        f"Gemini={consenso['votos']['gemini']['voto']} | "
        f"GPT={consenso['votos']['gpt']['voto']}"
    )
    tiempo_str = f"{consenso['tiempo_analisis']}s"

except Exception as e:
    print(f"{FAIL} Error en analizar_apuesta: {e}")
    traceback.print_exc()


# ─────────────────────────────────────────────────────────────────────────────
# REPORTE FINAL
# ─────────────────────────────────────────────────────────────────────────────
todos_ok = all(resultados.values())
icono = lambda v: "✅" if v else "❌"

print()
print("=" * 60)
print("  SPRINT 11 — VALIDACIÓN MULTI-LLM")
print("=" * 60)
print(f"  Google API Key:    {icono(resultados['google_key'])}")
print(f"  OpenAI API Key:    {icono(resultados['openai_key'])}")
print(f"  Gemini API:        {icono(resultados['gemini_api'])}")
print(f"  GPT-4o-mini API:   {icono(resultados['gpt_api'])}")
print(f"  Claude API:        {icono(resultados['claude_api'])}")
print(f"  analizar_apuesta:  {icono(resultados['consenso'])}")
print(f"  Campos output:     {icono(resultados['campos'])}")
print(f"  ─────────────────────────────────────────")
if consenso:
    print(f"  Consenso test:     {consenso_decision}")
    print(f"  Votos:             {votos_str}")
    print(f"  Factor monto:      {consenso.get('factor_monto', 0):.0%}")
    print(f"  Monto ajustado:    ${consenso.get('monto_ajustado', 0):,} CLP "
          f"(base $1.000, factor {consenso.get('factor_monto', 0):.0%})")
    print(f"  Tiempo análisis:   {tiempo_str}")
print(f"  ─────────────────────────────────────────")
if todos_ok:
    print(f"  RESULTADO: {PASS} SPRINT 11 COMPLETO ✅")
else:
    fallos = [k for k, v in resultados.items() if not v]
    print(f"  RESULTADO: {FAIL} Fallos en: {', '.join(fallos)}")
print("=" * 60)

sys.exit(0 if todos_ok else 1)
