"""
mirofish_bridge.py
Integración asíncrona entre Agente Apuestas y MiroFish.

Flujo:
  1. Genera documento TXT con datos del partido
  2. Llama MiroFish API: ontology → build → create → prepare → start
  3. Guarda tracking en mirofish_tracking.json
  4. Monitor en segundo plano: poll run-status → interview/all → Telegram

Uso desde run_agent.py:
    from mirofish_bridge import lanzar_simulacion_async
    lanzar_simulacion_async(partido, prob_xgboost=0.71, cuota=2.10)
"""

import json
import logging
import re
import threading
import time
from datetime import datetime
from pathlib import Path

import requests

log = logging.getLogger(__name__)

# ── Configuración ─────────────────────────────────────────────────────────────
MIROFISH_BASE = "http://localhost:5001/api"
TRACKING_PATH = Path(__file__).parent / "mirofish_tracking.json"
POLL_INTERVAL = 30        # segundos entre polls de run-status
POLL_TIMEOUT  = 3600      # timeout máximo (1 hora)
PROB_PESO_XGBOOST  = 0.6
PROB_PESO_MIROFISH = 0.4

# ── Telegram (reutiliza telegram_bot del agente) ───────────────────────────────
try:
    from telegram_bot import enviar_texto
    TELEGRAM_OK = True
except ImportError:
    TELEGRAM_OK = False
    def enviar_texto(msg):
        log.info(f"[TELEGRAM MOCK] {msg}")


# ─────────────────────────────────────────────────────────────────────────────
# TRACKING
# ─────────────────────────────────────────────────────────────────────────────

def _leer_tracking() -> list:
    if TRACKING_PATH.exists():
        try:
            return json.loads(TRACKING_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


def _guardar_tracking(registros: list):
    TRACKING_PATH.write_text(
        json.dumps(registros, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def _upsert_tracking(sim_id: str, datos: dict):
    registros = _leer_tracking()
    for r in registros:
        if r.get("sim_id") == sim_id:
            r.update(datos)
            _guardar_tracking(registros)
            return
    registros.append({"sim_id": sim_id, **datos})
    _guardar_tracking(registros)


# ─────────────────────────────────────────────────────────────────────────────
# DOCUMENTO DEL PARTIDO
# ─────────────────────────────────────────────────────────────────────────────

def crear_documento_partido(partido: dict, prob_xgboost: float, cuota: float) -> str:
    """Genera texto con datos del partido para alimentar a MiroFish."""
    local    = partido.get("equipo_local", partido.get("home_team", "Local"))
    visitante = partido.get("equipo_visitante", partido.get("away_team", "Visitante"))
    liga     = partido.get("liga", partido.get("league", "Liga"))
    fecha    = partido.get("fecha", datetime.now().strftime("%Y-%m-%d"))

    forma_local     = partido.get("forma_local", "N/A")
    forma_visitante = partido.get("forma_visitante", "N/A")
    goles_local_f   = partido.get("goles_local_favor", "N/A")
    goles_local_c   = partido.get("goles_local_contra", "N/A")
    goles_vis_f     = partido.get("goles_visitante_favor", "N/A")
    goles_vis_c     = partido.get("goles_visitante_contra", "N/A")
    h2h             = partido.get("h2h_resumen", "Sin datos H2H disponibles")
    lesiones        = partido.get("lesiones", "Sin información de lesiones")

    cuota_local   = cuota
    cuota_empate  = partido.get("cuota_empate", "N/A")
    cuota_visita  = partido.get("cuota_visitante", "N/A")

    return f"""{local} vs {visitante} — {liga} {fecha}

{local.upper()} (LOCAL)
Forma reciente: {forma_local}
Goles a favor: {goles_local_f} | Goles en contra: {goles_local_c}

{visitante.upper()} (VISITANTE)
Forma reciente: {forma_visitante}
Goles a favor: {goles_vis_f} | Goles en contra: {goles_vis_c}

HISTORIAL H2H
{h2h}

LESIONES Y BAJAS
{lesiones}

PREDICCIÓN XGBOOST
Probabilidad victoria {local}: {prob_xgboost:.1%}

CUOTAS
{local}: {cuota_local} | Empate: {cuota_empate} | {visitante}: {cuota_visita}

CONTEXTO
Partido de {liga}. Análisis de valor betting a cuota {cuota_local}.
"""


# ─────────────────────────────────────────────────────────────────────────────
# PIPELINE MIROFISH (llamadas HTTP)
# ─────────────────────────────────────────────────────────────────────────────

def _post(endpoint: str, **kwargs) -> dict:
    resp = requests.post(f"{MIROFISH_BASE}{endpoint}", timeout=60, **kwargs)
    resp.raise_for_status()
    data = resp.json()
    if not data.get("success"):
        raise RuntimeError(f"MiroFish error en {endpoint}: {data.get('error')}")
    return data["data"]


def _get(endpoint: str) -> dict:
    resp = requests.get(f"{MIROFISH_BASE}{endpoint}", timeout=30)
    resp.raise_for_status()
    return resp.json()


def _poll_task(task_id: str, campo_resultado: str, timeout: int = 300) -> str:
    """Espera a que una task asíncrona de MiroFish complete y retorna el campo resultado."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        data = _get(f"/graph/task/{task_id}")
        status = data.get("data", {}).get("status") or data.get("status")
        if status == "completed":
            return data.get("data", {}).get(campo_resultado) or data.get(campo_resultado)
        if status == "failed":
            raise RuntimeError(f"Task {task_id} falló: {data}")
        time.sleep(10)
    raise TimeoutError(f"Task {task_id} no completó en {timeout}s")


def _poll_prepare(sim_id: str, task_id: str, timeout: int = 600) -> None:
    """Espera a que el prepare de la simulación complete."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        data = _post(
            "/simulation/prepare/status",
            json={"task_id": task_id, "simulation_id": sim_id}
        )
        status = data.get("status")
        if status in ("completed", "ready"):
            return
        if status == "failed":
            raise RuntimeError(f"Prepare falló: {data}")
        prog = data.get("progress", "?")
        log.info(f"  [MIROFISH] Prepare {sim_id}: {status} {prog}%")
        time.sleep(15)
    raise TimeoutError(f"Prepare {sim_id} no completó en {timeout}s")


def _poll_run_status(sim_id: str, timeout: int = POLL_TIMEOUT) -> None:
    """Espera a que la simulación termine."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        data = _get(f"/simulation/{sim_id}/run-status")
        status = (data.get("data") or data).get("status")
        if status == "completed":
            return
        if status == "error":
            raise RuntimeError(f"Simulación {sim_id} terminó con error")
        log.info(f"  [MIROFISH] Simulación {sim_id}: {status}")
        time.sleep(POLL_INTERVAL)
    raise TimeoutError(f"Simulación {sim_id} no completó en {timeout}s")


def _extraer_prob_de_respuestas(resultados: dict, equipo_local: str) -> float:
    """
    Parsea las respuestas de interview/all y extrae probabilidad media.
    Pide un número 0-100 → divide entre 100.
    """
    numeros = []
    for key, val in resultados.items():
        respuesta = val.get("response", "") if isinstance(val, dict) else str(val)
        # Buscar primer número entero o decimal en la respuesta
        match = re.search(r'\b(\d{1,3}(?:\.\d+)?)\b', respuesta)
        if match:
            n = float(match.group(1))
            if 0 <= n <= 100:
                numeros.append(n / 100.0)

    if not numeros:
        log.warning("[MIROFISH] No se extrajeron probabilidades de las respuestas")
        return 0.5  # neutral si no hay datos

    prob = sum(numeros) / len(numeros)
    log.info(f"  [MIROFISH] {len(numeros)} agentes respondieron → prob_mirofish={prob:.2%}")
    return prob


# ─────────────────────────────────────────────────────────────────────────────
# PIPELINE COMPLETO (corre en thread)
# ─────────────────────────────────────────────────────────────────────────────

def _pipeline(partido: dict, prob_xgboost: float, cuota: float):
    local     = partido.get("equipo_local", partido.get("home_team", "Local"))
    visitante = partido.get("equipo_visitante", partido.get("away_team", "Visitante"))
    nombre    = f"{local} vs {visitante}"

    try:
        log.info(f"[MIROFISH] Iniciando pipeline para {nombre}")

        # 1. Ontology generate
        documento = crear_documento_partido(partido, prob_xgboost, cuota)
        prompt    = (
            f"Analiza el partido {nombre}. ¿Cuál es la probabilidad de victoria de {local}? "
            f"¿Es valor la apuesta a cuota {cuota:.2f}?"
        )
        files = [("files", (f"{nombre.replace(' ', '_')}.txt", documento.encode(), "text/plain"))]
        data1 = _post("/graph/ontology/generate",
                      files=files,
                      data={"simulation_requirement": prompt})
        project_id = data1["project_id"]
        log.info(f"  [MIROFISH] Ontología generada. project_id={project_id}")

        # 2. Build graph
        data2    = _post("/graph/build", json={"project_id": project_id})
        task_id  = data2["task_id"]
        graph_id = _poll_task(task_id, "graph_id", timeout=300)
        log.info(f"  [MIROFISH] Grafo construido. graph_id={graph_id}")

        # 3. Create simulation
        data3  = _post("/simulation/create",
                       json={"project_id": project_id, "graph_id": graph_id})
        sim_id = data3["simulation_id"]
        log.info(f"  [MIROFISH] Simulación creada. sim_id={sim_id}")

        _upsert_tracking(sim_id, {
            "partido": nombre,
            "liga": partido.get("liga", ""),
            "prob_xgboost": prob_xgboost,
            "cuota": cuota,
            "iniciado_at": datetime.now().isoformat(),
            "status": "preparing",
            "prob_mirofish": None,
            "prob_final": None,
        })

        # 4. Prepare
        data4      = _post("/simulation/prepare", json={"simulation_id": sim_id})
        prep_task  = data4.get("task_id")
        if prep_task:
            _poll_prepare(sim_id, prep_task, timeout=600)
        log.info(f"  [MIROFISH] Agentes preparados para {sim_id}")

        # 5. Start
        _post("/simulation/start",
              json={"simulation_id": sim_id, "platform": "parallel"})
        log.info(f"  [MIROFISH] Simulación iniciada: {sim_id}")
        _upsert_tracking(sim_id, {"status": "running"})

        # 6. Poll run-status
        _poll_run_status(sim_id)
        log.info(f"  [MIROFISH] Simulación completada: {sim_id}")

        # 7. Interview all
        pregunta = (
            f"En una escala del 0 al 100, ¿cuál es la probabilidad de que {local} "
            f"gane este partido? Responde solo con un número entero."
        )
        data7 = _post("/simulation/interview/all",
                      json={"simulation_id": sim_id, "prompt": pregunta})
        resultados = data7.get("result", {}).get("results", {})

        # 8. Calcular probabilidades
        prob_mirofish = _extraer_prob_de_respuestas(resultados, local)
        prob_final    = (prob_xgboost * PROB_PESO_XGBOOST) + (prob_mirofish * PROB_PESO_MIROFISH)

        _upsert_tracking(sim_id, {
            "status": "completed",
            "prob_mirofish": round(prob_mirofish, 4),
            "prob_final": round(prob_final, 4),
            "completado_at": datetime.now().isoformat(),
        })

        log.info(
            f"[MIROFISH] {nombre} — "
            f"XGBoost={prob_xgboost:.1%} | MiroFish={prob_mirofish:.1%} | Final={prob_final:.1%}"
        )

        # 9. Telegram
        diferencia = prob_final - prob_xgboost
        icono = "✅" if abs(diferencia) < 0.05 else ("⬆️" if diferencia > 0 else "⬇️")
        msg = (
            f"🐟 <b>MiroFish — {nombre}</b>\n\n"
            f"📊 XGBoost: <b>{prob_xgboost:.1%}</b>\n"
            f"🤖 MiroFish: <b>{prob_mirofish:.1%}</b>\n"
            f"🎯 Prob. final: <b>{prob_final:.1%}</b> {icono}\n"
            f"💰 Cuota analizada: <b>{cuota:.2f}</b>\n\n"
        )

        if prob_final >= 0.65 and (prob_final * cuota) > 1.0:
            msg += "✅ <b>CONFIRMADO — Apuesta válida</b>"
        elif prob_final < 0.50:
            msg += "🔴 <b>DESCARTADO — MiroFish discrepa significativamente</b>"
        else:
            msg += "⚠️ <b>DUDOSO — Considerar stake reducido (-50%)</b>"

        enviar_texto(msg)

    except Exception as e:
        log.error(f"[MIROFISH] Error en pipeline para {nombre}: {e}", exc_info=True)
        _upsert_tracking(nombre, {"status": "error", "error": str(e)})
        enviar_texto(f"🐟 <b>MiroFish Error</b>\n{nombre}: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# PUNTO DE ENTRADA PÚBLICO
# ─────────────────────────────────────────────────────────────────────────────

def lanzar_simulacion_async(partido: dict, prob_xgboost: float, cuota: float) -> None:
    """
    Lanza el pipeline MiroFish en un thread de fondo.
    No bloquea el agente principal.

    Args:
        partido:      dict del partido con keys equipo_local, equipo_visitante, liga, etc.
        prob_xgboost: probabilidad de victoria local según XGBoost (0.0-1.0)
        cuota:        cuota Betano para victoria local
    """
    t = threading.Thread(
        target=_pipeline,
        args=(partido, prob_xgboost, cuota),
        daemon=True,
        name=f"mirofish-{partido.get('equipo_local', 'match')}",
    )
    t.start()
    local = partido.get("equipo_local", partido.get("home_team", ""))
    visit = partido.get("equipo_visitante", partido.get("away_team", ""))
    log.info(f"[MIROFISH] Pipeline lanzado en background para {local} vs {visit}")
