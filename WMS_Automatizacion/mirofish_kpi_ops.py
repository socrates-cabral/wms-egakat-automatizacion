"""
mirofish_kpi_ops.py
Análisis semanal de KPIs operativos Egakat via simulación MiroFish.

200 agentes (Jefe de Ops, analistas de cliente, supervisores, etc.) debaten
el reporte semanal y generan hipótesis de riesgo rankeadas por consenso.

Uso:
    py WMS_Automatizacion/mirofish_kpi_ops.py               # JSON más reciente
    py WMS_Automatizacion/mirofish_kpi_ops.py --json logs/resumen_kpi_ops_20260525.json

Requiere:
    - MiroFish corriendo en localhost:5001  (cd MiroFish && npm run dev)
    - .env con TELEGRAM_BOT_TOKEN y TELEGRAM_CHAT_ID
"""

import sys
import os
import re
import json
import time
import argparse
import requests
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR      = Path(__file__).parent
CLAUDEWORK    = BASE_DIR.parent
LOGS_DIR      = CLAUDEWORK / "logs"
MIROFISH_BASE = "http://localhost:5001/api"
POLL_INTERVAL = 20   # seg entre polls
POLL_TIMEOUT  = 3600 # máximo 1 hora

# ── .env ───────────────────────────────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv(CLAUDEWORK / ".env")
except ImportError:
    pass

TELEGRAM_TOKEN   = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")


def _log(msg: str):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [MIROFISH-KPI] {msg}", flush=True)


# ── TELEGRAM ───────────────────────────────────────────────────────────────────

def _telegram(msg: str):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        _log(f"[TELEGRAM MOCK] {msg[:120]}")
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"},
            timeout=15,
        )
    except Exception as e:
        _log(f"Telegram error: {e}")


# ── LEER JSON KPI ─────────────────────────────────────────────────────────────

def _json_mas_reciente() -> Path | None:
    jsons = sorted(LOGS_DIR.glob("resumen_kpi_ops_*.json"), reverse=True)
    return jsons[0] if jsons else None


def _cargar_kpi(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ── CONSTRUIR DOCUMENTO ───────────────────────────────────────────────────────

def _fmt_pct(val) -> str:
    if val is None:
        return "N/D"
    return f"{val:.1f}%"


def construir_documento_kpi(kpi: dict) -> tuple[str, str]:
    """
    Convierte el JSON KPI en texto estructurado para MiroFish.
    Retorna (documento_txt, titulo_simulacion).
    """
    fecha_gen = kpi.get("fecha_generacion", "")
    nnss      = kpi.get("nnss", {})
    prod      = kpi.get("productividad", {})
    inv       = kpi.get("inventario", {})
    alertas   = kpi.get("alertas", [])
    recs      = kpi.get("recomendaciones", [])
    periodo   = nnss.get("periodo", {})
    anio      = periodo.get("anio", "")
    mes       = periodo.get("mes", "")
    MESES = {1:"Enero",2:"Febrero",3:"Marzo",4:"Abril",5:"Mayo",6:"Junio",
             7:"Julio",8:"Agosto",9:"Septiembre",10:"Octubre",11:"Noviembre",12:"Diciembre"}
    mes_nombre = MESES.get(mes, str(mes))
    titulo     = f"KPI Operativo Egakat — {mes_nombre} {anio}"

    # OTIF global
    otif     = nnss.get("otif", {})
    fillrate = nnss.get("fillrate", {})
    pend     = nnss.get("pendientes", {})

    lineas_otif = [
        f"  OTIF global:   {_fmt_pct(otif.get('pct_otif'))} ({otif.get('pedidos_evaluados',0)} pedidos)",
        f"  On Time:       {_fmt_pct(otif.get('pct_on_time'))}",
        f"  In Full:       {_fmt_pct(otif.get('pct_in_full'))}",
        f"  Fill Rate prom: {_fmt_pct(fillrate.get('promedio_fr'))}",
    ]

    # OTIF por cliente (solo con data)
    clientes_otif = [
        c for c in (otif.get("por_cliente") or [])
        if c.get("pedidos_evaluados", 0) > 0
    ]
    clientes_otif_txt = "\n".join(
        f"  {c['cliente']:25s}  OTIF={_fmt_pct(c.get('pct_otif'))}  "
        f"OT={_fmt_pct(c.get('pct_on_time'))}  IF={_fmt_pct(c.get('pct_in_full'))}  "
        f"({c['pedidos_evaluados']} ped)"
        for c in sorted(clientes_otif, key=lambda x: x.get("pct_otif") or 100)
    ) or "  Sin datos"

    # FillRate por cliente (solo evaluables)
    fr_clientes = [
        c for c in (fillrate.get("por_cliente") or [])
        if c.get("tiene_datos_evaluables")
    ]
    fr_clientes_txt = "\n".join(
        f"  {c['cliente']:25s}  FR={_fmt_pct(c.get('promedio_fr'))}  ({c.get('lineas',0)} líneas)"
        for c in sorted(fr_clientes, key=lambda x: x.get("promedio_fr") or 100)
    ) or "  Sin datos"

    # Pedidos pendientes
    pend_txt = (
        f"  Total pendientes: {pend.get('total_pedidos',0)} pedidos "
        f"/ {pend.get('total_unidades',0)} unidades\n"
    )
    if pend.get("mayores_7_dias"):
        atrasados = pend["mayores_7_dias"][:5]
        pend_txt += f"  ⚠ ATRASADOS >7 días ({len(pend.get('mayores_7_dias',0))} total):\n"
        for p in atrasados:
            pend_txt += f"    - {p['cliente']} | Pedido {p['nro_pedido']} | {p['dias_abierto']} días | {p['unidades']} uds\n"

    # Productividad global
    glb = prod.get("global", {})
    prod_txt = (
        f"  Líneas procesadas:  {glb.get('lineas',0):,}\n"
        f"  Unidades:           {glb.get('unidades',0):,.0f}\n"
        f"  Pedidos:            {glb.get('pedidos',0):,}\n"
        f"  Días trabajados:    {glb.get('dias_trabajados',0)}\n"
        f"  Prod. líneas/día:   {glb.get('productividad_lineas_dia',0):,.1f}\n"
        f"  Prod. uds/hora:     {glb.get('productividad_unidades_hora',0):,.1f}\n"
    )

    # Productividad por cliente (top 5)
    prod_clientes = sorted(
        (prod.get("por_cliente") or []),
        key=lambda x: x.get("lineas", 0),
        reverse=True
    )[:7]
    prod_cli_txt = "\n".join(
        f"  {c.get('cliente','?'):25s}  {c.get('lineas',0):6,} líneas  {c.get('unidades',0):8,.0f} uds"
        for c in prod_clientes
    ) or "  Sin datos"

    # Inventario
    stock    = inv.get("stock", {})
    staging  = inv.get("staging", {})
    inv_txt  = (
        f"  Stock total:       {stock.get('total_skus',stock.get('total_posiciones','N/D'))} posiciones\n"
        f"  Stock bloqueado:   {inv.get('stock_bloqueado_wms', {}).get('total_skus','N/D')}\n"
        f"  Staging pendiente: {staging.get('total_documentos','N/D')} documentos\n"
    )

    # Alertas y recomendaciones
    alertas_txt = "\n".join(f"  ⚠ {a}" for a in alertas[:8]) or "  Sin alertas críticas"
    recs_txt    = "\n".join(f"  → {r}" for r in recs[:6]) or "  Sin recomendaciones"

    doc = f"""REPORTE KPI OPERATIVO — EGAKAT SPA (3PL CHILE)
Período: {mes_nombre} {anio}  |  Generado: {fecha_gen}

═══════════════════════════════════════════════════
INDICADORES PRINCIPALES (NNSS)
═══════════════════════════════════════════════════
{chr(10).join(lineas_otif)}

OTIF POR CLIENTE:
{clientes_otif_txt}

FILL RATE POR CLIENTE:
{fr_clientes_txt}

PEDIDOS PENDIENTES:
{pend_txt}
═══════════════════════════════════════════════════
PRODUCTIVIDAD OPERACIONAL
═══════════════════════════════════════════════════
{prod_txt}
TOP CLIENTES POR VOLUMEN:
{prod_cli_txt}

═══════════════════════════════════════════════════
INVENTARIO / STOCK
═══════════════════════════════════════════════════
{inv_txt}
═══════════════════════════════════════════════════
ALERTAS DEL SISTEMA
═══════════════════════════════════════════════════
{alertas_txt}

RECOMENDACIONES AUTOMÁTICAS:
{recs_txt}

═══════════════════════════════════════════════════
CONTEXTO EGAKAT SPA
═══════════════════════════════════════════════════
Egakat SPA es un 3PL (Third Party Logistics) chileno con dos centros de
distribución: Pudahuel y Quilicura. Opera para 14+ clientes incluyendo
DERCO (automotriz), Mascotas Latinas, Barentz, Daikin, Pochteca, entre otros.
KPIs principales: OTIF (On-Time In-Full), Fill Rate, Productividad por CD.
Objetivo OTIF: ≥95%. Objetivo Fill Rate: ≥99%.
"""
    return doc, titulo


# ── MIROFISH API ──────────────────────────────────────────────────────────────

def _post(endpoint: str, **kwargs) -> dict:
    resp = requests.post(f"{MIROFISH_BASE}{endpoint}", timeout=90, **kwargs)
    resp.raise_for_status()
    data = resp.json()
    if not data.get("success"):
        raise RuntimeError(f"MiroFish error en {endpoint}: {data.get('error','')}")
    return data["data"]


def _get(endpoint: str) -> dict:
    resp = requests.get(f"{MIROFISH_BASE}{endpoint}", timeout=30)
    resp.raise_for_status()
    return resp.json()


def _poll_task(task_id: str, campo: str, timeout: int = 300) -> str:
    deadline = time.time() + timeout
    while time.time() < deadline:
        data = _get(f"/graph/task/{task_id}")
        status = (data.get("data") or data).get("status")
        if status == "completed":
            return (data.get("data") or data).get(campo)
        if status == "failed":
            raise RuntimeError(f"Task {task_id} falló")
        time.sleep(10)
    raise TimeoutError(f"Task {task_id} no completó en {timeout}s")


def _poll_prepare(sim_id: str, task_id: str, timeout: int = 600) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        data = _post("/simulation/prepare/status",
                     json={"task_id": task_id, "simulation_id": sim_id})
        status = data.get("status")
        if status in ("completed", "ready"):
            return
        if status == "failed":
            raise RuntimeError(f"Prepare falló: {data}")
        _log(f"  Prepare {sim_id}: {status} {data.get('progress','?')}%")
        time.sleep(15)
    raise TimeoutError(f"Prepare no completó en {timeout}s")


def _poll_run(sim_id: str) -> None:
    deadline = time.time() + POLL_TIMEOUT
    while time.time() < deadline:
        data = _get(f"/simulation/{sim_id}/run-status")
        status = (data.get("data") or data).get("status")
        if status == "completed":
            return
        if status == "error":
            raise RuntimeError(f"Simulación {sim_id} terminó en error")
        _log(f"  Simulación {sim_id}: {status}")
        time.sleep(POLL_INTERVAL)
    raise TimeoutError(f"Simulación no completó en {POLL_TIMEOUT}s")


def _extraer_riesgos(resultados: dict) -> list[str]:
    """
    Extrae las respuestas de los agentes y las agrupa por frecuencia de términos clave.
    Retorna lista de las respuestas más representativas (top 5).
    """
    respuestas = []
    for val in resultados.values():
        r = val.get("response", "") if isinstance(val, dict) else str(val)
        if r and len(r) > 20:
            respuestas.append(r.strip())

    if not respuestas:
        return ["Sin respuestas de agentes"]

    # Ordenar por longitud descendente (respuestas más elaboradas primero)
    respuestas.sort(key=len, reverse=True)
    return respuestas[:5]


# ── PIPELINE COMPLETO (SINCRÓNICO) ────────────────────────────────────────────

def ejecutar_simulacion(kpi_path: Path) -> None:
    _log(f"Cargando KPI desde {kpi_path.name}")
    kpi = _cargar_kpi(kpi_path)
    doc, titulo = construir_documento_kpi(kpi)

    periodo = kpi.get("nnss", {}).get("periodo", {})
    mes_anio = f"{periodo.get('mes','?')}/{periodo.get('anio','?')}"
    _log(f"Período: {mes_anio} | Documento: {len(doc)} chars")

    # Verificar que MiroFish está corriendo
    try:
        requests.get(f"{MIROFISH_BASE.replace('/api','')}/health", timeout=5)
    except Exception:
        try:
            requests.get(f"{MIROFISH_BASE}/graph/task/test", timeout=5)
        except requests.exceptions.ConnectionError:
            _log("ERROR: MiroFish no está corriendo. Ejecutar: cd MiroFish && npm run dev")
            _telegram("🐟 <b>MiroFish KPI</b>\nError: servidor MiroFish no disponible en localhost:5001")
            sys.exit(1)
        except Exception:
            pass  # 404 es OK, significa que el servidor sí está up

    _telegram(f"🐟 <b>MiroFish KPI Ops iniciado</b>\nPeríodo: {mes_anio}\nSimulación en curso (~20-40 min)...")

    # 1. Ontology
    _log("Paso 1/7: Generando ontología...")
    prompt = (
        f"Analiza el reporte KPI operativo de Egakat SPA para {mes_anio}. "
        "Identifica los principales riesgos operacionales, clientes con desempeño "
        "bajo el objetivo, pedidos pendientes críticos y recomendaciones de acción "
        "prioritaria para la próxima semana."
    )
    files = [("files", (f"kpi_ops_{mes_anio.replace('/','_')}.txt",
                        doc.encode("utf-8"), "text/plain"))]
    d1 = _post("/graph/ontology/generate",
               files=files,
               data={"simulation_requirement": prompt})
    project_id = d1["project_id"]
    _log(f"  project_id={project_id}")

    # 2. Build graph
    _log("Paso 2/7: Construyendo grafo de conocimiento...")
    d2      = _post("/graph/build", json={"project_id": project_id})
    task_id = d2["task_id"]
    graph_id = _poll_task(task_id, "graph_id", timeout=300)
    _log(f"  graph_id={graph_id}")

    # 3. Create simulation
    _log("Paso 3/7: Creando simulación...")
    d3     = _post("/simulation/create",
                   json={"project_id": project_id, "graph_id": graph_id})
    sim_id = d3["simulation_id"]
    _log(f"  sim_id={sim_id}")

    # 4. Prepare
    _log("Paso 4/7: Preparando agentes...")
    d4       = _post("/simulation/prepare", json={"simulation_id": sim_id})
    prep_tid = d4.get("task_id")
    if prep_tid:
        _poll_prepare(sim_id, prep_tid, timeout=600)
    _log("  Agentes listos")

    # 5. Start
    _log("Paso 5/7: Iniciando simulación...")
    _post("/simulation/start",
          json={"simulation_id": sim_id, "platform": "parallel"})
    _log("  Simulación corriendo...")

    # 6. Poll run-status
    _log("Paso 6/7: Esperando que completen los debates...")
    _poll_run(sim_id)
    _log("  Simulación completada")

    # 7. Interview
    _log("Paso 7/7: Entrevistando agentes...")
    pregunta = (
        "En base al reporte KPI operativo de Egakat, describe el riesgo operacional "
        "más crítico que identificas para la próxima semana y qué acción concreta recomiendas. "
        "Sé específico con clientes o métricas."
    )
    d7 = _post("/simulation/interview/all",
               json={"simulation_id": sim_id, "prompt": pregunta})
    resultados = d7.get("result", {}).get("results", {})

    n_respuestas = len(resultados)
    _log(f"  {n_respuestas} agentes respondieron")

    top_riesgos = _extraer_riesgos(resultados)

    # ── Armar mensaje Telegram ────────────────────────────────────────────────
    otif    = kpi.get("nnss", {}).get("otif", {})
    fillrate= kpi.get("nnss", {}).get("fillrate", {})
    alertas = kpi.get("alertas", [])

    header = (
        f"🐟 <b>MiroFish — Análisis KPI Ops</b>\n"
        f"📅 Período: <b>{mes_anio}</b> | {n_respuestas} agentes\n\n"
        f"📊 <b>KPIs del período:</b>\n"
        f"  OTIF: <b>{_fmt_pct(otif.get('pct_otif'))}</b>  "
        f"OT: {_fmt_pct(otif.get('pct_on_time'))}  IF: {_fmt_pct(otif.get('pct_in_full'))}\n"
        f"  Fill Rate: <b>{_fmt_pct(fillrate.get('promedio_fr'))}</b>\n\n"
    )

    # Clientes con OTIF < 95% (bajo objetivo)
    bajo_objetivo = [
        c for c in (otif.get("por_cliente") or [])
        if c.get("pedidos_evaluados", 0) > 0 and (c.get("pct_otif") or 100) < 95
    ]
    if bajo_objetivo:
        header += "⚠️ <b>Clientes bajo objetivo OTIF (&lt;95%):</b>\n"
        for c in sorted(bajo_objetivo, key=lambda x: x.get("pct_otif") or 100):
            header += f"  • {c['cliente']}: {_fmt_pct(c.get('pct_otif'))}\n"
        header += "\n"

    if alertas:
        header += "🔔 <b>Alertas activas:</b>\n"
        for a in alertas[:4]:
            header += f"  • {a[:90]}\n"
        header += "\n"

    riesgos_txt = "🤖 <b>Consenso MiroFish — Top riesgos identificados:</b>\n\n"
    for i, r in enumerate(top_riesgos, 1):
        fragmento = r[:280].replace("<", "&lt;").replace(">", "&gt;")
        riesgos_txt += f"<b>{i}.</b> {fragmento}...\n\n"

    # Telegram tiene límite de 4096 chars — enviar en 2 mensajes si es necesario
    msg1 = header + riesgos_txt[:3800 - len(header)]
    _telegram(msg1)

    _log("Análisis completado y enviado a Telegram.")

    # Guardar reporte local
    out_path = LOGS_DIR / f"mirofish_kpi_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
    out_path.parent.mkdir(exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({
            "sim_id": sim_id,
            "periodo": mes_anio,
            "n_agentes": n_respuestas,
            "top_riesgos": top_riesgos,
            "kpi_path": str(kpi_path),
            "generado": datetime.now().isoformat(),
        }, f, ensure_ascii=False, indent=2)
    _log(f"Reporte guardado en {out_path}")


# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="MiroFish KPI Ops — análisis semanal")
    parser.add_argument("--json", help="Ruta al resumen_kpi_ops JSON (default: más reciente)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Solo muestra el documento generado, sin llamar MiroFish")
    args = parser.parse_args()

    if args.json:
        kpi_path = Path(args.json)
    else:
        kpi_path = _json_mas_reciente()
        if not kpi_path:
            _log(f"ERROR: No se encontró ningún resumen_kpi_ops_*.json en {LOGS_DIR}")
            sys.exit(1)

    _log(f"Usando: {kpi_path}")

    if args.dry_run:
        kpi = _cargar_kpi(kpi_path)
        doc, titulo = construir_documento_kpi(kpi)
        print(f"\n{'='*60}")
        print(f"TÍTULO: {titulo}")
        print(f"{'='*60}")
        print(doc)
        return

    ejecutar_simulacion(kpi_path)


if __name__ == "__main__":
    main()
