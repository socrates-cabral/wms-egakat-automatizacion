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
        monto = int(row.get("Total", 0))
        mes = str(row.get("_mes_label", ""))

        if str(row.get("Estado", "")).strip() == "Pagado":
            pagados += 1
            continue

        if pd.isna(row.get("Fecha")):
            sin_plazo += 1
            continue

        plazo = _detectar_plazo(row.get("Forma de Pago", ""))
        if plazo is None:
            sin_plazo += 1
            continue

        fv = row["Fecha"].date() + timedelta(days=plazo)

        if fv < fecha_corte:
            dias_vencida = (fecha_corte - fv).days
            ids_vencidos.add(doc_id)
            vencidos.append({
                "cliente": cliente,
                "doc_id": doc_id,
                "monto": monto,
                "fecha_vencimiento": fv.strftime("%d/%m/%Y"),
                "dias_vencida": dias_vencida,
                "mes": mes,
            })
        elif fv <= horizonte:
            dias_restantes = (fv - fecha_corte).days
            ids_proximos.add(doc_id)
            proximos.append({
                "cliente": cliente,
                "doc_id": doc_id,
                "monto": monto,
                "fecha_vencimiento": fv.strftime("%d/%m/%Y"),
                "dias_restantes": dias_restantes,
                "mes": mes,
            })
        else:
            pendientes.append({
                "cliente": cliente,
                "doc_id": doc_id,
                "monto": monto,
                "fecha_vencimiento": fv.strftime("%d/%m/%Y"),
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
        no_pagadas = df[df["Estado"] == "NO Pagado"]
        pagadas = df[df["Estado"] == "Pagado"]
        hoy = _fecha_corte_scl()

        vencidas, proximos = [], []
        for _, row in no_pagadas.iterrows():
            if pd.isna(row["Fecha"]):
                continue
            plazo = _detectar_plazo(row.get("Forma de Pago", ""))
            if not plazo:
                continue
            fv = row["Fecha"].date() + timedelta(days=plazo)
            dias = (hoy - fv).days
            dias_r = (fv - hoy).days
            if dias >= 1:
                vencidas.append({"cliente": row.get(col, "—"), "doc_id": row["doc_id"],
                                  "monto": int(row["Total"]), "dias_vencida": dias,
                                  "mes": row.get("_mes_label", "")})
            elif 0 <= dias_r <= 7:
                proximos.append({"cliente": row.get(col, "—"), "doc_id": row["doc_id"],
                                  "monto": int(row["Total"]), "vence": fv.strftime("%d/%m/%Y"),
                                  "dias_restantes": dias_r})

        dso = None
        if not pagadas.empty and "dias_cobro" in pagadas.columns:
            dso_vals = pagadas["dias_cobro"].dropna()
            if not dso_vals.empty:
                dso = round(float(dso_vals.mean()), 1)

        top_pendiente = []
        if not no_pagadas.empty:
            agrupado = no_pagadas.groupby(col)["Total"].sum().sort_values(ascending=False).head(10)
            top_pendiente = [{"cliente": c, "monto": int(m)} for c, m in agrupado.items()]

        return jsonify({
            "ok": True,
            "fecha_consulta": hoy.strftime("%d/%m/%Y"),
            "total_documentos": len(df),
            "meses_analizados": df["_mes_label"].unique().tolist(),
            "facturacion_total": int(df["Total"].sum()),
            "pendiente_total": int(no_pagadas["Total"].sum()),
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
        hoy = _fecha_corte_scl()
        horizonte = hoy + timedelta(days=7)

        pagadas = df[df["Estado"] == "Pagado"]
        no_pagadas = df[df["Estado"] != "Pagado"]

        # ── DSO ────────────────────────────────────────────────────────
        dso = None
        if not pagadas.empty and "dias_cobro" in pagadas.columns:
            vals = pagadas["dias_cobro"].dropna()
            if not vals.empty:
                dso = round(float(vals.mean()), 1)

        # ── Clasificación única por documento ──────────────────────────
        vencidos, proximos, pendientes = [], [], []
        ids_vencidos: set = set()

        for _, row in no_pagadas.iterrows():
            if pd.isna(row.get("Fecha")):
                continue
            plazo = _detectar_plazo(row.get("Forma de Pago", ""))
            if plazo is None:
                continue

            doc_id        = str(row.get("doc_id", ""))
            cliente       = str(row.get(col, "—"))
            monto_factura = int(pd.to_numeric(row.get("Total", 0), errors="coerce") or 0)
            # BUG 1: usar Saldo (col T) como saldo real pendiente
            saldo_raw     = pd.to_numeric(row.get("Saldo", row.get("Total", 0)), errors="coerce")
            saldo_vencido = int(saldo_raw if pd.notna(saldo_raw) and saldo_raw > 0 else monto_factura)
            fv            = row["Fecha"].date() + timedelta(days=plazo)

            if fv < hoy:
                ids_vencidos.add(doc_id)
                vencidos.append({
                    "doc_id":        doc_id,
                    "cliente":       cliente,
                    "saldo_vencido": saldo_vencido,   # col T — saldo real
                    "monto_factura": monto_factura,   # col J — total original
                    "dias_vencido":  (hoy - fv).days,
                })
            elif fv <= horizonte:
                dias_rest = (fv - hoy).days
                proximos.append({
                    "doc_id":            doc_id,
                    "cliente":           cliente,
                    "monto":             monto_factura,
                    "fecha_vencimiento": fv.isoformat(),
                    "dias_restantes":    dias_rest,
                    # BUG 2: score combinado — prioriza alto monto aunque no venza hoy
                    "score_prioridad":   int(monto_factura / (dias_rest + 1)),
                })
            else:
                pendientes.append({"cliente": cliente, "monto": monto_factura})

        # Validación: vencido tiene prioridad sobre próximo
        proximos = [d for d in proximos if d["doc_id"] not in ids_vencidos]
        cross = ids_vencidos & {d["doc_id"] for d in proximos}
        if cross:
            print(f"[WARN] Duplicados residuales eliminados: {cross}")

        # Logs
        print(
            f"[LOG] docs={len(df)} | pagados={len(pagadas)} | "
            f"vencidos={len(vencidos)} | proximos={len(proximos)} | "
            f"pendientes={len(pendientes)} | duplicados={len(cross)}"
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
            exp[d["cliente"]] = exp.get(d["cliente"], 0) + d["monto"]
        top5_exp = sorted(
            [{"cliente": cl, "saldo_pendiente": m} for cl, m in exp.items()],
            key=lambda x: -x["saldo_pendiente"]
        )[:5]

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

        # ── Respuesta ──────────────────────────────────────────────────
        total_vencido  = sum(d["saldo_vencido"] for d in vencidos)
        total_proximos = sum(d["monto"] for d in proximos)
        total_pend     = sum(d["monto"] for d in pendientes)

        return jsonify({
            "fecha_consulta":    hoy.strftime("%d/%m/%Y"),
            "total_pendiente":   total_vencido + total_proximos + total_pend,
            "dso_promedio_dias": dso,
            "cartera_vencida": {
                "total":               total_vencido,
                "cantidad_documentos": len(vencidos),
                "top5":                top5_v,
            },
            "proximos_vencimientos": {
                "horizonte_dias":      7,
                "total":               total_proximos,
                "cantidad_documentos": len(proximos),
                "top5":                top5_p,
            },
            "mayor_exposicion_total": {
                "top5": top5_exp,
            },
            "prioridad_gestion": prioridad,
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

        pagadas   = df[df["Estado"] == "Pagado"]
        no_pagadas = df[df["Estado"] != "Pagado"]

        dso = None
        if not pagadas.empty and "dias_cobro" in pagadas.columns:
            vals = pagadas["dias_cobro"].dropna()
            if not vals.empty:
                dso = round(float(vals.mean()), 1)

        vencidos, proximos = [], []
        ids_vencidos: set = set()

        for _, row in no_pagadas.iterrows():
            if pd.isna(row.get("Fecha")):
                continue
            plazo = _detectar_plazo(row.get("Forma de Pago", ""))
            if plazo is None:
                continue

            doc_id        = str(row.get("doc_id", ""))
            monto_factura = int(pd.to_numeric(row.get("Total", 0), errors="coerce") or 0)
            saldo_raw     = pd.to_numeric(row.get("Saldo", row.get("Total", 0)), errors="coerce")
            saldo_vencido = int(saldo_raw if pd.notna(saldo_raw) and saldo_raw > 0 else monto_factura)
            fv            = row["Fecha"].date() + timedelta(days=plazo)

            if fv < hoy:
                ids_vencidos.add(doc_id)
                vencidos.append({
                    "doc_id":        doc_id,
                    "saldo_vencido": saldo_vencido,
                    "monto_factura": monto_factura,
                    "dias_vencido":  (hoy - fv).days,
                    "fecha_emision": row["Fecha"].strftime("%d/%m/%Y"),
                    "fecha_vencimiento": fv.strftime("%d/%m/%Y"),
                })
            elif fv <= horizonte:
                dias_rest = (fv - hoy).days
                proximos.append({
                    "doc_id":            doc_id,
                    "monto":             monto_factura,
                    "dias_restantes":    dias_rest,
                    "fecha_vencimiento": fv.isoformat(),
                    "score":             int(monto_factura / (dias_rest + 1)),
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
            "cartera_vencida": {
                "total":               sum(d["saldo_vencido"] for d in vencidos),
                "cantidad_documentos": len(vencidos),
                "documentos":          sorted(vencidos, key=lambda x: (-x["saldo_vencido"], -x["dias_vencido"])),
            },
            "proximos_vencimientos": {
                "horizonte_dias":      30,
                "total":               sum(d["monto"] for d in proximos),
                "cantidad_documentos": len(proximos),
                "documentos":          sorted(proximos, key=lambda x: -x["score"]),
            },
            "total_pendiente": (
                sum(d["saldo_vencido"] for d in vencidos) +
                sum(d["monto"] for d in proximos)
            ),
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
        no_pagadas = df[df["Estado"] != "Pagado"]

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
            if pd.isna(row.get("Fecha")):
                continue
            plazo = _detectar_plazo(row.get("Forma de Pago", ""))
            if plazo is None:
                continue
            fv = row["Fecha"].date() + timedelta(days=plazo)
            if fv < hoy:
                continue  # vencida — excluida (usar /resumen_bot)

            dias = (fv - hoy).days
            doc_id  = str(row.get("doc_id", ""))
            cliente = str(row.get(col, "—"))
            monto   = int(pd.to_numeric(row.get("Total", 0), errors="coerce") or 0)
            total_sin_vencer += monto

            entry = {
                "doc_id": doc_id,
                "cliente": cliente,
                "monto": monto,
                "fecha_vencimiento": fv.isoformat(),
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

            mes_key = f"{fv.year}-{fv.month:02d}"
            if mes_key not in por_mes:
                por_mes[mes_key] = {
                    "mes_key": mes_key,
                    "mes": f"{_MESES_SP[fv.month]} {fv.year}",
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
    port = int(os.getenv("API_COBRANZA_PORT", 8080))
    print(f"[INFO] API Cobranza Egakat corriendo en http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
