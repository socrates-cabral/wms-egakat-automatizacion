from __future__ import annotations
import sys
sys.stdout.reconfigure(encoding="utf-8")

import html
from datetime import datetime
from typing import Any

_C = {
    "verde":   "#27ae60",
    "naranja": "#e67e22",
    "rojo":    "#c0392b",
    "gris_h":  "#2c3e50",
    "gris_t":  "#7f8c8d",
    "gris_b":  "#ecf0f1",
    "gris_bd": "#bdc3c7",
    "chip_ok_bg":    "#d5f5e3",
    "chip_ok_txt":   "#1e8449",
    "chip_warn_bg":  "#fdebd0",
    "chip_warn_txt": "#a04000",
    "chip_fail_bg":  "#fadbd8",
    "chip_fail_txt": "#922b21",
    "chip_info_bg":  "#d6eaf8",
    "chip_info_txt": "#1b4f72",
}

_MESES_ES = {
    1:"Enero", 2:"Febrero", 3:"Marzo", 4:"Abril", 5:"Mayo", 6:"Junio",
    7:"Julio", 8:"Agosto", 9:"Septiembre", 10:"Octubre", 11:"Noviembre", 12:"Diciembre",
}

_DIAS_ES = {
    0:"Lunes", 1:"Martes", 2:"Miércoles", 3:"Jueves",
    4:"Viernes", 5:"Sábado", 6:"Domingo",
}


def determinar_estado(resumen: dict) -> str:
    if resumen.get("errores"):
        return "FALLOS"
    estados = [s for (_, _, s) in resumen.get("meses_procesados", [])]
    if any(e == "FALLO" for e in estados):
        return "FALLOS"
    if any(e == "SKIP" for e in estados):
        return "ADVERTENCIAS"
    return "OK"


def build_asunto(resumen: dict, fecha: datetime | None = None) -> str:
    fecha = fecha or datetime.now()
    estado = determinar_estado(resumen)
    n = resumen.get("total_eventos", 0)
    fecha_str = fecha.strftime("%d/%m/%Y")
    etiqueta = {"OK": "Proceso OK", "ADVERTENCIAS": "Con advertencias", "FALLOS": "Con fallos"}[estado]
    sufijo = f" — {n} cambios detectados" if n else " — sin cambios"
    return f"[Softnet Ventas] {etiqueta} {fecha_str}{sufijo}"


def build_html(resumen: dict, fecha: datetime | None = None) -> str:
    fecha = fecha or datetime.now()
    estado = determinar_estado(resumen)
    partes = [
        _header_html(estado, fecha),
        _estado_general_html(resumen, estado),
        _chips_resumen_html(resumen),
        _cxc_resumen_html(resumen),
        _alertas_alto_monto_html(resumen),
        _facturas_vencidas_html(resumen),
        _tabla_meses_html(resumen),
        _tabla_tipos_cambio_html(resumen),
        _tabla_pagos_del_dia_html(resumen),
        _errores_html(resumen),
        _footer_html(),
    ]
    cuerpo = "".join(p for p in partes if p)
    return f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8"><title>Softnet Ventas</title></head>
<body style="margin:0;padding:20px;background:#f4f6f8;font-family:Segoe UI,Arial,sans-serif;color:#2c3e50;">
<div style="max-width:780px;margin:0 auto;background:#ffffff;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.08);">
{cuerpo}
</div>
</body></html>"""


def _header_html(estado: str, fecha: datetime) -> str:
    color = {"OK": _C["verde"], "ADVERTENCIAS": _C["naranja"], "FALLOS": _C["rojo"]}[estado]
    icono = {"OK": "✅", "ADVERTENCIAS": "⚠️", "FALLOS": "❌"}[estado]
    titulo = {"OK": "PROCESO OK", "ADVERTENCIAS": "CON ADVERTENCIAS", "FALLOS": "CON FALLOS"}[estado]
    return f"""
<div style="background:{color};padding:24px 28px;color:#ffffff;">
  <div style="font-size:13px;opacity:0.85;letter-spacing:1px;text-transform:uppercase;">Softnet Ventas — Resumen Diario</div>
  <div style="font-size:22px;font-weight:600;margin-top:4px;">{icono} {titulo}</div>
  <div style="font-size:13px;opacity:0.9;margin-top:6px;">{_DIAS_ES[fecha.weekday()]} {fecha.day} de {_MESES_ES[fecha.month]} de {fecha.year} — {fecha.strftime('%H:%M')}</div>
</div>"""


def _estado_general_html(resumen: dict, estado: str) -> str:
    meses = resumen.get("meses_procesados", [])
    n_meses = len(meses)
    n_ok  = sum(1 for (_, _, s) in meses if s == "OK")
    n_sin = sum(1 for (_, _, s) in meses if s == "SIN_CAMBIOS")
    n_fail = sum(1 for (_, _, s) in meses if s == "FALLO")
    n_eventos = resumen.get("total_eventos", 0)

    if estado == "OK":
        msg = (f"Proceso finalizado correctamente. Se procesaron {n_meses} meses "
               f"({n_ok} con cambios, {n_sin} sin cambios) y se detectaron {n_eventos} eventos.")
    elif estado == "ADVERTENCIAS":
        msg = (f"Proceso finalizado con advertencias. Algunos meses fueron saltados por checkpoint. "
               f"Procesados: {n_meses}, Eventos: {n_eventos}.")
    else:
        msg = (f"Proceso finalizado con fallos. {n_fail} mes(es) no pudieron procesarse. "
               f"Revisar sección de errores más abajo.")

    return f"""
<div style="padding:18px 28px 4px 28px;font-size:14px;line-height:1.5;">
  <strong>Estado general:</strong> {msg}
</div>"""


def _chips_resumen_html(resumen: dict) -> str:
    meses = resumen.get("meses_procesados", [])
    n_meses  = len(meses)
    n_ok     = sum(1 for (_, _, s) in meses if s == "OK")
    n_sin    = sum(1 for (_, _, s) in meses if s == "SIN_CAMBIOS")
    n_fail   = sum(1 for (_, _, s) in meses if s == "FALLO")
    n_skip   = sum(1 for (_, _, s) in meses if s == "SKIP")
    n_eventos = resumen.get("total_eventos", 0)

    tipos = resumen.get("eventos_por_tipo", {})
    n_nuevas = tipos.get("NUEVA_FACTURA", 0)
    n_pagos  = tipos.get("PAGO_APLICADO", 0)
    monto_cobrado = sum(
        float(ev.get("monto_total", 0) or 0)
        for ev in resumen.get("eventos_detalle", [])
        if ev.get("tipo_cambio") == "PAGO_APLICADO"
    )

    chips = [
        _chip(f"Meses: {n_meses}", "info"),
        _chip(f"OK: {n_ok}", "ok"),
        _chip(f"Sin cambios: {n_sin}", "info") if n_sin else "",
        _chip(f"Fallos: {n_fail}", "fail") if n_fail else "",
        _chip(f"Saltados: {n_skip}", "warn") if n_skip else "",
        _chip(f"Cambios: {n_eventos}", "ok" if n_eventos else "info"),
        _chip(f"Facturas nuevas: {n_nuevas}", "info") if n_nuevas else "",
        _chip(f"Pagos hoy: {n_pagos} — {_formato_monto(monto_cobrado)}", "ok") if n_pagos else "",
    ]
    return f"""
<div style="padding:12px 28px 20px 28px;">
  {"".join(c for c in chips if c)}
</div>"""


def _chip(texto: str, tipo: str = "info") -> str:
    estilos = {
        "ok":   (_C["chip_ok_bg"],   _C["chip_ok_txt"]),
        "warn": (_C["chip_warn_bg"], _C["chip_warn_txt"]),
        "fail": (_C["chip_fail_bg"], _C["chip_fail_txt"]),
        "info": (_C["chip_info_bg"], _C["chip_info_txt"]),
    }
    bg, txt = estilos.get(tipo, estilos["info"])
    return (f'<span style="display:inline-block;background:{bg};color:{txt};'
            f'font-size:12px;font-weight:600;padding:5px 12px;border-radius:14px;margin:3px 6px 3px 0;">{texto}</span>')


def _tabla_meses_html(resumen: dict) -> str:
    meses = resumen.get("meses_procesados", [])
    if not meses:
        return ""

    eventos_por_mes: dict[str, int] = {}
    for ev in resumen.get("eventos_detalle", []):
        k = ev["mes_archivo"]
        eventos_por_mes[k] = eventos_por_mes.get(k, 0) + 1

    filas = []
    for i, (año, mes, estado_mes) in enumerate(meses):
        mes_label = f"{año}-{mes:02d}"
        archivo = f"{mes} - Ventas {_MESES_ES[mes]} {año}"
        cambios = eventos_por_mes.get(mes_label, 0)
        chip_estado = {
            "OK":          _chip("OK", "ok"),
            "SIN_CAMBIOS": _chip("Sin cambios", "info"),
            "SKIP":        _chip("Saltado", "warn"),
            "FALLO":       _chip("FALLO", "fail"),
        }.get(estado_mes, estado_mes)
        bg = _C["gris_b"] if i % 2 else "#ffffff"
        filas.append(f"""
<tr style="background:{bg};">
  <td style="padding:10px 14px;border-bottom:1px solid {_C['gris_bd']};">{_MESES_ES[mes]} {año}</td>
  <td style="padding:10px 14px;border-bottom:1px solid {_C['gris_bd']};font-family:Consolas,monospace;font-size:12px;color:{_C['gris_t']};">{archivo}</td>
  <td style="padding:10px 14px;border-bottom:1px solid {_C['gris_bd']};">{chip_estado}</td>
  <td style="padding:10px 14px;border-bottom:1px solid {_C['gris_bd']};text-align:right;font-weight:600;">{cambios if cambios else '—'}</td>
</tr>""")

    return f"""
<div style="padding:0 28px 20px 28px;">
  <h3 style="margin:0 0 10px 0;font-size:15px;color:{_C['gris_h']};">Meses procesados</h3>
  <table style="width:100%;border-collapse:collapse;font-size:13px;">
    <thead>
      <tr style="background:{_C['gris_h']};color:#ffffff;">
        <th style="padding:10px 14px;text-align:left;font-weight:600;">Mes</th>
        <th style="padding:10px 14px;text-align:left;font-weight:600;">Archivo en SharePoint</th>
        <th style="padding:10px 14px;text-align:left;font-weight:600;">Estado</th>
        <th style="padding:10px 14px;text-align:right;font-weight:600;">Cambios</th>
      </tr>
    </thead>
    <tbody>{"".join(filas)}</tbody>
  </table>
</div>"""


def _tabla_tipos_cambio_html(resumen: dict) -> str:
    tipos = resumen.get("eventos_por_tipo", {})
    if not tipos:
        return ""
    total = sum(tipos.values()) or 1
    orden = sorted(tipos.items(), key=lambda x: -x[1])
    filas = []
    for i, (tipo, n) in enumerate(orden):
        pct = n * 100 / total
        bg = _C["gris_b"] if i % 2 else "#ffffff"
        filas.append(f"""
<tr style="background:{bg};">
  <td style="padding:9px 14px;border-bottom:1px solid {_C['gris_bd']};font-size:12px;">{_formato_tipo(tipo)}</td>
  <td style="padding:9px 14px;border-bottom:1px solid {_C['gris_bd']};text-align:right;font-weight:600;">{n}</td>
  <td style="padding:9px 14px;border-bottom:1px solid {_C['gris_bd']};text-align:right;color:{_C['gris_t']};">{pct:.1f}%</td>
</tr>""")

    return f"""
<div style="padding:0 28px 20px 28px;">
  <h3 style="margin:0 0 10px 0;font-size:15px;color:{_C['gris_h']};">Detalle de cambios por tipo</h3>
  <table style="width:100%;border-collapse:collapse;font-size:13px;max-width:480px;">
    <thead>
      <tr style="background:{_C['gris_h']};color:#ffffff;">
        <th style="padding:10px 14px;text-align:left;font-weight:600;">Tipo de cambio</th>
        <th style="padding:10px 14px;text-align:right;font-weight:600;">Cantidad</th>
        <th style="padding:10px 14px;text-align:right;font-weight:600;">% del total</th>
      </tr>
    </thead>
    <tbody>{"".join(filas)}</tbody>
  </table>
</div>"""


def _tabla_pagos_del_dia_html(resumen: dict) -> str:
    eventos = resumen.get("eventos_detalle", [])
    pagos = [ev for ev in eventos if ev.get("tipo_cambio") == "PAGO_APLICADO"]
    if not pagos:
        return ""
    pagos_ord = sorted(pagos, key=lambda x: -float(x.get("monto_total", 0) or 0))
    total_monto = sum(float(ev.get("monto_total", 0) or 0) for ev in pagos_ord)
    filas = []
    for i, ev in enumerate(pagos_ord):
        bg = _C["gris_b"] if i % 2 else "#ffffff"
        monto = float(ev.get("monto_total", 0) or 0)
        dias = ev.get("dias_cobro", "—")
        razon = _escapar_html(_truncar(ev.get("razon_social", ""), 40))
        filas.append(f"""
<tr style="background:{bg};">
  <td style="padding:8px 14px;border-bottom:1px solid {_C['gris_bd']};font-size:12px;white-space:nowrap;">{ev.get('tipo_doc','')}-{ev.get('n_cto','')}</td>
  <td style="padding:8px 14px;border-bottom:1px solid {_C['gris_bd']};font-size:12px;">{razon}</td>
  <td style="padding:8px 14px;border-bottom:1px solid {_C['gris_bd']};font-size:12px;text-align:center;white-space:nowrap;">{ev.get('mes_archivo','—')}</td>
  <td style="padding:8px 14px;border-bottom:1px solid {_C['gris_bd']};font-size:12px;text-align:center;white-space:nowrap;">{ev.get('fecha_pago','—')}</td>
  <td style="padding:8px 14px;border-bottom:1px solid {_C['gris_bd']};font-size:12px;text-align:right;font-weight:600;white-space:nowrap;">{_formato_monto(monto)}</td>
  <td style="padding:8px 14px;border-bottom:1px solid {_C['gris_bd']};font-size:12px;text-align:right;color:{_color_dias(dias)};font-weight:600;white-space:nowrap;">{dias}</td>
</tr>""")

    return f"""
<div style="padding:0 28px 20px 28px;">
  <h3 style="margin:0 0 4px 0;font-size:15px;color:{_C['gris_h']};">Pagos aplicados hoy ({len(pagos_ord)})</h3>
  <p style="margin:0 0 10px 0;font-size:12px;color:{_C['gris_t']};">Monto total recaudado: <strong>{_formato_monto(total_monto)}</strong></p>
  <table style="width:100%;border-collapse:collapse;font-size:13px;">
    <thead>
      <tr style="background:{_C['gris_h']};color:#ffffff;">
        <th style="padding:10px 14px;text-align:left;font-weight:600;">Doc</th>
        <th style="padding:10px 14px;text-align:left;font-weight:600;">Cliente</th>
        <th style="padding:10px 14px;text-align:center;font-weight:600;">Mes emisión</th>
        <th style="padding:10px 14px;text-align:center;font-weight:600;">Fecha pago</th>
        <th style="padding:10px 14px;text-align:right;font-weight:600;">Monto</th>
        <th style="padding:10px 14px;text-align:right;font-weight:600;">Días cobro</th>
      </tr>
    </thead>
    <tbody>{"".join(filas)}</tbody>
  </table>
  <p style="margin:8px 0 0 0;font-size:11px;color:{_C['gris_t']};">
    <span style="color:#27ae60;">■</span> ≤30 días &nbsp;
    <span style="color:#e67e22;">■</span> 31-60 días &nbsp;
    <span style="color:#c0392b;">■</span> &gt;60 días
  </p>
</div>"""


def _cxc_resumen_html(resumen: dict) -> str:
    cxc = resumen.get("cxc_por_mes", {})
    if not cxc:
        return ""
    total_global = sum(v["total_pendiente"] for v in cxc.values())
    n_global     = sum(v["n_facturas"]      for v in cxc.values())
    filas = []
    for i, mes_label in enumerate(sorted(cxc)):
        datos = cxc[mes_label]
        año, mes = int(mes_label[:4]), int(mes_label[5:])
        bg = _C["gris_b"] if i % 2 else "#ffffff"
        filas.append(f"""
<tr style="background:{bg};">
  <td style="padding:9px 14px;border-bottom:1px solid {_C['gris_bd']};">{_MESES_ES[mes]} {año}</td>
  <td style="padding:9px 14px;border-bottom:1px solid {_C['gris_bd']};text-align:right;font-weight:600;white-space:nowrap;">{_formato_monto(datos['total_pendiente'])}</td>
  <td style="padding:9px 14px;border-bottom:1px solid {_C['gris_bd']};text-align:right;">{datos['n_facturas']}</td>
</tr>""")
    return f"""
<div style="padding:0 28px 20px 28px;">
  <h3 style="margin:0 0 4px 0;font-size:15px;color:{_C['gris_h']};">Cuentas por cobrar pendientes</h3>
  <p style="margin:0 0 4px 0;font-size:12px;color:{_C['gris_t']};">Total global: <strong style="color:{_C['gris_h']};font-size:14px;">{_formato_monto(total_global)}</strong> en {n_global} facturas</p>
  <p style="margin:0 0 10px 0;font-size:11px;color:{_C['gris_t']};font-style:italic;">Suma del saldo pendiente de todas las facturas sin pagar. Las alertas de alto monto y vencidas son subconjuntos filtrados de este total — una factura puede aparecer en más de una sección.</p>
  <table style="width:100%;border-collapse:collapse;font-size:13px;max-width:420px;">
    <thead>
      <tr style="background:{_C['gris_h']};color:#ffffff;">
        <th style="padding:9px 14px;text-align:left;font-weight:600;">Mes</th>
        <th style="padding:9px 14px;text-align:right;font-weight:600;">Pendiente</th>
        <th style="padding:9px 14px;text-align:right;font-weight:600;">Facturas</th>
      </tr>
    </thead>
    <tbody>{"".join(filas)}</tbody>
  </table>
</div>"""


def _alertas_alto_monto_html(resumen: dict) -> str:
    alertas = resumen.get("alertas_alto_monto", [])
    if not alertas:
        return ""
    filas = []
    for i, ev in enumerate(alertas):
        bg = _C["gris_b"] if i % 2 else "#ffffff"
        razon = _escapar_html(_truncar(ev.get("razon_social", ""), 38))
        filas.append(f"""
<tr style="background:{bg};">
  <td style="padding:8px 14px;border-bottom:1px solid {_C['gris_bd']};font-size:12px;white-space:nowrap;">{ev.get('tipo_doc','')}-{ev.get('n_cto','')}</td>
  <td style="padding:8px 14px;border-bottom:1px solid {_C['gris_bd']};font-size:12px;">{razon}</td>
  <td style="padding:8px 14px;border-bottom:1px solid {_C['gris_bd']};font-size:12px;text-align:center;">{ev.get('mes_label','—')}</td>
  <td style="padding:8px 14px;border-bottom:1px solid {_C['gris_bd']};font-size:12px;text-align:right;font-weight:600;white-space:nowrap;">{_formato_monto(ev.get('saldo',0))}</td>
  <td style="padding:8px 14px;border-bottom:1px solid {_C['gris_bd']};font-size:12px;text-align:right;color:{_color_dias(ev.get('dias_emision','—'))}">{ev.get('dias_emision','—')} días</td>
</tr>""")
    return f"""
<div style="margin:0 28px 20px 28px;padding:14px 18px;background:{_C['chip_warn_bg']};border-left:4px solid {_C['naranja']};border-radius:4px;">
  <h3 style="margin:0 0 10px 0;font-size:14px;color:{_C['chip_warn_txt']};">⚠️ Facturas de alto monto sin pagar ({len(alertas)})</h3>
  <table style="width:100%;border-collapse:collapse;font-size:13px;background:#ffffff;border-radius:4px;overflow:hidden;">
    <thead>
      <tr style="background:{_C['gris_h']};color:#ffffff;">
        <th style="padding:8px 14px;text-align:left;font-weight:600;">Doc</th>
        <th style="padding:8px 14px;text-align:left;font-weight:600;">Cliente</th>
        <th style="padding:8px 14px;text-align:center;font-weight:600;">Mes</th>
        <th style="padding:8px 14px;text-align:right;font-weight:600;">Saldo</th>
        <th style="padding:8px 14px;text-align:right;font-weight:600;">Días</th>
      </tr>
    </thead>
    <tbody>{"".join(filas)}</tbody>
  </table>
</div>"""


def _facturas_vencidas_html(resumen: dict) -> str:
    vencidas = resumen.get("facturas_vencidas", [])
    if not vencidas:
        return ""
    filas = []
    for i, ev in enumerate(vencidas):
        bg = _C["gris_b"] if i % 2 else "#ffffff"
        razon = _escapar_html(_truncar(ev.get("razon_social", ""), 38))
        dias  = ev.get("dias_atraso", "—")
        filas.append(f"""
<tr style="background:{bg};">
  <td style="padding:8px 14px;border-bottom:1px solid {_C['gris_bd']};font-size:12px;white-space:nowrap;">{ev.get('tipo_doc','')}-{ev.get('n_cto','')}</td>
  <td style="padding:8px 14px;border-bottom:1px solid {_C['gris_bd']};font-size:12px;">{razon}</td>
  <td style="padding:8px 14px;border-bottom:1px solid {_C['gris_bd']};font-size:12px;text-align:center;">{ev.get('mes_label','—')}</td>
  <td style="padding:8px 14px;border-bottom:1px solid {_C['gris_bd']};font-size:12px;text-align:right;font-weight:600;white-space:nowrap;">{_formato_monto(ev.get('saldo',0))}</td>
  <td style="padding:8px 14px;border-bottom:1px solid {_C['gris_bd']};font-size:12px;text-align:right;font-weight:600;color:{_C['rojo']};white-space:nowrap;">{dias} días</td>
</tr>""")
    return f"""
<div style="margin:0 28px 20px 28px;padding:14px 18px;background:{_C['chip_fail_bg']};border-left:4px solid {_C['rojo']};border-radius:4px;">
  <h3 style="margin:0 0 10px 0;font-size:14px;color:{_C['chip_fail_txt']};">🔴 Facturas vencidas sin pagar ({len(vencidas)})</h3>
  <table style="width:100%;border-collapse:collapse;font-size:13px;background:#ffffff;border-radius:4px;overflow:hidden;">
    <thead>
      <tr style="background:{_C['gris_h']};color:#ffffff;">
        <th style="padding:8px 14px;text-align:left;font-weight:600;">Doc</th>
        <th style="padding:8px 14px;text-align:left;font-weight:600;">Cliente</th>
        <th style="padding:8px 14px;text-align:center;font-weight:600;">Mes</th>
        <th style="padding:8px 14px;text-align:right;font-weight:600;">Saldo</th>
        <th style="padding:8px 14px;text-align:right;font-weight:600;">Días atraso</th>
      </tr>
    </thead>
    <tbody>{"".join(filas)}</tbody>
  </table>
</div>"""


def _errores_html(resumen: dict) -> str:
    errores = resumen.get("errores", [])
    if not errores:
        return ""
    items = "".join(f'<li style="margin:5px 0;">{e}</li>' for e in errores)
    return f"""
<div style="margin:0 28px 20px 28px;padding:14px 18px;background:{_C['chip_fail_bg']};border-left:4px solid {_C['rojo']};border-radius:4px;">
  <h3 style="margin:0 0 8px 0;font-size:14px;color:{_C['chip_fail_txt']};">Errores detectados</h3>
  <ul style="margin:0;padding-left:20px;font-size:13px;color:{_C['chip_fail_txt']};">{items}</ul>
</div>"""


def _footer_html() -> str:
    return f"""
<div style="padding:16px 28px 20px 28px;background:#fafbfc;border-top:1px solid {_C['gris_bd']};font-size:11px;color:{_C['gris_t']};text-align:center;">
  Notificación automática generada por Sistema Softnet Ventas — Egakat
</div>"""


def _formato_monto(n: float) -> str:
    try:
        return "$ " + f"{int(round(n)):,}".replace(",", ".")
    except Exception:
        return "—"


_TIPO_LABELS = {
    "PAGO_APLICADO":  "Pago aplicado",
    "NUEVA_FACTURA":  "Nueva factura",
    "NC_APLICADA":    "Nota de crédito",
    "CAMBIO_SALDO":   "Cambio de saldo",
    "CAMBIO_OTRO":    "Otro cambio",
}

def _formato_tipo(tipo: str) -> str:
    return _TIPO_LABELS.get(tipo, tipo.replace("_", " ").title())


def _truncar(s: str, n: int) -> str:
    s = str(s or "").strip()
    return s if len(s) <= n else s[:n-1] + "…"


def _escapar_html(texto: str) -> str:
    """Escapa caracteres HTML para prevenir XSS en emails."""
    return html.escape(str(texto or ""))


def _color_dias(dias: Any) -> str:
    try:
        d = int(dias)
        if d <= 30: return _C["verde"]
        if d <= 60: return _C["naranja"]
        return _C["rojo"]
    except Exception:
        return _C["gris_t"]
