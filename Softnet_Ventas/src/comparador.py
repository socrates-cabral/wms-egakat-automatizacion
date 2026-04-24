import sys
sys.stdout.reconfigure(encoding="utf-8")

from datetime import datetime, date
from pathlib import Path
import pandas as pd


def parse_libro_ventas(xlsx_path: Path) -> pd.DataFrame:
    """Lee archivo Softnet. Headers en fila 10 (índice 9), datos desde fila 11."""
    if not xlsx_path.exists():
        return pd.DataFrame()
    df = pd.read_excel(xlsx_path, header=9, engine="openpyxl")
    df = df.dropna(subset=["Cto", "Tipo Doc"])
    df = df[pd.to_numeric(df["Tipo Doc"], errors="coerce").notna()].copy()
    df["Tipo Doc"] = pd.to_numeric(df["Tipo Doc"], errors="coerce").astype(int)
    df["Cto"] = pd.to_numeric(df["Cto"], errors="coerce").astype(int)
    df["doc_id"] = df["Tipo Doc"].astype(str) + "-" + df["Cto"].astype(str)
    df["Estado"] = df["Estado"].fillna("").astype(str).str.strip()
    df["Fecha Ultimo pago"] = df["Fecha Ultimo pago"].fillna("-").astype(str).str.strip()
    df["Saldo"] = pd.to_numeric(df["Saldo"], errors="coerce").fillna(0)
    df["Total"] = pd.to_numeric(df["Total"], errors="coerce").fillna(0)
    return df


def detectar_cambios(df_nuevo: pd.DataFrame, df_anterior: pd.DataFrame, mes_archivo: str) -> list[dict]:
    """Compara dos DataFrames del mismo mes y retorna lista de eventos.
    Si df_anterior está vacío (primera carga), retorna lista vacía.
    """
    if df_anterior.empty or df_nuevo.empty:
        return []

    eventos = []
    idx_ant = df_anterior.set_index("doc_id")
    idx_nuevo = df_nuevo.set_index("doc_id")

    nuevos_ids = set(idx_nuevo.index) - set(idx_ant.index)
    for doc_id in nuevos_ids:
        row = idx_nuevo.loc[doc_id]
        tipo_evento = "NC_APLICADA" if row["Tipo Doc"] == 61 else "NUEVA_FACTURA"
        eventos.append(_build_evento(row, mes_archivo, tipo_evento, estado_anterior=None))

    comunes = set(idx_nuevo.index) & set(idx_ant.index)
    for doc_id in comunes:
        r_ant = idx_ant.loc[doc_id]
        r_new = idx_nuevo.loc[doc_id]
        estado_ant = r_ant["Estado"]
        estado_new = r_new["Estado"]

        if estado_ant == "NO Pagado" and estado_new == "Pagado":
            eventos.append(_build_evento(r_new, mes_archivo, "PAGO_APLICADO", estado_anterior=estado_ant))
        elif r_ant["Saldo"] != r_new["Saldo"] and estado_ant == estado_new:
            eventos.append(_build_evento(r_new, mes_archivo, "CAMBIO_SALDO", estado_anterior=estado_ant))

    return eventos


def hay_cambios(eventos: list[dict]) -> bool:
    return len(eventos) > 0


def analizar_estado_mes(df: pd.DataFrame, año: int, mes: int,
                         umbral_alto_monto: float = 5_000_000,
                         dias_vencimiento: int = 60) -> dict:
    """Analiza el estado actual de un mes descargado.
    Retorna vencidas, alertas de alto monto y totales CxC.
    Solo considera Tipo Doc=33 (facturas), excluye NC.
    """
    hoy = date.today()
    resultado = {"vencidas": [], "alto_monto": [], "cxc": {"total_pendiente": 0.0, "n_facturas": 0}}
    if df.empty:
        return resultado

    mes_label = f"{año}-{mes:02d}"
    facturas = df[(df["Tipo Doc"] == 33) & (df["Estado"] == "NO Pagado")].copy()

    for _, row in facturas.iterrows():
        saldo = float(row.get("Saldo", 0) or 0)
        total = float(row.get("Total", 0) or 0)
        resultado["cxc"]["total_pendiente"] += saldo if saldo > 0 else total
        resultado["cxc"]["n_facturas"] += 1

        dias_atraso = None
        try:
            fe = pd.to_datetime(row["Fecha"]).date()
            dias_atraso = (hoy - fe).days
        except Exception:
            pass

        base = {
            "mes_label": mes_label,
            "tipo_doc": 33,
            "n_cto": int(row["Cto"]),
            "rut": row.get("Rut", ""),
            "razon_social": row.get("Razon Social", ""),
            "monto_total": total,
            "saldo": saldo if saldo > 0 else total,
            "dias_emision": dias_atraso,
        }

        if dias_atraso is not None and dias_atraso > dias_vencimiento:
            resultado["vencidas"].append({**base, "dias_atraso": dias_atraso})

        if total > umbral_alto_monto:
            resultado["alto_monto"].append(base)

    resultado["vencidas"].sort(key=lambda x: -x["dias_atraso"])
    resultado["alto_monto"].sort(key=lambda x: -x["monto_total"])
    return resultado


def _build_evento(row, mes_archivo: str, tipo: str, estado_anterior) -> dict:
    dias_cobro = "—"
    if tipo == "PAGO_APLICADO":
        try:
            fe = pd.to_datetime(row["Fecha"]).date()
            fp = pd.to_datetime(row["Fecha Ultimo pago"]).date()
            dias_cobro = (fp - fe).days
        except Exception:
            pass

    return {
        "fecha_deteccion": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "mes_archivo": mes_archivo,
        "tipo_doc": int(row["Tipo Doc"]),
        "n_cto": int(row["Cto"]),
        "rut": row.get("Rut", ""),
        "razon_social": row.get("Razon Social", ""),
        "tipo_cambio": tipo,
        "estado_anterior_actual": f"{estado_anterior or '-'} → {row['Estado']}",
        "fecha_pago": row["Fecha Ultimo pago"],
        "monto_total": float(row["Total"]),
        "dias_cobro": dias_cobro,
    }
