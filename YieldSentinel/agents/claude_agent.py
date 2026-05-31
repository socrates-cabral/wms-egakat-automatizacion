"""
AGENTE CLAUDE AI — YIELD SENTINEL
===================================
Responsabilidad única: análisis inteligente de noticias macro
usando la API de Anthropic.

En Fase 1: opcional (no bloquea el sistema si no hay API key)
En Fase 3: recomendado para mejorar la calidad de las señales

La diferencia con el NewsAgent básico:
- NewsAgent detecta palabras clave (rápido, determinista, sin costo)
- ClaudeAgent entiende CONTEXTO (más lento, requiere API key, mejor calidad)

Ejemplo:
Noticia: "Fed pauses rate hikes amid mixed economic signals"
NewsAgent → detecta "Fed", clasifica como "macro", confianza 0.4
ClaudeAgent → entiende que la pausa es moderadamente bullish para oro,
              pero incierto para petróleo, da contexto histórico,
              y te dice qué otros datos watch esta semana.
"""

import json
import logging
import os
import sys
from datetime import datetime
from typing import Optional
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import ANTHROPIC_API_KEY, CLAUDE_MODEL

os.makedirs("data/logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [CLAUDE_AI] %(message)s",
    handlers=[
        logging.FileHandler("data/logs/claude_agent.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """Eres un analista de mercados financieros especializado en commodities 
(oro, plata, petróleo) con 20 años de experiencia. 
Analizas noticias macro para determinar su impacto en precios de corto plazo (1-48 horas).

Siempre respondes ÚNICAMENTE en JSON válido con esta estructura exacta:
{
  "affected_assets": ["GOLD", "CL"],
  "primary_direction": "bullish|bearish|neutral",
  "confidence": 0.0-1.0,
  "timeframe_hours": 24,
  "reasoning": "Explicación breve en español (máx 100 palabras)",
  "key_levels_to_watch": "Qué niveles de precio observar",
  "risk_factors": "Qué podría invalidar esta señal",
  "signal_strength": "strong|moderate|weak"
}

Sé conservador con la confianza. Reserva 0.8+ para eventos geopolíticos mayores 
o decisiones de política monetaria con impacto claro y directo.
No uses markdown ni texto fuera del JSON."""


class ClaudeAnalystAgent:
    """
    Agente de análisis usando Claude AI.
    
    Mejora las señales del NewsAgent con comprensión contextual:
    - Entiende el contexto histórico y político
    - Identifica impactos indirectos y correlaciones
    - Distingue entre ruido de mercado y señales reales
    - Da una evaluación de riesgo/reward narrativa
    """

    def __init__(self):
        self.api_key  = ANTHROPIC_API_KEY
        self.model    = CLAUDE_MODEL
        self.enabled  = bool(self.api_key and "TU_" not in self.api_key)
        self.call_count = 0

        if self.enabled:
            logger.info(f"ClaudeAnalystAgent activo — modelo: {self.model}")
        else:
            logger.info(
                "ClaudeAnalystAgent en modo SIMULADO "
                "(agrega ANTHROPIC_API_KEY en config.py para activar)"
            )

    def analyze_news(self, title: str, summary: str = "") -> Optional[dict]:
        """
        Analiza una noticia y retorna señal estructurada.
        
        Si no hay API key, retorna un análisis simulado (útil para desarrollo).
        """
        if not self.enabled:
            return self._simulate_analysis(title)

        prompt = (
            f"Analiza el impacto en mercados de commodities de esta noticia:\n\n"
            f"TITULAR: {title}\n"
            f"RESUMEN: {summary[:500] if summary else '(no disponible)'}\n\n"
            f"Fecha actual: {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}"
        )

        try:
            import requests
            self.call_count += 1

            response = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key":         self.api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type":      "application/json",
                },
                json={
                    "model":      self.model,
                    "max_tokens": 400,
                    "system":     SYSTEM_PROMPT,
                    "messages":   [{"role": "user", "content": prompt}],
                },
                timeout=15,
            )

            if response.status_code != 200:
                logger.error(f"Error API: {response.status_code} — {response.text[:200]}")
                return self._simulate_analysis(title)

            data    = response.json()
            content = data["content"][0]["text"].strip()

            # Parsear JSON de la respuesta
            analysis = json.loads(content)
            analysis["source"]    = "claude_ai"
            analysis["timestamp"] = datetime.now().isoformat()
            analysis["news_title"] = title[:100]

            logger.info(
                f"✅ Análisis Claude: {analysis['primary_direction']} | "
                f"Confianza: {analysis['confidence']} | "
                f"Activos: {analysis['affected_assets']}"
            )
            return analysis

        except json.JSONDecodeError as e:
            logger.error(f"Error parseando respuesta JSON de Claude: {e}")
            return self._simulate_analysis(title)
        except Exception as e:
            logger.error(f"Error llamando a Claude API: {e}")
            return self._simulate_analysis(title)

    def analyze_market_context(
        self,
        symbol:       str,
        current_price: float,
        price_24h_ago: float,
        open_positions: list,
    ) -> Optional[dict]:
        """
        Análisis más profundo: contexto de mercado completo.
        Usar antes de abrir una posición en producción real.
        """
        if not self.enabled:
            return None

        change_pct = ((current_price - price_24h_ago) / price_24h_ago * 100)
        pos_str    = json.dumps(open_positions[:3]) if open_positions else "ninguna"

        prompt = (
            f"Contexto de mercado para tomar decisión de trading:\n\n"
            f"Activo: {symbol}\n"
            f"Precio actual: ${current_price:,.2f}\n"
            f"Cambio 24h: {change_pct:+.2f}%\n"
            f"Posiciones abiertas: {pos_str}\n\n"
            f"¿Es un buen momento para abrir una posición? "
            f"¿Qué riesgos hay ahora mismo en este activo?"
        )

        try:
            import requests
            response = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key":         self.api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type":      "application/json",
                },
                json={
                    "model":      self.model,
                    "max_tokens": 500,
                    "system":     SYSTEM_PROMPT,
                    "messages":   [{"role": "user", "content": prompt}],
                },
                timeout=15,
            )
            data    = response.json()
            content = data["content"][0]["text"].strip()
            return json.loads(content)
        except Exception as e:
            logger.error(f"Error en analyze_market_context: {e}")
            return None

    def _simulate_analysis(self, title: str) -> dict:
        """
        Análisis simulado cuando no hay API key.
        Usa lógica básica de keywords para dar una respuesta razonable.
        Útil para desarrollo y testing sin gastar tokens.
        """
        title_lower = title.lower()

        # Detección básica de activos y dirección
        gold_words = ["gold", "oro", "fed", "inflation", "inflation", "safe haven"]
        oil_words  = ["oil", "opec", "crude", "petroleum", "barrel", "brent", "wti"]
        bull_words = ["surge", "rise", "jump", "rally", "cut", "attack", "conflict",
                      "shortage", "sube", "alza", "conflicto", "recorte"]
        bear_words = ["fall", "drop", "slump", "glut", "surplus", "peace", "deal",
                      "baja", "caída", "acuerdo", "exceso"]

        assets    = []
        if any(w in title_lower for w in gold_words):
            assets.append("GOLD")
        if any(w in title_lower for w in oil_words):
            assets.extend(["CL", "BRENTOIL"])
        if not assets:
            assets = ["GOLD"]

        bull_score = sum(1 for w in bull_words if w in title_lower)
        bear_score = sum(1 for w in bear_words if w in title_lower)

        if bull_score > bear_score:
            direction = "bullish"
            confidence = min(0.4 + bull_score * 0.1, 0.7)
        elif bear_score > bull_score:
            direction = "bearish"
            confidence = min(0.4 + bear_score * 0.1, 0.7)
        else:
            direction  = "neutral"
            confidence = 0.3

        return {
            "affected_assets":     assets,
            "primary_direction":   direction,
            "confidence":          round(confidence, 2),
            "timeframe_hours":     24,
            "reasoning":           f"Análisis simulado (sin API key). Título: {title[:80]}",
            "key_levels_to_watch": "Ver niveles de soporte/resistencia en el gráfico",
            "risk_factors":        "Volatilidad inesperada del mercado",
            "signal_strength":     "moderate" if confidence > 0.5 else "weak",
            "source":              "simulated",
            "timestamp":           datetime.now().isoformat(),
            "news_title":          title[:100],
        }

    def format_analysis_telegram(self, analysis: dict, news_title: str) -> str:
        """Formatea el análisis de Claude para enviar a Telegram."""
        dir_map = {
            "bullish": "📈 ALCISTA",
            "bearish": "📉 BAJISTA",
            "neutral": "➡️ NEUTRAL",
        }
        str_map = {
            "strong":   "🟢 Fuerte",
            "moderate": "🟡 Moderada",
            "weak":     "🔴 Débil",
        }

        src_label = (
            "🤖 Análisis Claude AI"
            if analysis.get("source") == "claude_ai"
            else "🔧 Análisis automático"
        )

        assets_str = " · ".join(analysis.get("affected_assets", []))
        conf_pct   = int(analysis.get("confidence", 0) * 100)
        conf_bar   = "█" * (conf_pct // 20) + "░" * (5 - conf_pct // 20)

        return (
            f"🧠 *{src_label}*\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"📰 _{news_title[:90]}_\n\n"
            f"🎯 *Activos:* {assets_str}\n"
            f"📊 *Dirección:* {dir_map.get(analysis['primary_direction'], '?')}\n"
            f"⚡ *Señal:* {str_map.get(analysis.get('signal_strength', 'weak'), '?')}\n"
            f"💪 *Confianza:* {conf_bar} {conf_pct}%\n"
            f"⏱️ *Horizonte:* {analysis.get('timeframe_hours', 24)}h\n\n"
            f"💡 *Razonamiento:*\n_{analysis.get('reasoning', 'N/A')}_\n\n"
            f"👀 *Niveles clave:* {analysis.get('key_levels_to_watch', 'N/A')}\n"
            f"⚠️ *Riesgo:* {analysis.get('risk_factors', 'N/A')}\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"⏰ {analysis.get('timestamp', '')[:16]}"
        )


# ─────────────────────────────────────────────────────────────────────
# EJECUCIÓN DIRECTA PARA PRUEBA
# ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n" + "="*55)
    print("  YIELD SENTINEL — Claude AI Agent")
    print("="*55 + "\n")

    agent = ClaudeAnalystAgent()
    mode  = "API REAL 🤖" if agent.enabled else "SIMULADO 🔧"
    print(f"Modo: {mode}\n")

    test_news = [
        "OPEC+ agrees to surprise production cut of 500,000 barrels per day",
        "Federal Reserve signals pause in rate hike cycle amid cooling inflation",
        "Middle East tensions escalate as conflict spreads to oil-producing regions",
    ]

    for headline in test_news:
        print(f"📰 {headline}")
        analysis = agent.analyze_news(headline)
        if analysis:
            print(f"   → {analysis['primary_direction'].upper()} | "
                  f"Confianza: {analysis['confidence']*100:.0f}% | "
                  f"Activos: {analysis['affected_assets']}")
            print(f"   → {analysis['reasoning'][:80]}...")
        print()

    print("✅ Claude AI Agent funcionando correctamente\n")
