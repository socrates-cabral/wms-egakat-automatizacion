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
import html as html_mod
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
POLL_TIMEOUT  = 7200 # máximo 2 horas (rondas finales son más lentas)

# ── .env ───────────────────────────────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv(CLAUDEWORK / "Softnet_Ventas" / ".env", override=False)
    load_dotenv(CLAUDEWORK / ".env", override=False)
except ImportError:
    pass

TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN_OPS", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_GRUPO_OPS_ID", "")

# Obsidian vault = directorio memory de Claude
OBSIDIAN_VAULT = Path(r"C:\Users\Socrates Cabral\.claude\projects\C--ClaudeWork\memory")


def _log(msg: str):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [MIROFISH-KPI] {msg}", flush=True)


# ── TELEGRAM ───────────────────────────────────────────────────────────────────

def _telegram(msg: str):
    token   = os.getenv("TELEGRAM_TOKEN_OPS", "")
    chat_id = os.getenv("TELEGRAM_GRUPO_OPS_ID", "")
    if not token or not chat_id:
        _log(f"[TELEGRAM MOCK] {msg[:120]}")
        return
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": msg, "parse_mode": "HTML"},
            timeout=15,
        )
        if not r.ok:
            _log(f"Telegram HTML error {r.status_code}, reintentando sin parse_mode...")
            r2 = requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": msg},
                timeout=15,
            )
            if not r2.ok:
                _log(f"Telegram error {r2.status_code}: {r2.text[:200]}")
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
    Convierte el JSON KPI en documento denso para MiroFish.
    Incluye OTIF histórico, productividad, inventario, staging, ocupación y recepciones.
    """
    fecha_gen = kpi.get("fecha_generacion", "")
    nnss      = kpi.get("nnss", {})
    prod      = kpi.get("productividad", {})
    inv       = kpi.get("inventario", {})
    hist      = kpi.get("historico", {})
    alertas   = kpi.get("alertas", [])
    recs      = kpi.get("recomendaciones", [])
    periodo   = nnss.get("periodo", {})
    anio      = periodo.get("anio", "")
    mes       = periodo.get("mes", "")
    MESES = {1:"Enero",2:"Febrero",3:"Marzo",4:"Abril",5:"Mayo",6:"Junio",
             7:"Julio",8:"Agosto",9:"Septiembre",10:"Octubre",11:"Noviembre",12:"Diciembre"}
    mes_nombre = MESES.get(mes, str(mes))
    titulo     = f"KPI Operativo Egakat — {mes_nombre} {anio}"

    otif     = nnss.get("otif", {})
    fillrate = nnss.get("fillrate", {})
    pend     = nnss.get("pendientes", {})

    # ── OTIF por CD ────────────────────────────────────────────────────────────
    otif_cd_txt = "\n".join(
        f"  {cd.get('cd','?'):12s}  OTIF={_fmt_pct(cd.get('pct_otif'))}  "
        f"OT={_fmt_pct(cd.get('pct_on_time'))}  IF={_fmt_pct(cd.get('pct_in_full'))}  "
        f"({cd.get('pedidos_evaluados',0)} ped)"
        for cd in (otif.get("por_cd") or [])
    ) or "  Sin datos"

    # ── OTIF por cliente con motivos no In Full ────────────────────────────────
    clientes_otif = sorted(
        [c for c in (otif.get("por_cliente") or []) if c.get("pedidos_evaluados", 0) > 0],
        key=lambda x: x.get("pct_otif") or 100
    )
    cli_otif_lines = []
    for c in clientes_otif:
        line = (
            f"  {c['cliente']:25s}  OTIF={_fmt_pct(c.get('pct_otif'))}  "
            f"OT={_fmt_pct(c.get('pct_on_time'))}  IF={_fmt_pct(c.get('pct_in_full'))}  "
            f"({c.get('pedidos_evaluados',0)} ped "
            f"/ {c.get('pedidos_no_in_full',0)} no-IF)"
        )
        for m in (c.get("motivos_no_in_full") or []):
            line += f"\n    → No-IF motivo: '{m['motivo']}' ({m['lineas']} líneas)"
        arr = c.get("arrastres", {})
        if arr and arr.get("total", 0) > 0:
            line += (
                f"\n    → Arrastres: {arr['total']} ped "
                f"({_fmt_pct(arr.get('pct_on_time_arrastres'))} OT arrastres)"
            )
        cli_otif_lines.append(line)
    clientes_otif_txt = "\n".join(cli_otif_lines) or "  Sin datos"

    # ── Fill Rate por cliente ──────────────────────────────────────────────────
    fr_clientes_txt = "\n".join(
        f"  {c['cliente']:25s}  FR={_fmt_pct(c.get('promedio_fr'))}  "
        f"({c.get('lineas',0)} líns / {c.get('pedidos',0)} ped)"
        for c in sorted(
            [c for c in (fillrate.get("por_cliente") or []) if c.get("tiene_datos_evaluables")],
            key=lambda x: x.get("promedio_fr") or 100
        )
    ) or "  Sin datos"

    # ── Pedidos pendientes ─────────────────────────────────────────────────────
    pend_txt = f"  Total: {pend.get('total_pedidos',0)} pedidos / {pend.get('total_unidades',0)} uds\n"
    for p in (pend.get("mayores_7_dias") or [])[:5]:
        ini = p.get("fecha_inicio_preparacion") or "sin registro de inicio"
        dias = p.get("dias_abierto", 0) or 0
        # >3650 días = fecha epoch (WMS timestamp=0): no es antigüedad real
        dias_str = f"{dias} dias" if dias <= 3650 else f"FECHA INVALIDA EN WMS (valor: {dias} dias)"
        pend_txt += (
            f"  CRITICO: {p['cliente']} | Ped.{p['nro_pedido']} | Estado: {p.get('estado','')} | "
            f"{dias_str} | Inicio prep: {ini} | {p.get('unidades',0)} uds\n"
        )

    # ── Histórico OTIF YTD ────────────────────────────────────────────────────
    ytd = hist.get("nnss", {}).get("otif_ytd", [])
    ytd_txt = "\n".join(
        f"  {y['cliente']:25s}  OTIF-YTD={_fmt_pct(y.get('pct_otif'))}  "
        f"({y.get('pedidos_evaluados_acum',0)} ped  meses:{y.get('meses_incluidos',[])})"
        for y in sorted([y for y in ytd if y.get("disponible")], key=lambda x: x.get("pct_otif") or 100)[:10]
    ) or "  Sin datos YTD"

    # ── Tendencia mensual clientes clave ──────────────────────────────────────
    otif_mensual = hist.get("nnss", {}).get("otif_mensual", [])
    CLIENTES_CLAVE = {"MASCOTAS LATINAS", "UNILEVER", "DAIKIN", "POCHTECA", "BARENTZ"}
    tendencia: dict = {}
    for r in otif_mensual:
        cli = r.get("cliente")
        if cli in CLIENTES_CLAVE and r.get("pct_otif") is not None:
            tendencia.setdefault(cli, []).append(
                f"{r.get('mes_nombre','?')[:3]}:{_fmt_pct(r.get('pct_otif'))}({r.get('pedidos_evaluados',0)}p)"
            )
    tendencia_txt = "\n".join(
        f"  {cli}: {' | '.join(meses)}" for cli, meses in tendencia.items()
    ) or "  Sin datos tendencia"

    # ── Productividad ──────────────────────────────────────────────────────────
    glb = prod.get("global", {})
    prod_cd_txt = "\n".join(
        f"  {c.get('Centro','?'):15s}  {c.get('lineas',0):7,} líns  "
        f"{c.get('unidades',0):10,.0f} uds  {c.get('participacion_lineas_pct',0):.1f}%"
        for c in (prod.get("por_cd") or [])
    )
    prod_cli_txt = "\n".join(
        f"  {c.get('cliente','?'):25s}  {c.get('lineas',0):7,} líns  "
        f"{c.get('unidades',0):10,.0f} uds  {c.get('pedidos',0)} ped  "
        f"({c.get('participacion_lineas_pct',0):.1f}%)"
        for c in sorted(prod.get("por_cliente") or [], key=lambda x: x.get("lineas",0), reverse=True)[:8]
    )
    derco = prod.get("derco", {})
    derco_txt = ""
    if derco.get("disponible"):
        ap = derco.get("ap_total", {})
        derco_txt = f"  AP total: {ap.get('lineas',0):,} líns / {ap.get('unidades',0):,.0f} uds\n"
        for d in (derco.get("ap_detalle") or []):
            derco_txt += f"    {d['canal_detalle']:22s}: {d['lineas']:,} líns / {d['unidades']:,.0f} uds\n"
        for c in (derco.get("canales") or []):
            derco_txt += f"  Canal {c['canal']:10s}: {c['lineas']:,} líns / {c['unidades']:,.0f} uds / {c['pedidos']} ped\n"

    # ── Inventario ─────────────────────────────────────────────────────────────
    stock     = inv.get("stock", {})
    blq       = inv.get("stock_bloqueado_wms", {})
    staging   = inv.get("staging", {})
    ocu       = inv.get("ocupacion", {})
    ant       = inv.get("staging_antiguedad", {})
    ira_ila   = inv.get("ira_ila", {}).get("wms", {})

    stock_cli_txt = "\n".join(
        f"  {c.get('cliente','?'):25s} {c.get('cd','?'):12s}  "
        f"{c.get('unidades',0):10,.0f} uds  {c.get('plts',0):5} plts  {c.get('skus',0)} SKUs"
        for c in (stock.get("por_cliente") or [])[:8]
    )
    stg_in  = next((s['plts'] for s in (staging.get("por_estado") or []) if s['estado_staging']=='STAGING IN'), 0)
    stg_out = next((s['plts'] for s in (staging.get("por_estado") or []) if s['estado_staging']=='STAGING OUT'), 0)

    ant_txt = "\n".join(
        f"  {b.get('balde_antiguedad','?'):22s}: {b.get('plts',0):4} plts / "
        f"{b.get('unidades',0):8,.0f} uds / {b.get('skus',0)} SKUs"
        for b in (ant.get("por_balde") or [])
    )
    ant_cli_txt = "\n".join(
        f"  {c.get('cliente','?'):25s} {c.get('cd','?'):12s}  "
        f"{c.get('plts',0)} plts tot  {c.get('plts_mayor_21_dias',0)} plts >21d  "
        f"[balde: {c.get('balde_principal','?')}]"
        for c in (ant.get("por_cliente") or []) if c.get("plts_mayor_21_dias", 0) > 0
    ) or "  Ninguno"

    ocu_cd_txt = "\n".join(
        f"  {c.get('cd','?'):12s}  Ocup={c.get('ocupacion_pct',0):.1f}%  "
        f"({c.get('ocupadas',0):,} ocup / {c.get('total_ubicaciones_layout',0):,.0f} total)  "
        f"Libres: {c.get('libres',0):,}"
        for c in (ocu.get("por_cd") or [])
    )
    ocu_loc_txt = "\n".join(
        f"  {c.get('cd','?')} {c.get('locacion','?'):15s}: {c.get('ocupacion_pct',0):.1f}%  "
        f"({c.get('ocupadas',0):,}/{c.get('total',0):,})"
        for c in (ocu.get("por_locacion") or [])
    )

    # ── Recepciones del período ────────────────────────────────────────────────
    rec_his = hist.get("recepciones", {})
    rec_mes = [r for r in (rec_his.get("por_cliente") or [])
               if r.get("mes") == mes and r.get("anio") == anio]
    rec_txt = "\n".join(
        f"  {r.get('cliente','?'):25s} {r.get('cd','?')[:12]:12s}  "
        f"ORs:{r.get('or_unicas',0)}  Plts:{r.get('pallets_recibidos',0)}  "
        f"Backlog:{r.get('backlog_or',0)} ORs ({r.get('backlog_pct',0):.1f}%)  "
        f"TPR:{r.get('tpr_dias_por_or',0):.2f}d/OR"
        for r in rec_mes[:8]
    ) or "  Sin datos de recepciones"

    # ── Armado del documento ───────────────────────────────────────────────────
    arr_global = otif.get("arrastres", {})

    doc = f"""REPORTE KPI OPERATIVO — EGAKAT SPA (3PL CHILE)
Periodo: {mes_nombre} {anio}  |  Generado: {fecha_gen}
CDs: QUILICURA (principal) | PUDAHUEL | PUDAHUEL UNITARIO
Objetivos: OTIF >=95% | Fill Rate >=99% | IRA >=99% | ILA >=99%

=====================================
1. OTIF Y FILL RATE DEL PERIODO
=====================================

GLOBAL:
  Pedidos evaluados: {otif.get('pedidos_evaluados',0)}
  OTIF:     {_fmt_pct(otif.get('pct_otif'))}  [obj >=95%]
  On Time:  {_fmt_pct(otif.get('pct_on_time'))}
  In Full:  {_fmt_pct(otif.get('pct_in_full'))}
  Fill Rate promedio: {_fmt_pct(fillrate.get('promedio_fr'))}  [obj >=99%]
  Arrastres mes anterior: {arr_global.get('total',0)} ped ({arr_global.get('arrastres_tardios',0)} tardios)

POR CENTRO DE DISTRIBUCION:
{otif_cd_txt}

POR CLIENTE (peor a mejor OTIF):
{clientes_otif_txt}

FILL RATE POR CLIENTE (peor a mejor):
{fr_clientes_txt}

=====================================
2. PEDIDOS PENDIENTES
=====================================

{pend_txt}
=====================================
3. TENDENCIA HISTORICA 2026 (YTD Ene-{mes_nombre})
=====================================

OTIF ACUMULADO AÑO (YTD):
{ytd_txt}

EVOLUCION MENSUAL OTIF — CLIENTES CLAVE:
{tendencia_txt}

=====================================
4. PRODUCTIVIDAD OPERACIONAL
=====================================

GLOBAL:
  Lineas:          {glb.get('lineas',0):,}
  Unidades:        {glb.get('unidades',0):,.0f}
  Pedidos:         {glb.get('pedidos',0):,}
  Dias trabajados: {glb.get('dias_trabajados',0)}
  Lineas/dia:      {glb.get('productividad_lineas_dia',0):,.1f}
  Uds/hora:        {glb.get('productividad_unidades_hora',0):,.1f}
  Horas trabajadas:{glb.get('horas_trabajadas_total',0):,.1f}

POR CENTRO:
{prod_cd_txt}

POR CLIENTE (top volumen):
{prod_cli_txt}

DERCO — DESGLOSE CANALES:
{derco_txt if derco_txt else '  Sin datos DERCO'}

=====================================
5. INVENTARIO — STOCK, STAGING, OCUPACION
=====================================

STOCK WMS:
  Total unidades: {stock.get('total_unidades',0):,.0f}
  Total pallets:  {stock.get('total_plts',0):,}
  SKUs activos:   {stock.get('total_skus',0):,}
  Stock bloqueado WMS: {blq.get('total_skus','N/D')} SKUs / {blq.get('total_unidades','N/D')} uds

STOCK POR CLIENTE:
{stock_cli_txt}

IRA/ILA (Precision de Inventario):
  IRA: {_fmt_pct(ira_ila.get('ira_ponderado_pct'))}  [obj >=99%]
  ILA: {_fmt_pct(ira_ila.get('ila_ponderado_pct'))}  [obj >=99%]

STAGING EN PROCESO:
  Total pallets: {staging.get('total_plts',0)}  ({stg_in} STAGING IN / {stg_out} STAGING OUT)
  Total uds: {staging.get('total_unidades',0):,.0f}

ANTIGUEDAD STAGING (critico para gestion):
{ant_txt}

CLIENTES CON PALLETS >21 DIAS EN STAGING:
{ant_cli_txt}

OCUPACION DE BODEGAS:
  Global: {ocu.get('ocupacion_pct',0):.1f}%  ({ocu.get('ocupadas',0):,}/{ocu.get('total_ubicaciones_layout',0):,.0f})  Libres:{ocu.get('libres',0):,}

POR CD:
{ocu_cd_txt}

POR TIPO DE UBICACION:
{ocu_loc_txt}

=====================================
6. RECEPCIONES DEL PERIODO
=====================================

{rec_txt}

=====================================
7. ALERTAS Y RECOMENDACIONES
=====================================

ALERTAS:
{chr(10).join(f'  ! {a}' for a in alertas[:10]) or '  Sin alertas'}

RECOMENDACIONES:
{chr(10).join(f'  > {r}' for r in recs[:8]) or '  Sin recomendaciones'}

=====================================
CONTEXTO EGAKAT SPA
=====================================
Egakat SPA: 3PL chileno, CDs Quilicura y Pudahuel.
Clientes: DERCO (automotriz, 97% del volumen), MASCOTAS LATINAS, UNILEVER,
  BARENTZ, DAIKIN, POCHTECA, OMNITECH, RUNO SPA, CEPAS CHILE y otros.
Indicadores servicio: OTIF y Fill Rate. Precision inventario: IRA e ILA.
Pedidos "no In Full" sin motivo registrado = campo vacio en WMS, no diagnosticado.
Staging >21 dias = pallet con permanencia anomala, riesgo de obsolescencia o bloqueo operativo.
Pedidos con fecha 1970 = anomalia de datos en WMS, requiere investigacion.
"""
    return doc, titulo


# ── MIROFISH API ──────────────────────────────────────────────────────────────

def _post(endpoint: str, **kwargs) -> dict:
    resp = requests.post(f"{MIROFISH_BASE}{endpoint}", timeout=90, **kwargs)
    if not resp.ok:
        try:
            body = resp.json()
        except Exception:
            body = resp.text[:400]
        raise RuntimeError(f"MiroFish {endpoint} → {resp.status_code}: {body}")
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
        inner = data.get("data") or data
        status = inner.get("status")
        if status == "completed":
            # graph_id está en result.graph_id, no en el nivel del task
            return inner.get("result", {}).get(campo) or inner.get(campo)
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
        inner = data.get("data") or data
        # El campo real es "runner_status", no "status"
        status = inner.get("runner_status")
        if status == "completed":
            return
        if status in ("failed", "error"):
            raise RuntimeError(f"Simulación {sim_id} terminó en error: {inner}")
        pct   = inner.get("progress_percent", 0)
        ronda = inner.get("current_round", 0)
        total = inner.get("total_rounds", "?")
        _log(f"  Simulación {sim_id}: {status} | ronda {ronda}/{total} ({pct:.1f}%)")
        time.sleep(POLL_INTERVAL)
    raise TimeoutError(f"Simulación no completó en {POLL_TIMEOUT}s")


def _extraer_riesgos(resultados: dict) -> list[str]:
    """
    Sintetiza las respuestas de los agentes con Claude.
    Retorna 3-5 bullets accionables en español.
    """
    respuestas = []
    for val in resultados.values():
        r = val.get("response", "") if isinstance(val, dict) else str(val)
        if r and len(r) > 20:
            respuestas.append(r.strip())

    if not respuestas:
        return ["Sin respuestas de agentes"]

    # Intentar síntesis con Claude
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))
        combined = "\n\n---\n\n".join(respuestas[:16])
        prompt = (
            "Eres analista senior de Egakat SPA (3PL chileno). "
            f"Tienes {len(respuestas)} analisis de agentes que debatieron los KPIs operativos.\n\n"
            "REGLA CRITICA: solo incluye clientes, metricas y hechos que aparezcan "
            "en MULTIPLES respuestas de agentes. Si un dato solo lo menciona un agente, "
            "ignora ese dato. No inventes causas raiz, protocolos ni referencias externas.\n\n"
            "TAREA: sintetizar exactamente 5 bullets — 3 operacionales + 2 estrategicos.\n\n"
            "Bullets 1-3 (OPERACIONAL) — accion esta semana:\n"
            "Formato: '• [Cliente]: [problema con cifra real] → [accion concreta]'\n"
            "Ejemplo valido: '• MASCOTAS LATINAS: OTIF 84.4% (7 ped no-IF sin motivo) → "
            "revisar causas de incumplimiento en WMS esta semana'\n\n"
            "Bullets 4-5 (ESTRATEGICO) — para gerencia, no para operaciones del dia:\n"
            "Formato: '• [Area/tema]: [observacion con dato] → [implicancia estrategica]'\n"
            "Ejemplo valido: '• Concentracion: DERCO representa 97% del volumen productividad "
            "→ riesgo operacional ante baja demanda de un solo cliente'\n\n"
            "Respeta el formato exacto. Maximo 130 chars por bullet. "
            "Si no hay consenso en un tema, no lo incluyas.\n\n"
            f"Respuestas de agentes:\n{combined[:10000]}"
        )
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}]
        )
        sintesis = msg.content[0].text.strip()
        bullets = [b.strip() for b in sintesis.split("\n") if b.strip().startswith("•")]
        if bullets:
            return bullets
    except Exception as e:
        _log(f"Síntesis Claude falló ({e}), usando extracción manual")

    # Fallback: extraer sección "Acción concreta" de cada respuesta
    acciones = []
    for r in respuestas:
        for marker in ["Acción concreta recomendada", "Acción concreta", "Recomendación"]:
            idx = r.find(marker)
            if idx != -1:
                fragmento = r[idx:idx+250].replace("\n", " ").strip()
                acciones.append(fragmento)
                break
    if acciones:
        return list(dict.fromkeys(acciones))[:3]  # deduplicar, top 3

    # Último fallback: primeras 2 oraciones de las respuestas más cortas
    respuestas.sort(key=len)
    return [r[:200] for r in respuestas[:3]]


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
            _telegram("🐟 <b>MiroFish KPI</b>\n❌ Error: servidor MiroFish no disponible en localhost:5001")
            sys.exit(1)
        except Exception:
            pass  # 404 es OK, significa que el servidor sí está up

    _telegram(f"🐟 <b>MiroFish KPI Ops iniciado</b>\n📅 Período: <b>{html_mod.escape(mes_anio)}</b>\n⏳ Simulación en curso (~20-40 min)...")

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
        f"Analiza el reporte KPI operativo de Egakat SPA — {mes_anio}. "
        "REGLA ABSOLUTA E INNEGOCIABLE: cita EXCLUSIVAMENTE cifras, clientes y hechos "
        "que esten en el documento de esta simulacion. Si algo no tiene explicacion en "
        "los datos (ej. 'Sin motivo registrado'), di exactamente eso. "
        "No inventes protocolos, procedimientos, codigos de incidente ni causas raiz "
        "que no aparezcan explicitamente en el reporte. "
        "\n\nEstructura tu respuesta en TRES secciones obligatorias:\n"
        "\n[ALERTA OPERACIONAL]\n"
        "El problema mas critico que requiere accion en las proximas 48 horas. "
        "Especifica: cliente exacto, indicador afectado con su valor real vs objetivo, "
        "magnitud del desvio (puntos porcentuales o dias de retraso), e impacto en nivel de servicio.\n"
        "\n[RIESGO SEMANA]\n"
        "El riesgo principal para el cierre operativo de la proxima semana. "
        "Sustenta con al menos un dato especifico del reporte (porcentaje, volumen, "
        "numero de pedidos, antiguedad de staging, ocupacion de CD). "
        "Indica que puede empeorar si no se actua y que cliente o area se ve afectada.\n"
        "\n[SEÑAL ESTRATEGICA]\n"
        "Una observacion relevante para gerencia, no para operaciones del dia. "
        "Puede ser sobre: concentracion de volumen en un cliente, desequilibrio de "
        "ocupacion entre CDs, tendencia acumulada YTD de un KPI, calidad de datos "
        "(campos vacios, fechas anomalas), o riesgo de capacidad a mediano plazo. "
        "Sustentado en datos del reporte, no en supuestos."
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

    h = html_mod.escape  # shorthand para escapar valores dinámicos

    otif_pct = otif.get("pct_otif")
    fr_pct   = fillrate.get("promedio_fr")
    n_ped    = otif.get("pedidos_evaluados", 0)

    emoji_otif = "✅" if (otif_pct or 0) >= 95 else ("⚠️" if (otif_pct or 0) >= 85 else "🔴")
    emoji_fr   = "✅" if (fr_pct or 0) >= 95 else ("⚠️" if (fr_pct or 0) >= 85 else "🔴")

    MESES_NOM = {1:"Enero",2:"Febrero",3:"Marzo",4:"Abril",5:"Mayo",6:"Junio",
                 7:"Julio",8:"Agosto",9:"Septiembre",10:"Octubre",11:"Noviembre",12:"Diciembre"}
    periodo   = kpi.get("nnss", {}).get("periodo", {})
    mes_nom   = MESES_NOM.get(periodo.get("mes"), mes_anio)
    anio_nom  = periodo.get("anio", "")

    msg = (
        f"🐟 <b>MiroFish · Análisis Operacional</b>\n"
        f"📅 <b>{h(mes_nom)} {anio_nom}</b>  ·  {n_respuestas} agentes\n\n"
        f"<b>¿Cómo cerró el período?</b>\n"
        f"{emoji_otif} OTIF: <b>{h(_fmt_pct(otif_pct))}</b>  "
        f"(OT: {h(_fmt_pct(otif.get('pct_on_time')))} · IF: {h(_fmt_pct(otif.get('pct_in_full')))})\n"
        f"{emoji_fr} Fill Rate: <b>{h(_fmt_pct(fr_pct))}</b>\n"
        f"📦 Pedidos evaluados: {n_ped:,}\n"
    )

    # Clientes con OTIF < 95% (bajo objetivo)
    bajo_objetivo = [
        c for c in (otif.get("por_cliente") or [])
        if c.get("pedidos_evaluados", 0) > 0 and (c.get("pct_otif") or 100) < 95
    ]
    if bajo_objetivo:
        msg += f"\n⚠️ <b>Clientes bajo objetivo OTIF (&lt;95%):</b>\n"
        for c in sorted(bajo_objetivo, key=lambda x: x.get("pct_otif") or 100):
            diff = round(95 - (c.get("pct_otif") or 0), 1)
            msg += f"  • <b>{h(c['cliente'])}</b>: {h(_fmt_pct(c.get('pct_otif')))} <i>(-{diff} pts)</i>\n"

    if alertas:
        msg += f"\n🔔 <b>Alertas activas:</b>\n"
        for a in alertas[:3]:
            msg += f"  • {h(str(a)[:100])}\n"

    # Haiku devuelve 5 bullets: primeros 3 ops, últimos 2 estratégicos
    ops_bullets    = top_riesgos[:3]
    estrat_bullets = top_riesgos[3:]

    if ops_bullets:
        msg += f"\n🔧 <b>Acciones operacionales esta semana:</b>\n"
        for r in ops_bullets:
            msg += f"\n{h(r.replace('**','').replace('*',''))}\n"

    if estrat_bullets:
        msg += f"\n📈 <b>Señales estratégicas para gerencia:</b>\n"
        for r in estrat_bullets:
            msg += f"\n{h(r.replace('**','').replace('*',''))}\n"

    if not top_riesgos:
        msg += f"\n🤖 <b>Sin consenso de agentes disponible</b>\n"

    msg += f"\n<i>Simulación MiroFish · {datetime.now().strftime('%d/%m/%Y %H:%M')}</i>"

    # Telegram tiene límite de 4096 chars — truncar si es necesario
    if len(msg) > 4000:
        msg = msg[:3950] + "\n<i>[truncado]</i>"
    _telegram(msg)

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

    # ── Export a Obsidian vault ───────────────────────────────────────────────
    _exportar_obsidian(kpi, top_riesgos, bajo_objetivo, otif, fillrate, sim_id)


# ── EXPORT OBSIDIAN ──────────────────────────────────────────────────────────

def _exportar_obsidian(kpi: dict, top_riesgos: list, bajo_objetivo: list,
                       otif: dict, fillrate: dict, sim_id: str) -> None:
    """Guarda nota Markdown en el vault de Obsidian (= directorio memory de Claude)."""
    try:
        periodo  = kpi.get("nnss", {}).get("periodo", {})
        anio     = periodo.get("anio", datetime.now().year)
        mes      = periodo.get("mes",  datetime.now().month)
        MESES    = {1:"Enero",2:"Febrero",3:"Marzo",4:"Abril",5:"Mayo",6:"Junio",
                    7:"Julio",8:"Agosto",9:"Septiembre",10:"Octubre",11:"Noviembre",12:"Diciembre"}
        mes_nombre = MESES.get(mes, str(mes))
        semana   = datetime.now().strftime("%Y-W%W")
        fecha    = datetime.now().strftime("%Y-%m-%d")

        # Clientes bajo objetivo como lista YAML
        clientes_riesgo_yaml = (
            "[" + ", ".join(f'"{c["cliente"]}"' for c in bajo_objetivo) + "]"
            if bajo_objetivo else "[]"
        )

        carpeta = OBSIDIAN_VAULT / "kpi_ops"
        carpeta.mkdir(exist_ok=True)
        nota_path = carpeta / f"KPI_Ops_{anio}_{mes:02d}.md"

        riesgos_md = "\n\n".join(
            f"**{i}.** {r}" for i, r in enumerate(top_riesgos, 1)
        )

        bajo_obj_md = "\n".join(
            f"| {c['cliente']} | {_fmt_pct(c.get('pct_otif'))} | "
            f"{_fmt_pct(c.get('pct_on_time'))} | {_fmt_pct(c.get('pct_in_full'))} |"
            for c in bajo_objetivo
        ) or "_(ninguno)_"

        contenido = f"""---
title: KPI Ops {mes_nombre} {anio}
date: {fecha}
semana: {semana}
type: kpi-ops
otif_global: {otif.get('pct_otif', 0)}
fillrate_global: {fillrate.get('promedio_fr', 0)}
pedidos_evaluados: {otif.get('pedidos_evaluados', 0)}
clientes_riesgo: {clientes_riesgo_yaml}
sim_id: {sim_id}
tags: [kpi-ops, mirofish, egakat]
---

# KPI Operativo — {mes_nombre} {anio}

## Indicadores globales

| Métrica | Valor |
|---------|-------|
| OTIF global | **{_fmt_pct(otif.get('pct_otif'))}** |
| On Time | {_fmt_pct(otif.get('pct_on_time'))} |
| In Full | {_fmt_pct(otif.get('pct_in_full'))} |
| Fill Rate promedio | **{_fmt_pct(fillrate.get('promedio_fr'))}** |
| Pedidos evaluados | {otif.get('pedidos_evaluados', 0)} |

## Clientes bajo objetivo OTIF (<95%)

| Cliente | OTIF | On Time | In Full |
|---------|------|---------|---------|
{bajo_obj_md}

## 🐟 Riesgos identificados por MiroFish

> Simulación `{sim_id}` — 200 agentes debatiendo el reporte operacional

{riesgos_md}

---
*Generado automáticamente por [[mirofish_kpi_ops]] · {fecha}*
"""
        nota_path.write_text(contenido, encoding="utf-8")
        _log(f"Nota Obsidian guardada: {nota_path}")
    except Exception as e:
        _log(f"WARNING: No se pudo exportar a Obsidian: {e}")


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
