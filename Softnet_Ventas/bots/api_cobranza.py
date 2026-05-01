"""
Microservicio de datos para n8n LangChain agent.
Expone el resumen del Libro de Ventas como JSON via HTTP.

Entrypoint Task Scheduler:
  py C:\\ClaudeWork\\Softnet_Ventas\\bots\\api_cobranza.py

Endpoints:
  GET /cobranza/resumen          — formato original (compatibilidad)
  GET /cobranza/resumen_bot      — formato optimizado para bot Telegram (clasificación única)
  GET /cobranza/proyeccion_caja  — cobros futuros por semana y mes (Sprint 4)
  GET /cobranza/resumen_cliente  — datos filtrados por RUT
  GET /clientes/info             — verificación registro bot clientes
  GET /health
"""
import sys
sys.stdout.reconfigure(encoding="utf-8")

import os
import traceback
from pathlib import Path
from datetime import date, timedelta, datetime
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
from flask import Flask, jsonify

_BASE = Path(__file__).resolve().parent.parent
load_dotenv(_BASE / ".env")
load_dotenv(_BASE.parent / ".env")

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sp_reader import leer_todos_meses_abiertos_consolidado, filtrar_por_rut

import pandas as pd

app = Flask(__name__)

_PLAZOS = [90, 60, 45, 30, 15]
_TZ_SCL = ZoneInfo("America/Santiago")
_MESES_SP = {1:"Enero", 2:"Febrero", 3:"Marzo", 4:"Abril", 5:"Mayo", 6:"Junio",
             7:"Julio", 8:"Agosto", 9:"Septiembre", 10:"Octubre", 11:"Noviembre", 12:"Diciembre"}

# Rutas que NO requieren autenticación
_RUTAS_PUBLICAS = {"/health"}


@app.before_request
def verificar_api_key():
    """Requiere X-API-Key en todos los endpoints excepto /health."""
    from flask import request as freq
    if freq.path in _RUTAS_PUBLICAS:
        return  # health pasa sin autenticación
    secret = os.getenv("API_COBRANZA_SECRET", "")
    if not secret:
        return jsonify({"error": "API no configurada — falta API_COBRANZA_SECRET"}), 500
    key = freq.headers.get("X-API-Key", "")
    if not key or key != secret:
        return jsonify({"error": "No autorizado"}), 401


# ── Helpers compartidos ────────────────────────────────────────────────

def _detectar_plazo(forma: str) -> int | None:
    texto = str(forma).upper()
    for d in _PLAZOS:
        if str(d) in texto:
            return d
    return None


def _col_razon(df: pd.DataFrame) -> str:
    for c in ("Razon Social", "Razón Social"):
        if c in df.columns:
            return c
    return df.columns[4]


def _fecha_corte_scl() -> date:
    """Fecha de hoy en zona America/Santiago."""
    return datetime.now(tz=_TZ_SCL).date()


def _estado_pagado(valor) -> bool:
    return str(valor or "").strip().upper() == "PAGADO"


def _monto_original(row) -> int:
    total_raw = pd.to_numeric(row.get("Total", 0), errors="coerce")
    if pd.notna(total_raw) and total_raw > 0:
        return int(round(float(total_raw)))
    return 0


def _plazo_pago_dias(row) -> int | None:
    for col in ("Plazo Pago (días)", "Plazo Pago (dias)", "Plazo Pago", "Plazo"):
        if col not in row.index:
            continue
        valor = pd.to_numeric(row.get(col), errors="coerce")
        if pd.notna(valor) and valor >= 0:
            return int(round(float(valor)))
    return _detectar_plazo(row.get("Forma de Pago", ""))


def _fecha_vencimiento_doc(row) -> date | None:
    for col in ("Vence", "Fecha Vencimiento", "Fecha de Vencimiento"):
        if col not in row.index:
            continue
        fecha = _fecha_base_date(row.get(col))
        if fecha is not None:
            return fecha

    fecha_base = _fecha_base_date(row.get("Fecha"))
    plazo = _plazo_pago_dias(row)
    if fecha_base is None or plazo is None:
        return None
    return fecha_base + timedelta(days=plazo)


def _clasificar_vencimiento_doc(row, fecha_corte: date) -> tuple[str, date | None, int | None]:
    fecha_vencimiento = _fecha_vencimiento_doc(row)
    if fecha_vencimiento is None:
        return "sin_plazo", None, None

    dias_mora = (fecha_corte - fecha_vencimiento).days
    if fecha_vencimiento < fecha_corte:
        return "vencido", fecha_vencimiento, dias_mora
    return "no_vencido", fecha_vencimiento, dias_mora


# Constante para sorting - docs sin mora van al final
_DIAS_MORA_SORT_DEFAULT = -999999



def _col_rut(df: pd.DataFrame) -> str | None:
    """Detecta una columna de RUT de forma tolerante, si existe."""
    candidatos = (
        "RUT", "Rut", "RUT Cliente", "Rut Cliente", "RUTCliente",
        "R.U.T.", "RUT_CLIENTE",
    )
    for c in candidatos:
        if c in df.columns:
            return c

    def normalizar(nombre: str) -> str:
        return (
            str(nombre)
            .upper()
            .replace(".", "")
            .replace("_", "")
            .replace(" ", "")
        )

    normalizados = {normalizar(c): c for c in df.columns}
    for key in ("RUT", "RUTCLIENTE"):
        if key in normalizados:
            return normalizados[key]
    return None


def _monto_pendiente(row) -> int:
    """
    Retorna el monto abierto real del documento.
    Prioridad: Saldo; fallback: Total solo si no hay Saldo disponible.
    """
    if "Saldo" in row.index:
        saldo_raw = pd.to_numeric(row.get("Saldo", None), errors="coerce")
        if pd.notna(saldo_raw):
            return max(int(round(float(saldo_raw))), 0)

    total_raw = pd.to_numeric(row.get("Total", None), errors="coerce")
    if pd.notna(total_raw):
        return max(int(round(float(total_raw))), 0)
    return 0


def _texto_plano(valor) -> str:
    if pd.isna(valor):
        return ""
    return str(valor).strip()


def _fecha_base_date(valor) -> date | None:
    """Convierte un valor de fecha a date, o None si no es válido."""
    if pd.isna(valor):
        return None
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    fecha = pd.to_datetime(valor, errors="coerce")
    if pd.isna(fecha):
        return None
    return fecha.date()


def _build_documento_detalle(row, fecha_corte: date, col_cliente: str, rut_col: str | None) -> dict | None:
    saldo_pendiente = _monto_pendiente(row)
    if saldo_pendiente <= 0 or _estado_pagado(row.get("Estado")):
        return None

    fecha_emision = _fecha_base_date(row.get("Fecha"))
    estado_vencimiento, fecha_vencimiento, dias_rel = _clasificar_vencimiento_doc(row, fecha_corte)
    dias_mora = int(dias_rel) if dias_rel is not None and estado_vencimiento == "vencido" else 0 if fecha_vencimiento else None
    vencido_doc = saldo_pendiente if estado_vencimiento == "vencido" else 0
    no_vencido_doc = saldo_pendiente if estado_vencimiento == "no_vencido" else 0
    sin_plazo_doc = saldo_pendiente if estado_vencimiento == "sin_plazo" else 0
    tipo_doc_num = pd.to_numeric(row.get("Tipo Doc"), errors="coerce")
    cto_num = pd.to_numeric(row.get("Cto"), errors="coerce")
    rut = _texto_plano(row.get(rut_col)) if rut_col else ""
    cto_text = "" if pd.isna(cto_num) else str(int(cto_num))
    tipo_doc_text = "" if pd.isna(tipo_doc_num) else str(int(tipo_doc_num))

    return {
        "cliente": _texto_plano(row.get(col_cliente)),
        "rut": rut,
        "tipo_doc": tipo_doc_text,
        "cto": cto_text,
        "folio": cto_text,
        "doc_id": _texto_plano(row.get("doc_id")),
        "fecha": fecha_emision.strftime("%d/%m/%Y") if fecha_emision else None,
        "fecha_vencimiento": fecha_vencimiento.strftime("%d/%m/%Y") if fecha_vencimiento else None,
        "estado": _texto_plano(row.get("Estado")),
        "total": _monto_original(row),
        "saldo": saldo_pendiente,
        "saldo_pendiente_doc": saldo_pendiente,
        "vencido_doc": vencido_doc,
        "no_vencido_doc": no_vencido_doc,
        "sin_plazo_doc": sin_plazo_doc,
        "dias_mora": dias_mora,
        "estado_vencimiento": estado_vencimiento,
        "clasificacion": _texto_plano(row.get("Clasificacion")),
        "area_de_negocio": _texto_plano(row.get("Area de Negocio")),
        "vendedor": _texto_plano(row.get("Vendedor")),
        "comprobantes_tesoreria": _texto_plano(row.get("Comprobantes Tesoreria")),
    }


def _clientes_cartera(df: pd.DataFrame, hoy: date, col_cliente: str) -> dict:
    """
    Devuelve la cartera completa agrupada por cliente.
    No altera la lógica de top5 usada por /cobranza/resumen_bot.
    """
    rut_col = _col_rut(df)
    clientes: dict[tuple[str, str | None], dict] = {}

    if df.empty or "Estado" not in df.columns:
        return {
            "total_clientes": 0,
            "total_documentos_pendientes": 0,
            "saldo_pendiente_total": 0,
            "cartera_vencida_total": 0,
            "cartera_no_vencida_total": 0,
            "sin_plazo_total": 0,
            "lista": [],
        }

    no_pagadas = df[~df["Estado"].apply(_estado_pagado)]

    for _, row in no_pagadas.iterrows():
        monto = _monto_pendiente(row)
        if monto <= 0:
            continue

        cliente = str(row.get(col_cliente, "—")).strip() or "—"
        rut = None
        if rut_col:
            rut_raw = row.get(rut_col)
            if pd.notna(rut_raw):
                rut_text = str(rut_raw).strip()
                if rut_text and rut_text.lower() != "nan":
                    rut = rut_text

        key = (cliente, rut)
        if key not in clientes:
            clientes[key] = {
                "cliente": cliente,
                "rut": rut,
                "saldo_pendiente": 0,
                "cartera_vencida": 0,
                "cartera_no_vencida": 0,
                "sin_plazo": 0,
                "documentos_pendientes": 0,
                "documentos_vencidos": 0,
                "max_dias_vencido": 0,
            }

        item = clientes[key]
        item["saldo_pendiente"] += monto
        item["documentos_pendientes"] += 1

        estado_vencimiento, fecha_vencimiento, dias_mora = _clasificar_vencimiento_doc(row, hoy)
        if estado_vencimiento == "sin_plazo":
            item["sin_plazo"] += monto
            continue

        if estado_vencimiento == "vencido":
            item["cartera_vencida"] += monto
            item["documentos_vencidos"] += 1
            item["max_dias_vencido"] = max(item["max_dias_vencido"], int(dias_mora or 0))
        else:
            item["cartera_no_vencida"] += monto

    lista = sorted(
        clientes.values(),
        key=lambda x: (-x["saldo_pendiente"], x["cliente"]),
    )

    return {
        "total_clientes": len(lista),
        "total_documentos_pendientes": sum(d["documentos_pendientes"] for d in lista),
        "saldo_pendiente_total": sum(d["saldo_pendiente"] for d in lista),
        "cartera_vencida_total": sum(d["cartera_vencida"] for d in lista),
        "cartera_no_vencida_total": sum(d["cartera_no_vencida"] for d in lista),
        "sin_plazo_total": sum(d["sin_plazo"] for d in lista),
        "lista": lista,
    }


# ── Clasificación única por documento ─────────────────────────────────

def _clasificar_docs(df: pd.DataFrame, fecha_corte: date) -> dict:
    """
    Clasifica cada documento en UNA categoría exclusiva:
      pagado | vencido | proximo_vencimiento | pendiente_no_vencido | sin_plazo
    Garantiza que ningún doc_id aparezca en dos categorías simultáneamente.
    """
    col = _col_razon(df)
    horizonte = fecha_corte + timedelta(days=7)

    vencidos, proximos, pendientes = [], [], []
    pagados = sin_plazo = 0
    ids_vencidos: set = set()
    ids_proximos: set = set()
    duplicados: list = []

    for _, row in df.iterrows():
        doc_id = str(row.get("doc_id", ""))
        cliente = str(row.get(col, "—"))
        monto = _monto_pendiente(row)
        mes = str(row.get("_mes_label", ""))

        if _estado_pagado(row.get("Estado")):
            pagados += 1
            continue

        if monto <= 0:
            continue

        estado_vencimiento, fecha_vencimiento, dias_mora = _clasificar_vencimiento_doc(row, fecha_corte)
        if estado_vencimiento == "sin_plazo":
            sin_plazo += 1
            continue

        if estado_vencimiento == "vencido":
            dias_vencida = int(dias_mora or 0)
            ids_vencidos.add(doc_id)
            vencidos.append({
                "cliente": cliente,
                "doc_id": doc_id,
                "monto": monto,
                "fecha_vencimiento": fecha_vencimiento.strftime("%d/%m/%Y"),
                "dias_vencida": dias_vencida,
                "mes": mes,
            })
        elif fecha_vencimiento <= horizonte:
            dias_restantes = (fecha_vencimiento - fecha_corte).days
            ids_proximos.add(doc_id)
            proximos.append({
                "cliente": cliente,
                "doc_id": doc_id,
                "monto": monto,
                "fecha_vencimiento": fecha_vencimiento.strftime("%d/%m/%Y"),
                "dias_restantes": dias_restantes,
                "mes": mes,
            })
        else:
            pendientes.append({
                "cliente": cliente,
                "doc_id": doc_id,
                "monto": monto,
                "fecha_vencimiento": fecha_vencimiento.strftime("%d/%m/%Y"),
            })

    # Validación: ningún doc_id en ambas listas
    duplicados_ids = ids_vencidos & ids_proximos
    if duplicados_ids:
        # Vencido tiene prioridad — lo eliminamos de próximos
        proximos = [d for d in proximos if d["doc_id"] not in duplicados_ids]
        duplicados = list(duplicados_ids)
        print(f"[WARN] Duplicados detectados y corregidos: {duplicados}")

    # Logs
    print(
        f"[LOG] Total docs: {len(df)} | Pagados: {pagados} | "
        f"Vencidos: {len(vencidos)} | Próximos 7d: {len(proximos)} | "
        f"Pendientes: {len(pendientes)} | Sin plazo: {sin_plazo} | "
        f"Duplicados corregidos: {len(duplicados)}"
    )

    return {
        "col": col,
        "vencidos": vencidos,
        "proximos": proximos,
        "pendientes": pendientes,
        "pagados": pagados,
        "sin_plazo": sin_plazo,
        "duplicados": duplicados,
        "total_docs": len(df),
    }


def _top5_vencidas(vencidos: list) -> list:
    """Top 5: mayor monto primero, luego mayor días vencida."""
    return sorted(vencidos, key=lambda x: (-x["monto"], -x["dias_vencida"]))[:5]


def _top5_proximos(proximos: list) -> list:
    """Top 5: score combinado — 60% monto alto + 40% urgencia (menos días)."""
    if not proximos:
        return []
    max_monto = max(d["monto"] for d in proximos) or 1

    def score(d):
        peso_monto = d["monto"] / max_monto * 0.6
        peso_urgencia = (7 - d["dias_restantes"]) / 7 * 0.4
        return -(peso_monto + peso_urgencia)

    return sorted(proximos, key=score)[:5]


def _prioridad_gestion(vencidos: list, proximos: list) -> list:
    """
    2-3 clientes prioritarios:
    1. Clientes con cartera vencida relevante (mayor monto y días)
    2. Si quedan slots: clientes con próximos vencimientos de alto monto
    Regla: nunca poner preventivos antes si hay cartera vencida real.
    """
    clientes_venc: dict = {}
    for d in vencidos:
        c = d["cliente"]
        if c not in clientes_venc:
            clientes_venc[c] = {"monto": 0, "max_dias": 0}
        clientes_venc[c]["monto"] += d["monto"]
        clientes_venc[c]["max_dias"] = max(clientes_venc[c]["max_dias"], d["dias_vencida"])

    prioridad = []
    for cliente, datos in sorted(clientes_venc.items(), key=lambda x: -x[1]["monto"])[:3]:
        urgencia = "ALTA" if datos["max_dias"] > 30 else "MEDIA"
        prioridad.append({
            "cliente": cliente,
            "razon": f"Cartera vencida ${datos['monto']:,} | {datos['max_dias']} días".replace(",", "."),
            "urgencia": urgencia,
        })

    # Completar con próximos de alto monto si quedan slots
    if len(prioridad) < 2:
        clientes_ya = {p["cliente"] for p in prioridad}
        for d in sorted(proximos, key=lambda x: -x["monto"]):
            if d["cliente"] not in clientes_ya and len(prioridad) < 3:
                prioridad.append({
                    "cliente": d["cliente"],
                    "razon": f"Vence en {d['dias_restantes']} días | ${d['monto']:,}".replace(",", "."),
                    "urgencia": "PREVENTIVA",
                })
                clientes_ya.add(d["cliente"])

    return prioridad[:3]


# ── Endpoints ──────────────────────────────────────────────────────────

@app.route("/cobranza/resumen")
def resumen():
    """Resumen original — mantiene compatibilidad. No modificar."""
    try:
        df = leer_todos_meses_abiertos_consolidado()
        if df.empty:
            return jsonify({"ok": False, "error": "Sin datos en SharePoint"}), 200

        col = _col_razon(df)
        no_pagadas = df[~df["Estado"].apply(_estado_pagado)]
        pagadas = df[df["Estado"].apply(_estado_pagado)]
        hoy = _fecha_corte_scl()

        vencidas, proximos = [], []
        for _, row in no_pagadas.iterrows():
            monto_abierto = _monto_pendiente(row)
            if monto_abierto <= 0:
                continue
            estado_vencimiento, fecha_vencimiento, dias_mora = _clasificar_vencimiento_doc(row, hoy)
            if estado_vencimiento == "sin_plazo" or fecha_vencimiento is None:
                continue
            dias = int(dias_mora or 0)
            dias_r = (fecha_vencimiento - hoy).days
            if dias >= 1:
                vencidas.append({"cliente": row.get(col, "—"), "doc_id": row["doc_id"],
                                  "monto": monto_abierto, "dias_vencida": dias,
                                  "mes": row.get("_mes_label", "")})
            elif 0 <= dias_r <= 7:
                proximos.append({"cliente": row.get(col, "—"), "doc_id": row["doc_id"],
                                  "monto": monto_abierto, "vence": fecha_vencimiento.strftime("%d/%m/%Y"),
                                  "dias_restantes": dias_r})

        dso = None
        if not pagadas.empty and "dias_cobro" in pagadas.columns:
            dso_vals = pagadas["dias_cobro"].dropna()
            if not dso_vals.empty:
                dso = round(float(dso_vals.mean()), 1)

        top_pendiente = []
        if not no_pagadas.empty:
            df_pend = no_pagadas.copy()
            df_pend["saldo_pendiente"] = df_pend.apply(_monto_pendiente, axis=1)
            df_pend = df_pend[df_pend["saldo_pendiente"] > 0]
            agrupado = df_pend.groupby(col)["saldo_pendiente"].sum().sort_values(ascending=False).head(10)
            top_pendiente = [{"cliente": c, "monto": int(m)} for c, m in agrupado.items()]

        return jsonify({
            "ok": True,
            "fecha_consulta": hoy.strftime("%d/%m/%Y"),
            "total_documentos": len(df),
            "meses_analizados": df["_mes_label"].unique().tolist(),
            "facturacion_total": int(df["Total"].sum()),
            "pendiente_total": int(no_pagadas.apply(_monto_pendiente, axis=1).sum()),
            "cobrado_total": int(pagadas["Total"].sum()),
            "pct_cobrado": round(pagadas["Total"].sum() / df["Total"].sum() * 100, 1) if df["Total"].sum() > 0 else 0,
            "dso_promedio_dias": dso,
            "top_pendiente_por_cliente": top_pendiente,
            "facturas_vencidas": sorted(vencidas, key=lambda x: -x["dias_vencida"])[:20],
            "proximos_vencimientos_7dias": sorted(proximos, key=lambda x: x["dias_restantes"]),
        })

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/cobranza/resumen_bot")
def resumen_bot():
    """
    Endpoint optimizado para bot Telegram.
    Clasificación única por documento — ningún doc_id aparece en dos listas.
    Zona horaria: America/Santiago.
    """
    try:
        df = leer_todos_meses_abiertos_consolidado()
        if df.empty:
            return jsonify({"error": "Sin datos en SharePoint"}), 200

        col = _col_razon(df)
        rut_col = _col_rut(df)
        hoy = _fecha_corte_scl()
        horizonte = hoy + timedelta(days=7)

        pagadas = df[df["Estado"].apply(_estado_pagado)]
        no_pagadas = df[~df["Estado"].apply(_estado_pagado)]

        # ── DSO ────────────────────────────────────────────────────────
        dso = None
        if not pagadas.empty and "dias_cobro" in pagadas.columns:
            vals = pagadas["dias_cobro"].dropna()
            if not vals.empty:
                dso = round(float(vals.mean()), 1)

        # ── Clasificación única por documento ──────────────────────────
        vencidos, proximos, pendientes, sin_plazo_docs = [], [], [], []
        documentos_pendientes_detalle, documentos_vencidos_detalle, documentos_no_vencidos_detalle = [], [], []
        ids_vencidos: set = set()

        for _, row in no_pagadas.iterrows():
            saldo_pendiente = _monto_pendiente(row)
            if saldo_pendiente <= 0:
                continue

            doc_id        = str(row.get("doc_id", ""))
            cliente       = str(row.get(col, "—"))
            monto_factura = _monto_original(row)
            estado_vencimiento, fecha_vencimiento, dias_mora = _clasificar_vencimiento_doc(row, hoy)
            doc_detalle = _build_documento_detalle(row, hoy, col, rut_col)
            if doc_detalle is None:
                continue
            documentos_pendientes_detalle.append(doc_detalle)

            if estado_vencimiento == "sin_plazo":
                doc_detalle["dias_mora"] = None
                sin_plazo_docs.append({
                    "doc_id": doc_id,
                    "cliente": cliente,
                    "saldo_pendiente": saldo_pendiente,
                    "monto_factura": monto_factura,
                })
                continue

            if estado_vencimiento == "vencido":
                ids_vencidos.add(doc_id)
                documentos_vencidos_detalle.append(doc_detalle)
                vencidos.append({
                    "doc_id":        doc_id,
                    "cliente":       cliente,
                    "saldo_vencido": saldo_pendiente,
                    "saldo_pendiente": saldo_pendiente,
                    "monto_factura": monto_factura,   # col J — total original
                    "fecha_vencimiento": fecha_vencimiento.isoformat(),
                    "dias_vencido":  int(dias_mora or 0),
                })
            elif fecha_vencimiento <= horizonte:
                documentos_no_vencidos_detalle.append(doc_detalle)
                dias_rest = (fecha_vencimiento - hoy).days
                proximos.append({
                    "doc_id":            doc_id,
                    "cliente":           cliente,
                    "monto":             saldo_pendiente,
                    "saldo_pendiente":   saldo_pendiente,
                    "monto_factura":     monto_factura,
                    "fecha_vencimiento": fecha_vencimiento.isoformat(),
                    "dias_restantes":    dias_rest,
                    "score_prioridad":   int(saldo_pendiente / (dias_rest + 1)),
                })
            else:
                documentos_no_vencidos_detalle.append(doc_detalle)
                pendientes.append({
                    "cliente": cliente,
                    "monto": saldo_pendiente,
                    "saldo_pendiente": saldo_pendiente,
                    "monto_factura": monto_factura,
                })

        # Validación: vencido tiene prioridad sobre próximo
        proximos = [d for d in proximos if d["doc_id"] not in ids_vencidos]
        cross = ids_vencidos & {d["doc_id"] for d in proximos}
        if cross:
            print(f"[WARN] Duplicados residuales eliminados: {cross}")

        # Logs
        print(
            f"[LOG] docs={len(df)} | pagados={len(pagadas)} | "
            f"vencidos={len(vencidos)} | proximos={len(proximos)} | "
            f"pendientes={len(pendientes)} | sin_plazo={len(sin_plazo_docs)} | "
            f"duplicados={len(cross)}"
        )

        # ── Top 5 vencidos: mayor saldo_vencido → mayor días ──────────
        top5_v = sorted(vencidos, key=lambda x: (-x["saldo_vencido"], -x["dias_vencido"]))[:5]

        # ── Top 5 próximos: mayor score_prioridad (monto / días+1) ────
        top5_p = sorted(proximos, key=lambda x: -x["score_prioridad"])[:5]

        # ── Mayor exposición total por cliente ─────────────────────────
        exp: dict = {}
        for d in vencidos:
            exp[d["cliente"]] = exp.get(d["cliente"], 0) + d["saldo_vencido"]
        for d in proximos + pendientes:
            exp[d["cliente"]] = exp.get(d["cliente"], 0) + d["saldo_pendiente"]
        for d in sin_plazo_docs:
            exp[d["cliente"]] = exp.get(d["cliente"], 0) + d["saldo_pendiente"]
        top5_exp = sorted(
            [{"cliente": cl, "saldo_pendiente": m} for cl, m in exp.items()],
            key=lambda x: -x["saldo_pendiente"]
        )[:5]

        def _sort_detalle_key(d: dict):
            return (
                0 if d["estado_vencimiento"] == "vencido" else 1 if d["estado_vencimiento"] == "no_vencido" else 2,
                -(d["dias_mora"] or 0),
                -d["saldo_pendiente_doc"],
                d["cliente"],
                d["cto"],
            )

        documentos_pendientes_detalle = sorted(documentos_pendientes_detalle, key=_sort_detalle_key)
        documentos_vencidos_detalle = sorted(
            documentos_vencidos_detalle,
            key=lambda d: (-d["vencido_doc"], -(d["dias_mora"] or 0), d["cliente"], d["cto"]),
        )
        documentos_no_vencidos_detalle = sorted(
            documentos_no_vencidos_detalle,
            key=lambda d: (-d["no_vencido_doc"], d["fecha_vencimiento"] or "9999-12-31", d["cliente"], d["cto"]),
        )

        # ── Prioridad gestión ──────────────────────────────────────────
        clientes_venc: dict = {}
        for d in vencidos:
            cv_key = d["cliente"]
            if cv_key not in clientes_venc:
                clientes_venc[cv_key] = {"saldo": 0, "max_dias": 0}
            clientes_venc[cv_key]["saldo"]   += d["saldo_vencido"]
            clientes_venc[cv_key]["max_dias"] = max(clientes_venc[cv_key]["max_dias"], d["dias_vencido"])

        prioridad = []
        for cliente, datos in sorted(clientes_venc.items(), key=lambda x: -x[1]["saldo"])[:3]:
            prioridad.append({
                "cliente": cliente,
                "motivo":  "cartera vencida relevante",
                "tipo":    "urgente",
            })

        if len(prioridad) < 2:
            ya = {p["cliente"] for p in prioridad}
            for d in sorted(proximos, key=lambda x: -x["score_prioridad"]):
                if d["cliente"] not in ya and len(prioridad) < 3:
                    prioridad.append({
                        "cliente": d["cliente"],
                        "motivo":  f"vence en {d['dias_restantes']} días, monto relevante",
                        "tipo":    "preventivo",
                    })
                    ya.add(d["cliente"])

        # ── Cartera completa por cliente ───────────────────────────────
        clientes_cartera = _clientes_cartera(df, hoy, col)
        print(
            "[LOG] clientes_cartera | "
            f"clientes={clientes_cartera['total_clientes']} | "
            f"docs={clientes_cartera['total_documentos_pendientes']} | "
            f"saldo={clientes_cartera['saldo_pendiente_total']} | "
            f"vencida={clientes_cartera['cartera_vencida_total']} | "
            f"no_vencida={clientes_cartera['cartera_no_vencida_total']} | "
            f"sin_plazo={clientes_cartera['sin_plazo_total']}"
        )

        docs_por_cliente_map: dict[tuple[str, str], dict] = {}
        for d in documentos_pendientes_detalle:
            key = (d["cliente"], d["rut"])
            bucket = docs_por_cliente_map.setdefault(
                key,
                {
                    "cliente": d["cliente"],
                    "rut": d["rut"],
                    "pendiente": 0,
                    "vencida": 0,
                    "no_vencida": 0,
                    "sin_plazo": 0,
                    "documentos_pendientes": 0,
                    "documentos_vencidos": 0,
                    "detalle": [],
                },
            )
            bucket["pendiente"] += d["saldo_pendiente_doc"]
            bucket["vencida"] += d["vencido_doc"]
            bucket["no_vencida"] += d["no_vencido_doc"]
            bucket["sin_plazo"] += d["sin_plazo_doc"]
            bucket["documentos_pendientes"] += 1
            if d["estado_vencimiento"] == "vencido":
                bucket["documentos_vencidos"] += 1
            bucket["detalle"].append(d)

        documentos_por_cliente = []
        for item in clientes_cartera["lista"]:
            key = (item["cliente"], item.get("rut") or "")
            bucket = docs_por_cliente_map.get(key)
            if not bucket:
                continue
            bucket["detalle"] = sorted(bucket["detalle"], key=_sort_detalle_key)
            documentos_por_cliente.append(bucket)

        # ── Respuesta ──────────────────────────────────────────────────
        total_vencido = sum(d["saldo_vencido"] for d in vencidos)
        total_proximos = sum(d["saldo_pendiente"] for d in proximos)
        total_pend = sum(d["saldo_pendiente"] for d in pendientes)
        total_sin_plazo = sum(d["saldo_pendiente"] for d in sin_plazo_docs)
        total_no_vencido = total_proximos + total_pend

        return jsonify({
            "fecha_consulta":    hoy.strftime("%d/%m/%Y"),
            "total_pendiente":   total_vencido + total_no_vencido + total_sin_plazo,
            "dso_promedio_dias": dso,
            "cartera_vencida": {
                "total":               total_vencido,
                "cantidad_documentos": len(vencidos),
                "top5":                top5_v,
            },
            "cartera_no_vencida": {
                "total":               total_no_vencido,
                "cantidad_documentos": len(proximos) + len(pendientes),
            },
            "proximos_vencimientos": {
                "horizonte_dias":      7,
                "total":               total_proximos,
                "cantidad_documentos": len(proximos),
                "top5":                top5_p,
            },
            "sin_plazo": {
                "total":               total_sin_plazo,
                "cantidad_documentos": len(sin_plazo_docs),
            },
            "mayor_exposicion_total": {
                "top5": top5_exp,
            },
            "prioridad_gestion": prioridad,
            "clientes_cartera": clientes_cartera,
            "documentos_pendientes_detalle": documentos_pendientes_detalle,
            "documentos_vencidos_detalle": documentos_vencidos_detalle,
            "documentos_no_vencidos_detalle": documentos_no_vencidos_detalle,
            "documentos_por_cliente": documentos_por_cliente,
        })

    except Exception as e:
        print(f"[FALLO] /cobranza/resumen_bot: {traceback.format_exc()}")
        return jsonify({"error": str(e)}), 500


@app.route("/clientes/info")
def cliente_info():
    """
    GET /clientes/info?chat_id=123456
    Retorna registro del cliente desde SQLite.
    Usado por n8n para verificar autorización antes de mostrar datos.
    """
    from flask import request as freq
    from db_manager import get_cliente
    chat_id_raw = freq.args.get("chat_id", "")
    if not chat_id_raw:
        return jsonify({"autorizado": False, "error": "chat_id requerido"}), 400
    try:
        cliente = get_cliente(int(chat_id_raw))
        if cliente:
            return jsonify({
                "autorizado":   True,
                "chat_id":      cliente["chat_id"],
                "nombre":       cliente["nombre"],
                "empresa":      cliente["empresa"],
                "rut_cliente":  cliente["rut_cliente"],
            })
        return jsonify({"autorizado": False})
    except Exception as e:
        return jsonify({"autorizado": False, "error": str(e)}), 500


@app.route("/cobranza/resumen_cliente")
def resumen_cliente():
    """
    GET /cobranza/resumen_cliente?rut=77.767.415-0
    Datos financieros filtrados EXCLUSIVAMENTE para ese RUT.
    Barrera 1 de aislamiento — nunca devuelve datos de otro cliente.
    """
    from flask import request as freq
    rut = freq.args.get("rut", "").strip()
    if not rut:
        return jsonify({"error": "rut requerido"}), 400

    try:
        df_total = leer_todos_meses_abiertos_consolidado()
        if df_total.empty:
            return jsonify({"error": "Sin datos en SharePoint"}), 200

        df = filtrar_por_rut(df_total, rut)
        if df.empty:
            return jsonify({
                "rut":             rut,
                "empresa":         "—",
                "sin_datos":       True,
                "mensaje":         "No se encontraron documentos para este RUT en el período activo.",
            })

        col      = _col_razon(df)
        empresa  = str(df[col].iloc[0]) if not df.empty else "—"
        hoy      = _fecha_corte_scl()
        horizonte = hoy + timedelta(days=30)   # ventana 30 días para clientes

        pagadas = df[df["Estado"].apply(_estado_pagado)]
        no_pagadas = df[~df["Estado"].apply(_estado_pagado)]

        dso = None
        if not pagadas.empty and "dias_cobro" in pagadas.columns:
            vals = pagadas["dias_cobro"].dropna()
            if not vals.empty:
                dso = round(float(vals.mean()), 1)

        vencidos, proximos, no_vencidos, sin_plazo_docs, documentos_detalle = [], [], [], [], []
        ids_vencidos: set = set()

        for _, row in no_pagadas.iterrows():
            saldo_pendiente = _monto_pendiente(row)
            if saldo_pendiente <= 0:
                continue

            doc_id        = str(row.get("doc_id", ""))
            monto_factura = _monto_original(row)
            estado_vencimiento, fecha_vencimiento, dias_mora = _clasificar_vencimiento_doc(row, hoy)
            fecha_emision = _fecha_base_date(row.get("Fecha"))
            dias_restantes = None if fecha_vencimiento is None else (fecha_vencimiento - hoy).days

            documentos_detalle.append({
                "doc_id": doc_id,
                "tipo_doc": int(pd.to_numeric(row.get("Tipo Doc", 0), errors="coerce") or 0),
                "cto": int(pd.to_numeric(row.get("Cto", 0), errors="coerce") or 0),
                "estado": str(row.get("Estado", "")).strip(),
                "monto_factura": monto_factura,
                "saldo_pendiente": saldo_pendiente,
                "fecha_emision": fecha_emision.strftime("%d/%m/%Y") if fecha_emision else None,
                "fecha_vencimiento": fecha_vencimiento.strftime("%d/%m/%Y") if fecha_vencimiento else None,
                "estado_vencimiento": estado_vencimiento,
                "dias_mora": int(dias_mora) if dias_mora is not None else None,
                "dias_restantes": int(dias_restantes) if dias_restantes is not None else None,
            })

            if estado_vencimiento == "sin_plazo":
                sin_plazo_docs.append({
                    "doc_id": doc_id,
                    "saldo_pendiente": saldo_pendiente,
                    "monto_factura": monto_factura,
                })
                continue

            if estado_vencimiento == "vencido":
                ids_vencidos.add(doc_id)
                vencidos.append({
                    "doc_id":        doc_id,
                    "saldo_vencido": saldo_pendiente,
                    "saldo_pendiente": saldo_pendiente,
                    "monto_factura": monto_factura,
                    "dias_vencido":  int(dias_mora or 0),
                    "fecha_emision": fecha_emision.strftime("%d/%m/%Y") if fecha_emision else None,
                    "fecha_vencimiento": fecha_vencimiento.strftime("%d/%m/%Y"),
                })
                continue

            no_vencidos.append({
                "doc_id": doc_id,
                "saldo_pendiente": saldo_pendiente,
                "monto_factura": monto_factura,
                "fecha_vencimiento": fecha_vencimiento.strftime("%d/%m/%Y"),
                "dias_restantes": int(dias_restantes or 0),
            })
            if fecha_vencimiento <= horizonte:
                dias_rest = (fecha_vencimiento - hoy).days
                proximos.append({
                    "doc_id":            doc_id,
                    "monto":             saldo_pendiente,
                    "saldo_pendiente":   saldo_pendiente,
                    "monto_factura":     monto_factura,
                    "dias_restantes":    dias_rest,
                    "fecha_vencimiento": fecha_vencimiento.strftime("%d/%m/%Y"),
                    "score":             int(saldo_pendiente / (dias_rest + 1)),
                })

        proximos = [d for d in proximos if d["doc_id"] not in ids_vencidos]

        print(
            f"[LOG] resumen_cliente rut={rut} | empresa={empresa} | "
            f"vencidos={len(vencidos)} | proximos={len(proximos)}"
        )

        return jsonify({
            "rut":     rut,
            "empresa": empresa,
            "fecha_consulta": hoy.strftime("%d/%m/%Y"),
            "dso_promedio_dias": dso,
            "documentos_pendientes": {
                "cantidad_documentos": len(documentos_detalle),
                "documentos": sorted(
                    documentos_detalle,
                    key=lambda x: (
                        0 if x["estado_vencimiento"] == "vencido" else 1 if x["estado_vencimiento"] == "no_vencido" else 2,
                        -(x["dias_mora"] or _DIAS_MORA_SORT_DEFAULT),
                        -(x["saldo_pendiente"] or 0),
                    ),
                ),
            },
            "cartera_vencida": {
                "total":               sum(d["saldo_vencido"] for d in vencidos),
                "cantidad_documentos": len(vencidos),
                "documentos":          sorted(vencidos, key=lambda x: (-x["saldo_vencido"], -x["dias_vencido"])),
            },
            "cartera_no_vencida": {
                "total":               sum(d["saldo_pendiente"] for d in no_vencidos),
                "cantidad_documentos": len(no_vencidos),
            },
            "proximos_vencimientos": {
                "horizonte_dias":      30,
                "total":               sum(d["saldo_pendiente"] for d in proximos),
                "cantidad_documentos": len(proximos),
                "documentos":          sorted(proximos, key=lambda x: (-x["score"], x["dias_restantes"])),
            },
            "sin_plazo": {
                "total":               sum(d["saldo_pendiente"] for d in sin_plazo_docs),
                "cantidad_documentos": len(sin_plazo_docs),
            },
            "total_pendiente": sum(d["saldo_pendiente"] for d in documentos_detalle),
        })

    except Exception as e:
        print(f"[FALLO] /cobranza/resumen_cliente: {traceback.format_exc()}")
        return jsonify({"error": str(e)}), 500


@app.route("/cobranza/proyeccion_caja")
def proyeccion_caja():
    """
    GET /cobranza/proyeccion_caja
    Proyección de cobros futuros agrupados por semana (4 semanas) y mes.
    Solo incluye facturas pendientes NO vencidas — las vencidas están en /resumen_bot.
    """
    try:
        df = leer_todos_meses_abiertos_consolidado()
        if df.empty:
            return jsonify({"error": "Sin datos en SharePoint"}), 200

        hoy = _fecha_corte_scl()
        col = _col_razon(df)
        no_pagadas = df[~df["Estado"].apply(_estado_pagado)]

        _SEMANAS = [
            {"n": 1, "label": "Esta semana",  "d0": 0,  "d1": 6},
            {"n": 2, "label": "Semana 2",     "d0": 7,  "d1": 13},
            {"n": 3, "label": "Semana 3",     "d0": 14, "d1": 20},
            {"n": 4, "label": "Semana 4",     "d0": 21, "d1": 27},
        ]
        buckets: dict[int, list] = {s["n"]: [] for s in _SEMANAS}
        posterior: list = []
        por_mes: dict[str, dict] = {}
        total_sin_vencer = 0

        for _, row in no_pagadas.iterrows():
            monto = _monto_pendiente(row)
            if monto <= 0:
                continue
            estado_vencimiento, fecha_vencimiento, _dias_mora = _clasificar_vencimiento_doc(row, hoy)
            if estado_vencimiento != "no_vencido" or fecha_vencimiento is None:
                continue  # vencida — excluida (usar /resumen_bot)

            dias = (fecha_vencimiento - hoy).days
            doc_id  = str(row.get("doc_id", ""))
            cliente = str(row.get(col, "—"))
            total_sin_vencer += monto

            entry = {
                "doc_id": doc_id,
                "cliente": cliente,
                "monto": monto,
                "saldo_pendiente": monto,
                "monto_factura": _monto_original(row),
                "fecha_vencimiento": fecha_vencimiento.isoformat(),
                "dias_restantes": dias,
            }

            colocado = False
            for s in _SEMANAS:
                if s["d0"] <= dias <= s["d1"]:
                    buckets[s["n"]].append(entry)
                    colocado = True
                    break
            if not colocado:
                posterior.append(entry)

            mes_key = f"{fecha_vencimiento.year}-{fecha_vencimiento.month:02d}"
            if mes_key not in por_mes:
                por_mes[mes_key] = {
                    "mes_key": mes_key,
                    "mes": f"{_MESES_SP[fecha_vencimiento.month]} {fecha_vencimiento.year}",
                    "total": 0, "cantidad": 0,
                }
            por_mes[mes_key]["total"]    += monto
            por_mes[mes_key]["cantidad"] += 1

        semanas_resp = []
        for s in _SEMANAS:
            docs = buckets[s["n"]]
            fecha_ini = hoy + timedelta(days=s["d0"])
            fecha_fin = hoy + timedelta(days=s["d1"])
            semanas_resp.append({
                "semana": s["n"],
                "label": f"{s['label']} ({fecha_ini.strftime('%d/%m')}–{fecha_fin.strftime('%d/%m')})",
                "fecha_inicio": fecha_ini.isoformat(),
                "fecha_fin":    fecha_fin.isoformat(),
                "total":               sum(d["monto"] for d in docs),
                "cantidad_documentos": len(docs),
                "top5": sorted(docs, key=lambda x: -x["monto"])[:5],
            })

        print(
            f"[LOG] proyeccion_caja | total_sin_vencer={total_sin_vencer} | "
            f"semanas={[len(buckets[s['n']]) for s in _SEMANAS]} | posterior={len(posterior)}"
        )

        return jsonify({
            "fecha_consulta":         hoy.strftime("%d/%m/%Y"),
            "total_pendiente_sin_vencer": total_sin_vencer,
            "semanas":                semanas_resp,
            "posterior_4_semanas": {
                "total":               sum(d["monto"] for d in posterior),
                "cantidad_documentos": len(posterior),
                "top5": sorted(posterior, key=lambda x: -x["monto"])[:5],
            },
            "por_mes": [v for _, v in sorted(por_mes.items())],
        })

    except Exception as e:
        print(f"[FALLO] /cobranza/proyeccion_caja: {traceback.format_exc()}")
        return jsonify({"error": str(e)}), 500


@app.route("/health")
def health():
    return jsonify({"status": "ok", "servicio": "api_cobranza Egakat",
                    "endpoints": ["/cobranza/resumen", "/cobranza/resumen_bot",
                                  "/cobranza/proyeccion_caja",
                                  "/cobranza/resumen_cliente", "/clientes/info"]})


if __name__ == "__main__":
    # Validar configuración crítica al inicio
    if not os.getenv("API_COBRANZA_SECRET"):
        print("[FALLO] API_COBRANZA_SECRET no configurado en .env")
        print("        Generar secret: python -c 'import secrets; print(secrets.token_hex(16))'")
        sys.exit(1)

    port = int(os.getenv("API_COBRANZA_PORT", 8080))
    print(f"[INFO] API Cobranza Egakat corriendo en http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
