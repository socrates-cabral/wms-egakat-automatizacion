import sys
sys.stdout.reconfigure(encoding="utf-8")

import math
from typing import Dict, List, Optional
import pandas as pd


def calc_ingresos_totales(liquido: float, amipass: float = 0, otros: float = 0) -> float:
    """Suma ingresos líquidos totales del mes."""
    return liquido + amipass + otros


def calc_resumen_mes(df: pd.DataFrame, mes: int) -> dict:
    """
    Retorna resumen del mes dado.
    {por_grupo: {grupo: total}, total: float, por_tipo: {tipo: total}, ingresos: float}
    total solo cuenta Gastos (no Ingresos) para no inflar el KPI de gastos.
    """
    df_mes = df[df["mes"] == mes].copy()
    if df_mes.empty:
        return {"por_grupo": {}, "total": 0.0, "por_tipo": {}, "ingresos": 0.0}
    col_tipo = "tipo_tx" if "tipo_tx" in df_mes.columns else "tipo"
    df_gastos  = df_mes[df_mes[col_tipo] != "Ingreso"] if col_tipo in df_mes.columns else df_mes
    df_ingresos = df_mes[df_mes[col_tipo] == "Ingreso"] if col_tipo in df_mes.columns else pd.DataFrame()
    por_grupo = df_gastos.groupby("grupo")["importe"].sum().to_dict()
    total     = df_gastos["importe"].sum()
    ingresos  = df_ingresos["importe"].sum() if not df_ingresos.empty else 0.0
    por_tipo  = df_mes.groupby(col_tipo)["importe"].sum().to_dict() if col_tipo in df_mes.columns else {}
    return {"por_grupo": por_grupo, "total": total, "por_tipo": por_tipo, "ingresos": ingresos}


def calc_tasa_ahorro(ingresos: float, gastos: float) -> dict:
    """
    Calcula tasa de ahorro.
    estado_semaforo: 'verde' >=20%, 'amarillo' 10-19%, 'rojo' <10%
    """
    if ingresos <= 0:
        return {"tasa": 0.0, "absoluto": 0.0, "estado_semaforo": "rojo"}
    ahorro = ingresos - gastos
    tasa = (ahorro / ingresos) * 100
    if tasa >= 20:
        estado = "verde"
    elif tasa >= 10:
        estado = "amarillo"
    else:
        estado = "rojo"
    return {"tasa": round(tasa, 1), "absoluto": ahorro, "estado_semaforo": estado}


def calc_regla_50_30_20(
    df_mes: pd.DataFrame,
    ingresos: float,
    tipos_dict: Dict[str, str],
) -> dict:
    """
    Clasifica gastos según regla 50/30/20:
    - Necesidades (Fijo): 50% ideal
    - Deseos (Variable + Prescindible): 30% ideal
    - Ahorro/Deudas: 20% ideal
    """
    df = df_mes.copy()
    if "tipo" not in df.columns:
        df["tipo"] = df["grupo"].map(tipos_dict).fillna("Variable")
    necesidades = df[df["tipo"] == "Fijo"]["importe"].sum()
    deseos = df[df["tipo"].isin(["Variable", "Prescindible"])]["importe"].sum()
    total_gastos = necesidades + deseos
    ahorro_real = max(ingresos - total_gastos, 0)
    ideal_nec = ingresos * 0.50
    ideal_des = ingresos * 0.30
    ideal_aho = ingresos * 0.20
    return {
        "necesidades": necesidades,
        "deseos": deseos,
        "ahorro_deudas": ahorro_real,
        "ideal_necesidades": ideal_nec,
        "ideal_deseos": ideal_des,
        "ideal_ahorro": ideal_aho,
        "diferencia_ahorro": ahorro_real - ideal_aho,
    }


def calc_patrimonio_neto(activos_dict: dict, pasivos_dict: dict) -> dict:
    """
    Calcula patrimonio neto.
    activos_dict / pasivos_dict: {nombre: valor}
    """
    total_activos = sum(v for v in activos_dict.values() if isinstance(v, (int, float)))
    total_pasivos = sum(v for v in pasivos_dict.values() if isinstance(v, (int, float)))
    neto = total_activos - total_pasivos
    ratio = (total_pasivos / total_activos * 100) if total_activos > 0 else 0
    return {
        "total_activos": total_activos,
        "total_pasivos": total_pasivos,
        "neto": neto,
        "ratio_endeudamiento": round(ratio, 1),
    }


def calc_proyeccion_afp(
    saldo_actual: float,
    aporte_neto_mensual: float,
    tasa_anual: float,
    anos: int,
) -> List[float]:
    """
    Proyecta saldo AFP mes a mes.
    Retorna lista de saldos anuales (longitud = anos + 1).
    """
    tasa_mensual = (1 + tasa_anual / 100) ** (1 / 12) - 1
    saldos = [saldo_actual]
    saldo = saldo_actual
    for _ in range(anos * 12):
        saldo = saldo * (1 + tasa_mensual) + aporte_neto_mensual
    # Calcular año a año
    saldos_anuales = [saldo_actual]
    saldo = saldo_actual
    for ano in range(anos):
        for _ in range(12):
            saldo = saldo * (1 + tasa_mensual) + aporte_neto_mensual
        saldos_anuales.append(saldo)
    return saldos_anuales


def calc_pe_financiero(ingresos: float, gastos_fijos: float) -> float:
    """Meses para punto de equilibrio si ingresos = gastos_fijos."""
    if ingresos >= gastos_fijos:
        return 0.0
    return round(gastos_fijos / ingresos, 1)


def calc_fire_number(gastos_anuales: float, tasa_retiro: float = 0.04) -> dict:
    """
    Calcula capital necesario para FIRE (Financial Independence, Retire Early).
    Regla del 4%.
    """
    capital = gastos_anuales / tasa_retiro
    return {
        "capital_necesario": capital,
        "tasa_retiro_pct": tasa_retiro * 100,
        "gastos_anuales": gastos_anuales,
    }


def calc_tiempo_para_meta(
    saldo_actual: float,
    meta: float,
    ahorro_mensual: float,
    tasa_anual: float = 0.0,
) -> dict:
    """
    Calcula meses para alcanzar una meta de ahorro.
    Considera rendimiento compuesto si tasa_anual > 0.
    """
    if ahorro_mensual <= 0:
        return {"meses": None, "anos": None, "imposible": True}
    if saldo_actual >= meta:
        return {"meses": 0, "anos": 0, "imposible": False}
    tasa_mensual = (1 + tasa_anual / 100) ** (1 / 12) - 1 if tasa_anual > 0 else 0
    if tasa_mensual == 0:
        meses = math.ceil((meta - saldo_actual) / ahorro_mensual)
    else:
        # FV = saldo*(1+r)^n + pmt*((1+r)^n - 1)/r = meta
        # Resolver numéricamente
        saldo = saldo_actual
        meses = 0
        while saldo < meta and meses < 600:
            saldo = saldo * (1 + tasa_mensual) + ahorro_mensual
            meses += 1
        if saldo < meta:
            return {"meses": None, "anos": None, "imposible": True}
    return {
        "meses": meses,
        "anos": round(meses / 12, 1),
        "imposible": False,
    }


def calc_amortizacion(
    saldo: float,
    tasa_mensual_pct: float,
    cuota: float,
) -> pd.DataFrame:
    """
    Genera tabla de amortización francesa.
    Retorna DataFrame con: mes, saldo_inicial, interes, capital, cuota, saldo_final
    """
    tasa = tasa_mensual_pct / 100
    filas = []
    mes = 1
    while saldo > 0.01 and mes <= 600:
        interes = saldo * tasa
        capital = cuota - interes
        if capital <= 0:
            break
        saldo_final = max(saldo - capital, 0)
        filas.append({
            "Mes": mes,
            "Saldo Inicial": round(saldo, 0),
            "Interés": round(interes, 0),
            "Capital": round(capital, 0),
            "Cuota": round(cuota, 0),
            "Saldo Final": round(saldo_final, 0),
        })
        saldo = saldo_final
        mes += 1
    return pd.DataFrame(filas)
