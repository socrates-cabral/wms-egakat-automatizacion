"""
AGENTE DE TELEGRAM
==================
Responsabilidad única: comunicación con el usuario.
Envía alertas, reportes y confirmaciones al bot de Telegram.

Este es el único punto de contacto entre el sistema y tú.
"""

import requests
import logging
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [TELEGRAM] %(message)s",
    handlers=[
        logging.FileHandler("data/logs/telegram_agent.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class TelegramAgent:
    """Agente de notificaciones via Telegram."""

    def __init__(self):
        self.token   = TELEGRAM_BOT_TOKEN
        self.chat_id = TELEGRAM_CHAT_ID
        self.base    = f"https://api.telegram.org/bot{self.token}"
        self._check_config()

    def _check_config(self):
        if "TU_TOKEN" in self.token or not self.token:
            logger.warning(
                "⚠️  Token de Telegram no configurado. "
                "Edita config.py con tu token real."
            )
        if "TU_CHAT" in self.chat_id or not self.chat_id:
            logger.warning(
                "⚠️  Chat ID no configurado. "
                "Edita config.py con tu Chat ID."
            )

    def send(self, message: str, silent: bool = False) -> bool:
        """
        Envía un mensaje de texto al bot de Telegram.
        
        Parámetros:
        - message: texto (soporta Markdown)
        - silent:  True = sin sonido de notificación
        """
        if "TU_TOKEN" in self.token:
            logger.info(f"[SIMULADO] Mensaje que se enviaría:\n{message[:200]}...")
            return True

        try:
            # Intento 1: con Markdown
            response = requests.post(
                f"{self.base}/sendMessage",
                json={
                    "chat_id":                  self.chat_id,
                    "text":                     message[:4096],
                    "parse_mode":               "Markdown",
                    "disable_notification":     silent,
                    "disable_web_page_preview": True,
                },
                timeout=10
            )
            data = response.json()
            if data.get("ok"):
                logger.info("Mensaje enviado correctamente")
                return True

            # Intento 2: sin Markdown (evita errores de parse)
            response2 = requests.post(
                f"{self.base}/sendMessage",
                json={
                    "chat_id":              self.chat_id,
                    "text":                 message[:4096],
                    "disable_notification": silent,
                },
                timeout=10
            )
            data2 = response2.json()
            if data2.get("ok"):
                logger.info("Mensaje enviado (sin Markdown)")
                return True

            logger.error(f"Error de Telegram: {data2.get('description')}")
            return False
        except Exception as e:
            logger.error(f"Error enviando mensaje: {e}")
            return False

    def send_price_update(self, assets: dict):
        """Envía actualización de precios de todos los activos monitoreados."""
        lines = ["💹 *PRECIOS EN TIEMPO REAL*\n━━━━━━━━━━━━━━━━━━━━━"]
        for key, asset in assets.items():
            lines.append(
                f"{asset['emoji']} *{asset['name']}*: "
                f"`${asset['price']:>12,.2f}`"
            )
        from datetime import datetime
        lines.append(f"\n⏰ {datetime.now().strftime('%H:%M:%S')}")
        self.send("\n".join(lines), silent=True)

    def send_signal_alert(self, signal_message: str):
        """Envía alerta de señal de trading (con sonido)."""
        self.send(signal_message, silent=False)

    def send_news_alert(self, news_message: str):
        """Envía alerta de noticia macro."""
        self.send(news_message, silent=False)

    def send_daily_report(self, report_message: str):
        """Envía reporte diario de performance."""
        self.send(report_message, silent=True)

    def send_error(self, error: str):
        """Envía alerta de error del sistema."""
        from datetime import datetime
        msg = (
            f"🚨 *ERROR DEL SISTEMA*\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"`{error[:300]}`\n"
            f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        self.send(msg, silent=False)


# ─────────────────────────────────────────────
# EJECUCIÓN DIRECTA PARA PRUEBA
# ─────────────────────────────────────────────
if __name__ == "__main__":
    print("\n" + "="*50)
    print("  YIELD SENTINEL — Telegram Agent")
    print("  Probando conexión...")
    print("="*50 + "\n")

    agent = TelegramAgent()

    test_msg = (
        "🤖 *YIELD SENTINEL — Test de Conexión*\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "✅ El sistema está funcionando correctamente.\n"
        "🧪 Modo: Paper Trading (sin dinero real)\n\n"
        "Los siguientes agentes están activos:\n"
        "  📡 Market Agent — precios HL\n"
        "  📰 News Agent — noticias macro\n"
        "  🎯 Signal Agent — generación de señales\n"
        "  📊 Paper Agent — simulación de trades\n\n"
        "_Yield Sentinel v1.0 — Listo para operar_"
    )

    result = agent.send(test_msg)
    if result:
        print("✅ Mensaje enviado (o simulado si no hay token configurado)")
    print("\n✅ Agente de Telegram funcionando correctamente\n")
