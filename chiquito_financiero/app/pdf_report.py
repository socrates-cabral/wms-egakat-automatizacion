import sys
sys.stdout.reconfigure(encoding="utf-8")

# pdf_report.py — Generador de reporte PDF mensual para Chiquito Finanzas
# Usa fpdf2. Retorna bytes para descarga desde Streamlit.

from fpdf import FPDF
from datetime import datetime


# ─── Colores (RGB) ─────────────────────────────────────────────────────────────
C_FONDO     = (13,  17,  23)   # #0d1117
C_PANEL     = (22,  27,  34)   # #161b22
C_BORDE     = (48,  54,  61)   # #30363d
C_TEXTO     = (230, 237, 243)  # #e6edf3
C_TEXTO2    = (139, 148, 158)  # #8b949e
C_VERDE     = (63,  185, 80)   # #3fb950
C_ROJO      = (248, 81,  73)   # #f85149
C_AMBAR     = (210, 153, 34)   # #d29922
C_AZUL      = (88,  166, 255)  # #58a6ff


def _fmt(valor: float) -> str:
    """Formatea como pesos chilenos."""
    return f"${valor:,.0f}"


def _txt(texto: str) -> str:
    """
    Normaliza texto a latin-1 para fuentes core de fpdf2.
    Reemplaza caracteres problemáticos por equivalentes ASCII.
    """
    reemplazos = {
        '\u2014': '--',   # em dash
        '\u2013': '-',    # en dash
        '\u2019': "'",    # comilla derecha
        '\u2018': "'",    # comilla izquierda
        '\u201c': '"',    # comilla doble izq
        '\u201d': '"',    # comilla doble der
        '\u00e9': 'e',    # é → e  (ya está en latin-1 pero por si acaso)
        '\u2265': '>=',   # ≥
        '\u2264': '<=',   # ≤
    }
    for orig, repl in reemplazos.items():
        texto = texto.replace(orig, repl)
    # Eliminar cualquier caracter fuera de latin-1
    return texto.encode('latin-1', errors='replace').decode('latin-1')


class ChiquitoPDF(FPDF):
    """Clase base del PDF con estilos corporativos oscuros."""

    def cell(self, w=0, h=0, text='', *args, **kwargs):
        """Sobrescribe cell para normalizar texto a latin-1 automáticamente."""
        super().cell(w, h, _txt(str(text)), *args, **kwargs)

    def header(self):
        # Fondo negro del encabezado
        self.set_fill_color(*C_PANEL)
        self.rect(0, 0, 210, 20, 'F')
        # Línea inferior del encabezado
        self.set_draw_color(*C_BORDE)
        self.line(0, 20, 210, 20)
        # Título
        self.set_font('Courier', 'B', 13)
        self.set_text_color(*C_TEXTO)
        self.set_xy(10, 5)
        self.cell(0, 10, 'Chiquito Finanzas -- Reporte Mensual', align='L')
        self.set_font('Courier', '', 9)
        self.set_text_color(*C_TEXTO2)
        self.set_xy(10, 12)
        self.cell(0, 6, f'Generado el {datetime.now().strftime("%d-%b-%Y %H:%M")}', align='L')
        self.ln(15)

    def footer(self):
        self.set_y(-12)
        self.set_font('Courier', '', 8)
        self.set_text_color(*C_TEXTO2)
        self.cell(0, 10, f'Página {self.page_no()} | Control de Gestión y Mejora Continua — Sócrates Cabral', align='C')

    def fondo_pagina(self):
        """Pinta el fondo de la página de negro."""
        self.set_fill_color(*C_FONDO)
        self.rect(0, 0, 210, 297, 'F')

    def seccion_titulo(self, titulo: str):
        """Encabezado de sección con borde inferior."""
        self.set_font('Courier', 'B', 11)
        self.set_text_color(*C_AZUL)
        self.set_fill_color(*C_PANEL)
        self.cell(0, 8, f'  {titulo}', fill=True, ln=True)
        self.set_draw_color(*C_BORDE)
        self.line(self.get_x(), self.get_y(), 200, self.get_y())
        self.ln(3)

    def kpi_box(self, x, y, w, h, valor: str, label: str, color_val=None):
        """Tarjeta KPI pequeña."""
        if color_val is None:
            color_val = C_TEXTO
        # Caja de fondo
        self.set_fill_color(*C_PANEL)
        self.set_draw_color(*C_BORDE)
        self.rect(x, y, w, h, 'FD')
        # Valor
        self.set_font('Courier', 'B', 12)
        self.set_text_color(*color_val)
        self.set_xy(x, y + 3)
        self.cell(w, 6, valor, align='C')
        # Label
        self.set_font('Courier', '', 7)
        self.set_text_color(*C_TEXTO2)
        self.set_xy(x, y + 10)
        self.cell(w, 4, label, align='C')

    def tabla_fila(self, cols: list, widths: list, es_cabecera: bool = False, color_row=None):
        """Dibuja una fila de tabla."""
        if es_cabecera:
            self.set_fill_color(*C_PANEL)
            self.set_font('Courier', 'B', 8)
            self.set_text_color(*C_AZUL)
        else:
            fondo = color_row if color_row else C_FONDO
            self.set_fill_color(*fondo)
            self.set_font('Courier', '', 8)
            self.set_text_color(*C_TEXTO)

        self.set_draw_color(*C_BORDE)
        for i, (col, w) in enumerate(zip(cols, widths)):
            self.cell(w, 6, str(col), border=1, fill=True, align='R' if i > 0 else 'L')
        self.ln()

    def semaforo(self, pct_pe: float, resultado: float):
        """Bloque de semáforo de salud financiera."""
        if resultado > 0 and pct_pe >= 80:
            color, estado, icono = C_VERDE, 'SALUDABLE', '[OK]'
        elif resultado > -200_000 and pct_pe >= 50:
            color, estado, icono = C_AMBAR, 'EN RIESGO', '[!]'
        else:
            color, estado, icono = C_ROJO, 'CRITICO', '[!!]'

        x, y = self.get_x(), self.get_y()
        self.set_fill_color(*color)
        self.rect(x, y, 190, 14, 'F')
        self.set_font('Courier', 'B', 13)
        self.set_text_color(*C_FONDO)
        self.set_xy(x, y + 3)
        self.cell(190, 8, f'{icono} SALUD FINANCIERA: {estado}', align='C')
        self.ln(18)


def generar_reporte_mensual(mes: str, datos: dict) -> bytes:
    """
    Genera un PDF de 2 páginas con el resumen financiero mensual.
    datos: {ingresos, gastos, resultado, deuda_total, cuotas_mes, pe, pct_pe}
    Retorna bytes para descarga desde Streamlit.
    """
    pdf = ChiquitoPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_margins(10, 25, 10)

    # ─── PÁGINA 1: Resumen ejecutivo ─────────────────────────────────────────
    pdf.add_page()
    pdf.fondo_pagina()

    # Título del mes
    pdf.set_font('Courier', 'B', 16)
    pdf.set_text_color(*C_TEXTO)
    pdf.set_y(25)
    pdf.cell(0, 10, f'Resumen ejecutivo — {mes}', align='C', ln=True)
    pdf.ln(5)

    # Semáforo
    pdf.semaforo(datos.get('pct_pe', 0), datos.get('resultado', 0))

    # KPI cards (2 filas x 3)
    kpis_fila1 = [
        (_fmt(datos.get('ingresos', 0)),   'Ingresos del mes',    C_VERDE),
        (_fmt(datos.get('gastos', 0)),     'Gastos del mes',      C_ROJO),
        (_fmt(datos.get('resultado', 0)),  'Resultado neto',
            C_VERDE if datos.get('resultado', 0) >= 0 else C_ROJO),
    ]
    kpis_fila2 = [
        (_fmt(datos.get('deuda_total', 0)), 'Deuda total',        C_ROJO),
        (_fmt(datos.get('cuotas_mes', 0)),  'Cuotas bancarias',   C_AMBAR),
        (f"{datos.get('pct_pe', 0):.0f}%", '% Punto Equilibrio',
            C_VERDE if datos.get('pct_pe', 0) >= 70 else C_ROJO),
    ]

    y_kpi = pdf.get_y()
    for i, (val, lbl, col) in enumerate(kpis_fila1):
        pdf.kpi_box(10 + i * 64, y_kpi, 60, 18, val, lbl, col)

    pdf.set_y(y_kpi + 22)
    y_kpi2 = pdf.get_y()
    for i, (val, lbl, col) in enumerate(kpis_fila2):
        pdf.kpi_box(10 + i * 64, y_kpi2, 60, 18, val, lbl, col)

    pdf.set_y(y_kpi2 + 25)
    pdf.ln(3)

    # ── Análisis rápido ──
    pdf.seccion_titulo('ANÁLISIS DEL MES')
    lineas_analisis = []
    resultado = datos.get('resultado', 0)
    pct_pe    = datos.get('pct_pe', 0)
    ingresos  = datos.get('ingresos', 0)
    pe        = datos.get('pe', 3_950_000)

    if resultado >= 0:
        lineas_analisis.append(f'+ Mes positivo: resultado de {_fmt(resultado)} sobre cero.')
    else:
        lineas_analisis.append(f'- Mes negativo: déficit de {_fmt(abs(resultado))} que consume capital de trabajo.')

    if pct_pe >= 100:
        lineas_analisis.append(f'+ Punto de equilibrio superado ({pct_pe:.0f}%).')
    elif pct_pe >= 70:
        lineas_analisis.append(f'~ Ventas al {pct_pe:.0f}% del PE. Necesita {_fmt(pe - ingresos)} más para equilibrarse.')
    else:
        lineas_analisis.append(f'! Ventas muy por debajo del PE ({pct_pe:.0f}%). Se requiere acción urgente.')

    for linea in lineas_analisis:
        pdf.set_font('Courier', '', 9)
        pdf.set_text_color(*C_TEXTO)
        pdf.cell(0, 6, linea, ln=True)
    pdf.ln(5)

    # ── Flujo de caja resumido ──
    pdf.seccion_titulo('FLUJO DE CAJA DEL MES')
    headers  = ['Concepto', 'Monto ($)']
    widths   = [130, 50]
    pdf.tabla_fila(headers, widths, es_cabecera=True)

    filas_flujo = [
        ('Ingresos operacionales',       _fmt(datos.get('ingresos', 0))),
        ('(-) Gastos operacionales',     _fmt(datos.get('gastos', 0))),
        ('(-) Cuotas bancarias (est.)',   _fmt(datos.get('cuotas_mes', 0))),
        ('= Resultado neto estimado',    _fmt(resultado - datos.get('cuotas_mes', 0))),
    ]
    for i, (concepto, monto) in enumerate(filas_flujo):
        color = C_PANEL if i % 2 == 0 else C_FONDO
        pdf.tabla_fila([concepto, monto], widths, color_row=color)

    pdf.ln(5)

    # ─── PÁGINA 2: Estado de deuda y recomendaciones ─────────────────────────
    pdf.add_page()
    pdf.fondo_pagina()

    pdf.set_y(25)
    pdf.seccion_titulo('ESTADO DE DEUDA')

    # Tabla de deuda con defaults
    from calculators import DEUDAS_DEFAULT
    headers_d = ['Instrumento', 'Tipo', 'Saldo ($)', 'Cuota/mes ($)', 'Tasa %']
    widths_d  = [60, 25, 40, 40, 25]
    pdf.tabla_fila(headers_d, widths_d, es_cabecera=True)

    for i, d in enumerate(DEUDAS_DEFAULT):
        color = C_PANEL if i % 2 == 0 else C_FONDO
        pdf.tabla_fila(
            [d['acreedor'], d['tipo'], _fmt(d['saldo']), _fmt(d['cuota']), f"{d['tasa']:.1f}%"],
            widths_d, color_row=color
        )

    # Total deuda
    pdf.set_font('Courier', 'B', 9)
    pdf.set_text_color(*C_AMBAR)
    pdf.set_fill_color(*C_PANEL)
    pdf.set_draw_color(*C_BORDE)
    total_s = sum(d['saldo'] for d in DEUDAS_DEFAULT)
    total_c = sum(d['cuota'] for d in DEUDAS_DEFAULT)
    pdf.cell(85, 6, 'TOTAL', border=1, fill=True)
    pdf.cell(40, 6, _fmt(total_s), border=1, fill=True, align='R')
    pdf.cell(40, 6, _fmt(total_c), border=1, fill=True, align='R')
    pdf.cell(25, 6, '', border=1, fill=True)
    pdf.ln(8)

    # ── Recomendaciones del mes ──
    pdf.seccion_titulo('RECOMENDACIONES PRIORITARIAS')
    recomendaciones = [
        "1. Renegociar alquiler del taller ($700K → $400K) — ahorro de $300K/mes.",
        "2. Separar gastos personales de la caja del negocio ($80K/mes).",
        "3. Escalar ventas hacia los $3.5M/mes para alcanzar el punto de equilibrio.",
        "4. Evaluar pago anticipado de CMR Falabella (tasa más alta: 3.3%/mes).",
    ]
    pdf.set_font('Courier', '', 9)
    pdf.set_text_color(*C_TEXTO)
    for rec in recomendaciones:
        pdf.cell(0, 6, rec, ln=True)

    pdf.ln(5)

    # ── Firma ──
    pdf.set_font('Courier', '', 8)
    pdf.set_text_color(*C_TEXTO2)
    pdf.cell(0, 5, 'Generado por Chiquito Finanzas v1.0 — Sócrates Cabral / Control de Gestión y Mejora Continua / Egakat SPA', ln=True, align='C')

    return bytes(pdf.output())


# ─── Test manual ──────────────────────────────────────────────────────────────
if __name__ == '__main__':
    datos_test = {
        'ingresos':    1_964_928,
        'gastos':      1_617_387,
        'resultado':     347_541,
        'deuda_total': 29_644_120,
        'cuotas_mes':    918_903,
        'pe':          4_250_896,
        'pct_pe':           46.2,
    }
    pdf_bytes = generar_reporte_mensual('Feb-26', datos_test)
    out_path  = r'C:\ClaudeWork\chiquito_financiero\reporte_test.pdf'
    with open(out_path, 'wb') as f:
        f.write(pdf_bytes)
    print(f"PDF generado: {out_path} ({len(pdf_bytes):,} bytes)")
