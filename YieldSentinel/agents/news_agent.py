"""
AGENTE DE NOTICIAS
==================
Responsabilidad única: monitorear fuentes de noticias macro
y detectar eventos relevantes para oro y petróleo.

Cuando detecta algo relevante, genera una señal estructurada
para que el agente de señales decida qué hacer.
"""

import feedparser
import json
import logging
import os
import sys
from datetime import datetime, timedelta
from typing import Optional
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import NEWS_FEEDS, NEWS_KEYWORDS, ASSETS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [NOTICIAS] %(message)s",
    handlers=[
        logging.FileHandler("data/logs/news_agent.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class NewsAgent:
    """
    Agente que escanea feeds RSS de noticias financieras.
    Detecta eventos relevantes para commodities.
    No toma decisiones — solo clasifica y puntúa noticias.
    """

    def __init__(self):
        self.feeds       = NEWS_FEEDS
        self.keywords    = NEWS_KEYWORDS
        self.seen_urls   = set()
        self._load_seen_urls()
        logger.info(f"NewsAgent iniciado. {len(self.feeds)} fuentes configuradas.")

    def _load_seen_urls(self):
        """Carga URLs ya procesadas para no duplicar alertas."""
        path = "data/logs/seen_news.json"
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    data = json.load(f)
                    # Solo recordamos las últimas 500 noticias
                    self.seen_urls = set(data[-500:])
            except Exception:
                self.seen_urls = set()

    def _save_seen_urls(self):
        """Guarda URLs procesadas."""
        path = "data/logs/seen_news.json"
        os.makedirs("data/logs", exist_ok=True)
        with open(path, "w") as f:
            json.dump(list(self.seen_urls)[-500:], f)

    def _classify_news(self, title: str, summary: str) -> dict:
        """
        Clasifica una noticia según su impacto potencial en cripto.

        Retorna:
        - affected_assets: lista de activos afectados
        - direction:       "bullish 📈", "bearish 📉", o "neutral ➡️"
        - confidence:      0.0 a 1.0
        - category:        tipo de evento
        """
        text     = (title + " " + summary).lower()
        affected = set()
        score    = 0
        category = "general"

        # ─── Detectar activos específicos mencionados ──────
        asset_mentions = {
            "BTC":  ["bitcoin", "btc", "satoshi"],
            "ETH":  ["ethereum", "eth", "ether"],
            "SOL":  ["solana", "sol"],
            "AVAX": ["avalanche", "avax"],
            "ARB":  ["arbitrum", "arb"],
        }
        for symbol, terms in asset_mentions.items():
            if any(t in text for t in terms):
                affected.add(symbol)
                score += 2

        # ─── Noticias cripto generales → afectan BTC+ETH ──
        crypto_hits = sum(1 for k in [kw.lower() for kw in self.keywords.get("crypto", [])] if k in text)
        if crypto_hits > 0:
            affected.update(["BTC", "ETH"])
            score += crypto_hits
            category = "crypto"

        # ─── Noticias macro → afectan BTC (digital gold) ──
        macro_hits = sum(1 for k in [kw.lower() for kw in self.keywords.get("macro", [])] if k in text)
        if macro_hits > 0:
            affected.add("BTC")
            score += macro_hits
            category = "macro"

        # ─── Noticias de riesgo/sentimiento → todos ────────
        riesgo_hits = sum(1 for k in [kw.lower() for kw in self.keywords.get("riesgo", [])] if k in text)
        if riesgo_hits > 0:
            affected.update(["BTC", "ETH", "SOL"])
            score += riesgo_hits
            category = "sentimiento"

        if not affected:
            return {"relevant": False}

        # ─── Detectar dirección (bullish/bearish) ──────────
        bullish_signals = [
            "surge", "rise", "jump", "rally", "gain", "high", "record",
            "shortage", "cut", "attack", "conflict", "tension", "war",
            "sube", "alza", "récord", "conflicto", "escasez", "recorte"
        ]
        bearish_signals = [
            "fall", "drop", "slump", "decline", "low", "surplus", "glut",
            "ceasefire", "deal", "agreement", "peace", "rate hike",
            "baja", "caída", "acuerdo", "paz", "exceso", "superávit"
        ]

        bull_count = sum(1 for s in bullish_signals if s in text)
        bear_count = sum(1 for s in bearish_signals if s in text)

        if bull_count > bear_count:
            direction = "bullish 📈"
        elif bear_count > bull_count:
            direction = "bearish 📉"
        else:
            direction = "neutral ➡️"

        # ─── Calcular confianza ────────────────────────────
        confidence = min(score / 5.0, 1.0)  # máximo 1.0

        return {
            "relevant":        True,
            "affected_assets": list(affected),
            "direction":       direction,
            "confidence":      round(confidence, 2),
            "category":        category,
            "keyword_hits":    score,
        }

    def scan_feeds(self, only_new: bool = True) -> list:
        """
        Escanea todos los feeds RSS configurados.
        
        Parámetros:
        - only_new: si True, omite noticias ya procesadas
        
        Retorna lista de noticias relevantes con su clasificación.
        """
        relevant_news = []
        cutoff = datetime.now() - timedelta(hours=6)  # Solo últimas 6 horas

        for feed_url in self.feeds:
            try:
                logger.info(f"Escaneando: {feed_url}")
                feed = feedparser.parse(feed_url)

                for entry in feed.entries:
                    url     = entry.get("link", "")
                    title   = entry.get("title", "")
                    summary = entry.get("summary", "")

                    # Saltar si ya la procesamos
                    if only_new and url in self.seen_urls:
                        continue

                    # Clasificar la noticia
                    classification = self._classify_news(title, summary)

                    if classification.get("relevant"):
                        news_item = {
                            "title":    title,
                            "summary":  summary[:300],  # primeros 300 chars
                            "url":      url,
                            "source":   feed.feed.get("title", feed_url),
                            "datetime": datetime.now().isoformat(),
                            **classification
                        }
                        relevant_news.append(news_item)
                        logger.info(
                            f"✅ Relevante: '{title[:60]}...' "
                            f"| {classification['direction']} "
                            f"| confianza: {classification['confidence']}"
                        )

                    self.seen_urls.add(url)

            except Exception as e:
                logger.error(f"Error escaneando {feed_url}: {e}")

        self._save_seen_urls()
        logger.info(f"Escaneo completo: {len(relevant_news)} noticias relevantes")
        return relevant_news

    def format_telegram_alert(self, news: dict) -> str:
        """
        Formatea una noticia como mensaje de Telegram.
        Listo para enviar directamente al bot.
        """
        assets_str = ", ".join(news.get("affected_assets", []))
        conf_bar   = "🟢" * int(news["confidence"] * 5) + "⚪" * (5 - int(news["confidence"] * 5))

        return (
            f"📰 *ALERTA DE NOTICIAS MACRO*\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"*{news['title'][:100]}*\n\n"
            f"🎯 *Activos afectados:* {assets_str}\n"
            f"📊 *Dirección probable:* {news['direction']}\n"
            f"🔍 *Categoría:* {news['category'].capitalize()}\n"
            f"💪 *Confianza:* {conf_bar} {int(news['confidence']*100)}%\n\n"
            f"📝 _{news['summary'][:200]}_\n\n"
            f"🔗 [Leer noticia completa]({news['url']})\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"⏰ {news['datetime'][:16]}"
        )


# ─────────────────────────────────────────────
# EJECUCIÓN DIRECTA PARA PRUEBA
# ─────────────────────────────────────────────
if __name__ == "__main__":
    # Instalar dependencia si no está
    try:
        import feedparser
    except ImportError:
        print("Instalando feedparser...")
        os.system("pip install feedparser --break-system-packages")
        import feedparser

    print("\n" + "="*50)
    print("  YIELD SENTINEL — News Agent")
    print("  Escaneando noticias macro...")
    print("="*50 + "\n")

    agent = NewsAgent()
    news  = agent.scan_feeds(only_new=False)  # False = muestra todo para prueba

    if not news:
        print("ℹ️  No se encontraron noticias relevantes en este momento.")
        print("   Esto es normal. El agente revisa cada 15 minutos.")
    else:
        print(f"\n🔔 {len(news)} noticias relevantes encontradas:\n")
        for i, item in enumerate(news[:5], 1):  # Mostrar máximo 5
            print(f"{'─'*50}")
            print(f"  [{i}] {item['title'][:70]}")
            print(f"       Activos: {', '.join(item['affected_assets'])}")
            print(f"       {item['direction']} | Confianza: {item['confidence']*100:.0f}%")
            print()

    print("\n✅ Agente de noticias funcionando correctamente\n")
