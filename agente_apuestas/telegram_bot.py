import sys
sys.stdout.reconfigure(encoding="utf-8")

"""
telegram_bot.py
Módulo de notificaciones Telegram para el Agente de Apuestas.

════════════════════════════════════════════════════════════════
SETUP REQUERIDO (solo la primera vez)
════════════════════════════════════════════════════════════════
1. Crear bot en Telegram:
   - Buscar @BotFather en Telegram
   - Enviar: /newbot
   - Nombre sugerido: Agente Apuestas
   - Username sugerido: agente_apuestas_XXX_bot
   - BotFather entrega un TOKEN

2. Obtener tu CHAT_ID:
   - Abrir el bot → enviar cualquier mensaje
   - Visitar: https://api.telegram.org/bot{TOKEN}/getUpdates
   - Buscar "chat":{"id": XXXXXXX}

3. Agregar al .env:
   TELEGRAM_BOT_TOKEN=xxxxxxxxx:xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   TELEGRAM_CHAT_ID=xxxxxxxxx
════════════════════════════════════════════════════════════════

Funciones:
  enviar_texto()           — mensaje libre al chat
  enviar_recomendacion()   — tarjeta completa de apuesta
  enviar_alerta_permiso()  — solicita SI/NO para montos altos
  esperar_respuesta()      — polling hasta timeout
  enviar_resumen_dia()     — resumen nocturno automático
  enviar_alerta_riesgo()   — alertas críticas del sistema
"""

import os
import time
import requests
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

# ── .env ──────────────────────────────────────────────────────────────────────
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

TELEGRAM_TOKEN   = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
MONTO_AUTONOMO   = int(os.getenv("MONTO_AUTONOMO", "1000"))

_BASE_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

# ── Modo Paper Trading ────────────────────────────────────────────────────────
# Se lee desde config.py (mismo directorio)
try:
    from config import MODO_PAPER_TRADING
except Exception:
    MODO_PAPER_TRADING = True

_PAPER_TAG = "🟡 <b>[PAPER TRADING — apuesta ficticia]</b>\n" if MODO_PAPER_TRADING else ""


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS INTERNOS
# ─────────────────────────────────────────────────────────────────────────────

def _verificar_config() -> bool:
    """Verifica que TOKEN y CHAT_ID estén configurados. Muestra instrucciones si no."""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print()
        print("=" * 60)
        print("TELEGRAM NO CONFIGURADO — Sigue estos pasos:")
        print("=" * 60)
        print()
        print("1. Abrir Telegram → buscar @BotFather")
        print("   Enviar: /newbot")
        print("   Nombre: Agente Apuestas")
        print("   Username: agente_apuestas_XXX_bot")
        print("   BotFather entregará un TOKEN")
        print()
        print("2. Obtener tu CHAT_ID:")
        print("   → Abrir el bot → enviar cualquier mensaje")
        print("   → Visitar: https://api.telegram.org/bot{TOKEN}/getUpdates")
        print("   → Buscar: \"chat\":{\"id\": XXXXXXX}")
        print()
        print("3. Agregar al .env:")
        print("   TELEGRAM_BOT_TOKEN=xxxxxxxxx:xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
        print("   TELEGRAM_CHAT_ID=xxxxxxxxx")
        print("   MONTO_AUTONOMO=1000")
        print("=" * 60)
        print()
        return False
    return True


def _post(endpoint: str, payload: dict, timeout: int = 10) -> dict | None:
    """Envía POST a la API de Telegram. Retorna JSON o None si falla."""
    try:
        r = requests.post(f"{_BASE_URL}/{endpoint}", json=payload, timeout=timeout)
        if r.status_code == 200 and r.json().get("ok"):
            return r.json()
        print(f"  [FALLO] Telegram {endpoint}: HTTP {r.status_code} — {r.text[:200]}")
        return None
    except requests.exceptions.ConnectionError:
        print(f"  [FALLO] Telegram {endpoint}: sin conexión a internet")
        return None
    except Exception as e:
        print(f"  [FALLO] Telegram {endpoint}: {e}")
        return None


def _ts() -> str:
    """Timestamp formateado para mensajes."""
    return datetime.now().strftime("%d/%m/%Y %H:%M")


# ─────────────────────────────────────────────────────────────────────────────
# 1. ENVIAR TEXTO SIMPLE
# ─────────────────────────────────────────────────────────────────────────────

def enviar_texto(mensaje: str) -> bool:
    """
    Envía mensaje de texto simple al chat configurado.

    Args:
        mensaje: texto plano o HTML (acepta <b>, <i>, <code>)

    Returns:
        True si OK, False si falla. El agente NUNCA aborta por este fallo.
    """
    if not _verificar_config():
        return False

    payload = {
        "chat_id":    TELEGRAM_CHAT_ID,
        "text":       mensaje,
        "parse_mode": "HTML",
    }
    resultado = _post("sendMessage", payload)
    if resultado:
        print(f"  [OK] Telegram: mensaje enviado")
        return True
    return False


# ─────────────────────────────────────────────────────────────────────────────
# 2. ENVIAR RECOMENDACIÓN COMPLETA
# ─────────────────────────────────────────────────────────────────────────────

def enviar_recomendacion(partido: dict, apuesta: dict, bankroll: float) -> bool:
    """
    Envía tarjeta formateada con la recomendación completa de apuesta.

    Args:
        partido:  dict del fixture (liga_nombre, fecha, home_nombre, away_nombre, ciudad)
        apuesta:  dict de la recomendación (tipo_apuesta, seleccion, cuota, value,
                  prob_modelo, prob_implicita, consenso_modelos, confianza, monto_kelly,
                  monto_flat, lineup_confirmado, alertas)
        bankroll: bankroll actual en CLP

    Returns:
        True si OK, False si falla.
    """
    if not _verificar_config():
        return False

    liga      = partido.get("liga_nombre", "Liga desconocida")
    fecha_raw = partido.get("fecha", "")
    home      = partido.get("home_nombre", "Local")
    away      = partido.get("away_nombre", "Visita")

    # Formatear fecha/hora legible
    try:
        dt = datetime.fromisoformat(fecha_raw)
        fecha_hora = dt.strftime("%d/%m %H:%M")
    except Exception:
        fecha_hora = fecha_raw[:16] if fecha_raw else "–"

    tipo      = apuesta.get("tipo_apuesta", "")
    seleccion = apuesta.get("seleccion", "")
    cuota     = apuesta.get("cuota", 0)
    value     = apuesta.get("value", 0)
    prob_m    = apuesta.get("prob_modelo", 0)
    prob_i    = apuesta.get("prob_implicita", 0)
    consenso  = apuesta.get("consenso_modelos", 0)
    confianza = apuesta.get("confianza", 0)
    lineup_ok = apuesta.get("lineup_confirmado", False)

    monto_kelly = apuesta.get("monto_kelly", 0)
    monto_flat  = apuesta.get("monto_flat", round(bankroll * 0.03))

    # Detectar fuente de prediccion (Sprint 10: ML vs sistema de reglas)
    fuente_prediccion = apuesta.get("fuente", "reglas")

    # Nombre legible del mercado
    nombres_mercado = {
        "1X2":           "1X2 (Resultado final)",
        "DOUBLE_CHANCE": "Doble Chance",
        "BTTS":          "Ambos Anotan",
        "OVER_UNDER":    "Over/Under",
        "ASIAN_HC":      "Hándicap Asiático",
        "HALF_TIME":     "Resultado 1er tiempo",
        "MONEYLINE":     "Ganador",
        "SPREAD":        "Handicap puntos",
        "TOTAL":         "Total puntos",
    }
    nombre_betano = nombres_mercado.get(tipo, tipo)

    # Bloque de alertas críticas
    alertas = apuesta.get("alertas", [])
    bloque_alertas = ""
    if alertas:
        items = "\n".join(f"⚠️ {a}" for a in alertas)
        bloque_alertas = f"\n{items}\n"

    # Lineup emoji
    lineup_txt = "✅ CONFIRMADO" if lineup_ok else "⏳ PENDIENTE"

    # Bloque consenso multi-LLM (Sprint 11)
    bloque_llm = ""
    if "votos_llm" in apuesta:
        emojis_v = {"CONFIRMAR": "✅", "RECHAZAR": "❌", "NEUTRAL": "⚠️"}
        votos    = apuesta["votos_llm"]
        n_conf   = apuesta.get("consenso_llm", {}).get("confirmaciones", 0)
        estrellas = "★" * n_conf + "☆" * (3 - n_conf)
        bloque_llm = (
            f"\n🧠 <b>CONSENSO IA ({n_conf}/3) {estrellas}</b>\n"
            f"  Claude: {emojis_v.get(votos['claude']['voto'], '⚠️')} "
            f"{votos['claude']['voto']} — {votos['claude']['justificacion']}\n"
            f"  Gemini: {emojis_v.get(votos['gemini']['voto'], '⚠️')} "
            f"{votos['gemini']['voto']} — {votos['gemini']['justificacion']}\n"
            f"  GPT-4:  {emojis_v.get(votos['gpt']['voto'], '⚠️')} "
            f"{votos['gpt']['voto']} — {votos['gpt']['justificacion']}\n"
            f"  <b>Monto ajustado: ${apuesta.get('monto_autonomo', 0):,.0f} CLP "
            f"({apuesta.get('factor_monto', 1):.0%})</b>"
        )

    # Indicador de confianza
    if confianza >= 70:
        conf_emoji = "🟢"
    elif confianza >= 55:
        conf_emoji = "🟡"
    else:
        conf_emoji = "🔴"

    # Header y footer según fuente de prediccion (Sprint 10)
    if fuente_prediccion == "ml_xgboost":
        encabezado = "<b>🤖 PREDICCION ML (XGBoost)</b>"
        footer_extra = (
            f"\n<b>Fuente:</b> Modelo XGBoost | Umbral: 70% | Value min: 10%"
            f"\n<b>Confianza ML:</b> {conf_emoji} {prob_m*100:.1f}%"
        )
    else:
        encabezado = "<b>⚽ APUESTA RECOMENDADA</b>"
        footer_extra = (
            f"\n<b>Score confianza:</b> {conf_emoji} {confianza}/100"
            f"\n<b>Consenso:</b> {consenso}/3 modelos"
        )

    mensaje = (
        f"{_PAPER_TAG}"
        f"{encabezado}\n"
        f"─────────────────────────\n"
        f"<b>{liga}</b> | {fecha_hora}\n"
        f"{home} vs {away}\n"
        f"\n"
        f"<b>Mercado:</b> {nombre_betano}\n"
        f"<b>Selección:</b> <b>{seleccion}</b>\n"
        f"<b>Cuota Betano:</b> {cuota}\n"
        f"<b>Value:</b> +{value*100:.1f}%\n"
        f"\n"
        f"<b>Prob. modelo:</b>   {prob_m*100:.1f}%\n"
        f"<b>Prob. implícita:</b> {prob_i*100:.1f}%\n"
        f"\n"
        f"<b>💰 MONTO SUGERIDO</b>\n"
        f"Kelly: ${monto_kelly:,.0f} CLP\n"
        f"Flat (3%): ${monto_flat:,.0f} CLP\n"
        f"Bankroll actual: ${bankroll:,.0f} CLP\n"
        f"\n"
        f"<b>Lineup:</b> {lineup_txt}"
        f"{footer_extra}"
        f"{bloque_llm}"
        f"{bloque_alertas}\n"
        f"─────────────────────────\n"
        f"Abre Betano → busca este partido y selecciona el mercado indicado."
    )

    resultado = _post("sendMessage", {
        "chat_id":    TELEGRAM_CHAT_ID,
        "text":       mensaje,
        "parse_mode": "HTML",
    })

    if resultado:
        print(f"  [OK] Telegram recomendación: {home} vs {away} — {tipo} {seleccion}")
        return True
    return False


# ─────────────────────────────────────────────────────────────────────────────
# 3. ENVIAR ALERTA DE PERMISO (monto > MONTO_AUTONOMO)
# ─────────────────────────────────────────────────────────────────────────────

def enviar_alerta_permiso(partido: dict, apuesta: dict,
                          monto_kelly: float, limite: float) -> bool:
    """
    Se envía cuando monto_kelly > MONTO_AUTONOMO. Solicita aprobación manual.

    Respuestas válidas: SI | NO | CANCELAR

    Args:
        partido:     dict fixture
        apuesta:     dict recomendación
        monto_kelly: monto calculado por Kelly (supera el límite autónomo)
        limite:      MONTO_AUTONOMO configurado en .env

    Returns:
        True si el mensaje fue enviado, False si falla.
    """
    if not _verificar_config():
        return False

    home      = partido.get("home_nombre", "Local")
    away      = partido.get("away_nombre", "Visita")
    liga      = partido.get("liga_nombre", "")
    tipo      = apuesta.get("tipo_apuesta", "")
    seleccion = apuesta.get("seleccion", "")
    cuota     = apuesta.get("cuota", 0)
    value     = apuesta.get("value", 0)
    confianza = apuesta.get("confianza", 0)

    mensaje = (
        f"{_PAPER_TAG}"
        f"<b>🔔 SOLICITUD DE APROBACIÓN</b>\n"
        f"─────────────────────────\n"
        f"Kelly sugiere <b>${monto_kelly:,.0f} CLP</b>\n"
        f"Supera tu límite autónomo de <b>${limite:,.0f} CLP</b>\n"
        f"\n"
        f"<b>Partido:</b> {home} vs {away}\n"
        f"<b>Liga:</b> {liga}\n"
        f"<b>Mercado:</b> {tipo} → {seleccion}\n"
        f"<b>Cuota:</b> {cuota} | <b>Value:</b> +{value*100:.1f}%\n"
        f"<b>Confianza:</b> {confianza}/100\n"
        f"\n"
        f"<b>Responde a este mensaje:</b>\n"
        f"  <code>SI</code> — aprobar ${monto_kelly:,.0f} CLP\n"
        f"  <code>NO</code> — usar límite de ${limite:,.0f} CLP\n"
        f"  <code>CANCELAR</code> — omitir esta apuesta\n"
        f"\n"
        f"⏱ Tienes 30 minutos para responder."
    )

    resultado = _post("sendMessage", {
        "chat_id":    TELEGRAM_CHAT_ID,
        "text":       mensaje,
        "parse_mode": "HTML",
    })

    if resultado:
        print(f"  [OK] Telegram alerta permiso: Kelly=${monto_kelly:,.0f} > límite=${limite:,.0f}")
        return True
    return False


# ─────────────────────────────────────────────────────────────────────────────
# 4. ESPERAR RESPUESTA (polling /getUpdates)
# ─────────────────────────────────────────────────────────────────────────────

def esperar_respuesta(timeout_minutos: int = 30) -> str:
    """
    Polling del endpoint /getUpdates cada 10 segundos.
    Espera hasta timeout_minutos o hasta recibir una respuesta válida.

    Respuestas aceptadas (case-insensitive, con aliases):
      SI     ← "si", "sí", "s", "yes", "y", "dale", "ok"
      NO     ← "no", "n"
      CANCELAR ← "cancelar", "cancel", "no apostar", "omitir"

    Returns:
        "SI" | "NO" | "CANCELAR" | "TIMEOUT"
    """
    if not _verificar_config():
        return "TIMEOUT"

    ALIASES = {
        "SI":       {"si", "sí", "s", "yes", "y", "dale", "ok", "1"},
        "NO":       {"no", "n", "2"},
        "CANCELAR": {"cancelar", "cancel", "no apostar", "omitir", "skip", "3"},
    }

    timeout_segundos = timeout_minutos * 60
    inicio           = time.time()
    ultimo_update_id = None

    # Obtener el último update_id conocido para ignorar mensajes previos
    try:
        r = requests.get(f"{_BASE_URL}/getUpdates", params={"limit": 1, "offset": -1},
                         timeout=10)
        if r.status_code == 200 and r.json().get("ok"):
            updates = r.json().get("result", [])
            if updates:
                ultimo_update_id = updates[-1]["update_id"]
    except Exception:
        pass

    print(f"  [INFO] Esperando respuesta Telegram (timeout {timeout_minutos}min)...")

    while time.time() - inicio < timeout_segundos:
        time.sleep(10)

        try:
            params = {"timeout": 0, "limit": 5}
            if ultimo_update_id is not None:
                params["offset"] = ultimo_update_id + 1

            r = requests.get(f"{_BASE_URL}/getUpdates", params=params, timeout=15)
            if r.status_code != 200 or not r.json().get("ok"):
                continue

            updates = r.json().get("result", [])
            for upd in updates:
                ultimo_update_id = upd["update_id"]
                msg = upd.get("message", {})

                # Solo procesar mensajes de nuestro chat
                if str(msg.get("chat", {}).get("id", "")) != str(TELEGRAM_CHAT_ID):
                    continue

                texto = (msg.get("text") or "").strip().lower()

                for respuesta, aliases in ALIASES.items():
                    if texto in aliases:
                        print(f"  [OK] Respuesta Telegram recibida: {respuesta}")
                        return respuesta

        except Exception as e:
            print(f"  [INFO] polling error: {e}")

    print(f"  [INFO] Telegram: timeout después de {timeout_minutos} minutos → TIMEOUT")
    return "TIMEOUT"


# ─────────────────────────────────────────────────────────────────────────────
# 5. ENVIAR RESUMEN DEL DÍA
# ─────────────────────────────────────────────────────────────────────────────

def enviar_resumen_dia(stats: dict) -> bool:
    """
    Resumen nocturno automático (llamar desde run_backtesting.py a las 23:00).

    Args:
        stats: dict con las siguientes claves:
          n:           int  — apuestas enviadas hoy
          verificados: int  — resultados verificados
          ganadas:     int
          perdidas:    int
          bankroll_inicio: float  (CLP)
          bankroll_cierre: float  (CLP)
          mejor:       str  — descripción de la mejor apuesta
          peor:        str  — descripción de la peor apuesta
          proximos:    int  — partidos analizados para mañana

    Returns:
        True si OK.
    """
    if not _verificar_config():
        return False

    n        = stats.get("n", 0)
    verif    = stats.get("verificados", 0)
    ganadas  = stats.get("ganadas", 0)
    perdidas = stats.get("perdidas", 0)
    inicio   = stats.get("bankroll_inicio", 0)
    cierre   = stats.get("bankroll_cierre", 0)
    mejor    = stats.get("mejor", "–")
    peor     = stats.get("peor", "–")
    proximos = stats.get("proximos", 0)

    diferencia = cierre - inicio
    pct        = (diferencia / inicio * 100) if inicio else 0
    signo      = "+" if diferencia >= 0 else ""
    emoji_res  = "📈" if diferencia >= 0 else "📉"

    mensaje = (
        f"{_PAPER_TAG}"
        f"<b>{emoji_res} RESUMEN DEL DÍA — {_ts()[:5]}</b>\n"
        f"─────────────────────────\n"
        f"Apuestas enviadas: <b>{n}</b>\n"
        f"Resultados verificados: {verif}\n"
        f"Ganadas: ✅ {ganadas} | Perdidas: ❌ {perdidas}\n"
        f"\n"
        f"Bankroll inicio: ${inicio:,.0f} CLP\n"
        f"Bankroll cierre: ${cierre:,.0f} CLP\n"
        f"Resultado: <b>{signo}{diferencia:,.0f} CLP ({pct:+.1f}%)</b>\n"
        f"\n"
        f"Mejor apuesta: {mejor}\n"
        f"Peor apuesta: {peor}\n"
        f"\n"
        f"Próximos partidos analizados: {proximos}"
    )

    resultado = _post("sendMessage", {
        "chat_id":    TELEGRAM_CHAT_ID,
        "text":       mensaje,
        "parse_mode": "HTML",
    })

    if resultado:
        print(f"  [OK] Telegram resumen día enviado")
        return True
    return False


# ─────────────────────────────────────────────────────────────────────────────
# 6. ENVIAR ALERTA DE RIESGO (alertas críticas del sistema)
# ─────────────────────────────────────────────────────────────────────────────

def enviar_alerta_riesgo(tipo: str, detalle: str) -> bool:
    """
    Alertas críticas del sistema:
      - Stop-loss activado
      - Lineup cambiado 1h antes del partido
      - API sin cuota disponible
      - Error en módulo
      - Bloqueo semanal activo

    Args:
        tipo:   etiqueta de la alerta (STOP_LOSS | LINEUP_CAMBIO | SIN_CUOTA | ERROR_MODULO)
        detalle: descripción del problema

    Returns:
        True si OK.
    """
    if not _verificar_config():
        return False

    emoji_map = {
        "STOP_LOSS":     "🛑",
        "LINEUP_CAMBIO": "📋",
        "SIN_CUOTA":     "⏸️",
        "ERROR_MODULO":  "⚠️",
        "BLOQUEO":       "🔒",
    }
    emoji = emoji_map.get(tipo, "⚠️")

    mensaje = (
        f"<b>{emoji} ALERTA {tipo}</b>\n"
        f"─────────────────────────\n"
        f"{detalle}\n"
        f"\n"
        f"<i>{_ts()}</i>"
    )

    resultado = _post("sendMessage", {
        "chat_id":    TELEGRAM_CHAT_ID,
        "text":       mensaje,
        "parse_mode": "HTML",
    })

    if resultado:
        print(f"  [OK] Telegram alerta_riesgo: {tipo}")
        return True
    return False


# ─────────────────────────────────────────────────────────────────────────────
# TEST
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("TEST — telegram_bot.py")
    print("=" * 60)
    print()

    if not _verificar_config():
        print("Configura el .env antes de testear.")
        sys.exit(0)

    print("Enviando mensaje de prueba...")
    ok = enviar_texto(
        "🤖 <b>Test conexión Telegram — Agente Apuestas OK</b>\n"
        f"<i>{_ts()}</i>"
    )

    if ok:
        print()
        print("✅ Telegram configurado correctamente.")
        print("   El agente enviará notificaciones a este chat.")
    else:
        print()
        print("❌ Fallo al enviar. Verifica TELEGRAM_BOT_TOKEN y TELEGRAM_CHAT_ID en .env")
