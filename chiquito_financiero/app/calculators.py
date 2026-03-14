import sys
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# calculators.py — Lógica financiera para Chiquito Finanzas
# Contiene: punto de equilibrio, amortización francesa, inyección de capital

COSTOS_FIJOS_BASE = {
    'alquiler_taller':  700_000,
    'telefono':          45_000,
    'internet':          18_000,
    'luz_agua':          55_000,
    'mercadopago':       36_000,
    'gasolina':         100_000,
    'gastos_varios':     40_000,
}

DEUDAS_DEFAULT = [
    {'acreedor': 'Banco Itau (crédito 36m)',    'saldo': 5_749_547, 'cuota': 154_028, 'tasa': 2.8, 'tipo': 'banco'},
    {'acreedor': 'Banco Estado (crédito 36m)',  'saldo': 5_600_000, 'cuota': 174_437, 'tasa': 3.1, 'tipo': 'banco'},
    {'acreedor': 'Banco Santander (TC)',         'saldo': 3_760_935, 'cuota': 109_000, 'tasa': 2.8, 'tipo': 'tc'},
    {'acreedor': 'CMR Falabella (TC retail)',    'saldo': 1_607_443, 'cuota':  80_000, 'tasa': 3.3, 'tipo': 'tc'},
    {'acreedor': 'Líneas crédito (3 bancos)',    'saldo': 2_360_000, 'cuota':  71_660, 'tasa': 3.1, 'tipo': 'linea'},
    {'acreedor': 'Crédito automotriz Foton',    'saldo': 9_517_195, 'cuota': 264_366, 'tasa': 1.2, 'tipo': 'auto'},
    {'acreedor': 'Seguro camión Foton',         'saldo':         0, 'cuota':  65_412, 'tasa': 0.0, 'tipo': 'seguro'},
    {'acreedor': 'Hermana (dólares)',            'saldo': 1_050_000, 'cuota':       0, 'tasa': 0.0, 'tipo': 'familiar'},
]

BCI_CREDITO_DEFAULT = {
    'monto':            10_000_000,
    'cuotas':           18,
    'tasa_mensual':     0.0143,
    'cuota':            648_805,
    'cae':              0.2024,
    'ctc':              11_678_482,
    'primera_cuota':    '15-Abr-2026',
}

MONTHLY_DEFAULT = [
    {'mes': 'Nov-25', 'ing': 1_721_170, 'gas': 2_025_470},
    {'mes': 'Dic-25', 'ing': 3_024_913, 'gas': 2_715_420},
    {'mes': 'Ene-26', 'ing': 1_625_820, 'gas': 1_601_683},
    {'mes': 'Feb-26', 'ing': 1_964_928, 'gas': 1_617_387},
    {'mes': 'Mar-26', 'ing': 2_400_000, 'gas': 2_200_000},
]


def calc_punto_equilibrio(costos_fijos: dict, cuotas_bancarias: float, margen_bruto_pct: float) -> float:
    """
    Retorna el monto mensual de ventas necesario para cubrir todos los costos.
    margen_bruto_pct: porcentaje como decimal (ej: 0.45 para 45%)
    """
    if margen_bruto_pct <= 0:
        return float('inf')
    total_fijos = sum(costos_fijos.values()) + cuotas_bancarias
    return total_fijos / margen_bruto_pct


def calc_cuota_frances(monto: float, tasa_mensual: float, n_cuotas: int) -> float:
    """
    Sistema francés (cuota fija). Fórmula: C = P * i / (1 - (1+i)^-n)
    Usado para calcular cuota del crédito BCI.
    """
    if tasa_mensual == 0:
        return monto / n_cuotas
    i = tasa_mensual
    cuota = monto * i / (1 - (1 + i) ** (-n_cuotas))
    return round(cuota, 0)


def calc_amortizacion(monto: float, tasa_mensual: float, n_cuotas: int) -> list:
    """
    Retorna tabla de amortización mes a mes.
    Cada fila: {mes, cuota, interes, principal, saldo}
    """
    cuota = calc_cuota_frances(monto, tasa_mensual, n_cuotas)
    saldo = monto
    tabla = []
    for mes in range(1, n_cuotas + 1):
        interes   = round(saldo * tasa_mensual, 0)
        principal = round(cuota - interes, 0)
        saldo     = round(saldo - principal, 0)
        if saldo < 0:
            saldo = 0
        tabla.append({
            'mes':       mes,
            'cuota':     cuota,
            'interes':   interes,
            'principal': principal,
            'saldo':     saldo,
        })
    return tabla


def calc_inyeccion_capital(
    monto_bci:       float,
    aporte_familiar: float,
    tasa_bci:        float,
    cuotas_bci:      int,
    deudas=None,
) -> dict:
    """
    Calcula el impacto de inyectar capital en la deuda.
    Estrategia: pagar de mayor a menor tasa.
    El préstamo de Sócrates a su hermana NO tiene interés — apoyo familiar.
    """
    if deudas is None:
        deudas = DEUDAS_DEFAULT

    capital_total = monto_bci + aporte_familiar
    cuota_bci     = calc_cuota_frances(monto_bci, tasa_bci, cuotas_bci)

    # Ordenar deudas de mayor a menor tasa (excluir 'familiar')
    deudas_ordenadas = sorted(
        [d for d in deudas if d['tipo'] != 'familiar'],
        key=lambda x: x['tasa'],
        reverse=True
    )

    capital_restante        = capital_total
    asignaciones            = []
    cuotas_liberadas        = 0.0
    intereses_eliminados    = 0.0

    for deuda in deudas_ordenadas:
        if capital_restante <= 0:
            break
        pago = min(deuda['saldo'], capital_restante)
        if pago <= 0:
            continue

        # Fracción del saldo que se cancela → libera fracción proporcional de cuota
        if deuda['saldo'] > 0:
            fraccion         = pago / deuda['saldo']
            cuota_liberada   = round(deuda['cuota'] * fraccion, 0)
            interes_mensual  = round(deuda['saldo'] * (deuda['tasa'] / 100), 0)
            interes_eliminado = round(interes_mensual * fraccion, 0)
        else:
            cuota_liberada    = 0
            interes_eliminado = 0

        asignaciones.append({
            'acreedor':          deuda['acreedor'],
            'saldo_original':    deuda['saldo'],
            'pago':              pago,
            'cuota_liberada':    cuota_liberada,
            'interes_eliminado': interes_eliminado,
            'cancelado':         pago >= deuda['saldo'],
        })

        cuotas_liberadas     += cuota_liberada
        intereses_eliminados += interes_eliminado
        capital_restante     -= pago

    interes_bci_mensual  = round(monto_bci * tasa_bci, 0)
    impacto_neto_cuotas  = round(cuotas_liberadas - cuota_bci, 0)
    ahorro_neto_intereses = round(intereses_eliminados - interes_bci_mensual, 0)
    ahorro_total_periodo = round(ahorro_neto_intereses * cuotas_bci, 0)

    # Tasa promedio ponderada de las deudas eliminadas
    total_deuda_pagada = sum(a['pago'] for a in asignaciones)
    if total_deuda_pagada > 0:
        tasa_promedio_deuda = sum(
            next(d['tasa'] for d in deudas if d['acreedor'] == a['acreedor']) * a['pago']
            for a in asignaciones
        ) / total_deuda_pagada
    else:
        tasa_promedio_deuda = 0

    arbitraje_tasa = round(tasa_promedio_deuda - tasa_bci * 100, 2)

    return {
        'asignaciones':              asignaciones,
        'cuotas_liberadas':          cuotas_liberadas,
        'cuota_bci':                 cuota_bci,
        'impacto_neto_cuotas':       impacto_neto_cuotas,
        'intereses_eliminados_mes':  intereses_eliminados,
        'interes_bci_mensual':       interes_bci_mensual,
        'ahorro_neto_intereses':     ahorro_neto_intereses,
        'ahorro_total_periodo':      ahorro_total_periodo,
        'arbitraje_tasa':            arbitraje_tasa,
        'capital_sobrante':          capital_restante,
        'acuerdo_hermana': (
            f"La hermana paga la cuota BCI de ${cuota_bci:,.0f}/mes. "
            "Sin interés adicional — es apoyo familiar sin costo para ella."
        ),
    }


def calc_meses_hasta_quiebra(resultado_mensual: float, capital_trabajo: float = 500_000):
    """
    Si el resultado mensual es negativo, retorna cuántos meses dura el capital de trabajo.
    Retorna None si el negocio es rentable.
    """
    if resultado_mensual >= 0:
        return None
    if capital_trabajo <= 0:
        return 0
    return int(capital_trabajo / abs(resultado_mensual))


def calc_proyeccion_12m(ventas_base: float, crecimiento_pct: float, costos_fijos: dict, cuotas: float, margen: float) -> list:
    """
    Proyección mensual a 12 meses.
    crecimiento_pct: porcentaje mensual como decimal (ej: 0.02 para 2%)
    """
    resultado = []
    ventas = ventas_base
    for mes in range(1, 13):
        costo_variable = ventas * (1 - margen)
        costo_total    = costo_variable + sum(costos_fijos.values()) + cuotas
        resultado_mes  = ventas - costo_total
        resultado.append({
            'mes':             mes,
            'ventas':          round(ventas, 0),
            'costo_total':     round(costo_total, 0),
            'resultado':       round(resultado_mes, 0),
        })
        ventas = ventas * (1 + crecimiento_pct)
    return resultado


# ─── Tests internos ────────────────────────────────────────────────────────────
if __name__ == '__main__':
    # Punto de equilibrio
    pe = calc_punto_equilibrio(COSTOS_FIJOS_BASE, 918_903, 0.45)
    assert pe > 3_000_000, f"PE inesperado: {pe}"
    print(f"PE: ${pe:,.0f}")

    # Cuota francesa BCI
    cuota = calc_cuota_frances(10_000_000, 0.0143, 18)
    assert 620_000 < cuota < 670_000, f"Cuota BCI inesperada: {cuota}"
    print(f"Cuota BCI: ${cuota:,.0f}")

    # Amortización
    tabla = calc_amortizacion(10_000_000, 0.0143, 18)
    assert len(tabla) == 18
    assert tabla[-1]['saldo'] == 0
    print(f"Última cuota saldo: ${tabla[-1]['saldo']:,.0f}")

    # Inyección de capital
    resultado = calc_inyeccion_capital(10_000_000, 2_200_000, 0.0143, 18)
    assert resultado['arbitraje_tasa'] > 0, "Arbitraje debe ser positivo"
    print(f"Arbitraje: {resultado['arbitraje_tasa']:.2f}% mensual")
    print(f"Ahorro total: ${resultado['ahorro_total_periodo']:,.0f}")

    # Meses hasta quiebra
    meses = calc_meses_hasta_quiebra(-200_000, 500_000)
    assert meses == 2
    assert calc_meses_hasta_quiebra(100_000) is None
    print(f"Meses hasta quiebra: {meses}")

    print("\n✅ Todos los tests pasaron.")
