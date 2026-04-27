import sys
sys.stdout.reconfigure(encoding="utf-8")

from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from claude_agent import llamar_openai

SISTEMA = """Eres el clasificador de intenciones del sistema financiero de Egakat SPA.
Dado un mensaje, responde ÚNICAMENTE con una de estas palabras:
COBRANZA | ALERTAS | PROYECCION | GENERAL

Reglas:
- COBRANZA: cartera, deuda, facturas, saldo, DSO, cobro, cliente específico,
  análisis, vencidos, quién debe, cuánto nos deben, días de pago
- ALERTAS: qué pagó hoy, pagos del día, pagos recibidos, novedades
- PROYECCION: proyección, caja, próxima semana, cuánto entra, forecast
- GENERAL: saludos, ayuda, preguntas fuera de contexto financiero, todo lo demás

Responde SOLO la palabra, sin puntuación ni explicación."""


def clasificar(mensaje: str) -> str:
    """Retorna: COBRANZA | ALERTAS | PROYECCION | GENERAL"""
    historial = [{"role": "user", "content": mensaje}]
    resultado = llamar_openai(SISTEMA, historial, max_tokens=10)
    resultado = resultado.strip().upper()
    if resultado not in {"COBRANZA", "ALERTAS", "PROYECCION", "GENERAL"}:
        return "GENERAL"
    return resultado
