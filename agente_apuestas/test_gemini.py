import sys
if sys.stdout:
    sys.stdout.reconfigure(encoding="utf-8")
from multi_llm_analyst import llamar_gemini
r = llamar_gemini("Responde CONFIRMAR en la primera linea, luego escribe Test exitoso.")
print("GEMINI:", r[:200])
