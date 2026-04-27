"""
pdf_exporter.py — Exporta análisis a PDF usando fpdf2.
"""

import re
from datetime import datetime


def _strip_emojis(text: str) -> str:
    """Elimina emojis y símbolos fuera del rango Latin-1."""
    result = []
    for char in text:
        cp = ord(char)
        if cp < 0x0100 or 0x00C0 <= cp <= 0x00FF:
            result.append(char)
    return ''.join(result)


def _clean_markdown(text: str) -> str:
    """Convierte markdown a texto con marcadores propios para el render PDF."""
    # Headers → marcadores propios (evitar conflicto con ### en el texto)
    text = re.sub(r'^#{1,3}\s+(.+)$', r'H3:\1', text, flags=re.MULTILINE)
    text = re.sub(r'^#{4,6}\s+(.+)$', r'H2:\1', text, flags=re.MULTILINE)
    # Bold/italic → texto plano
    text = re.sub(r'\*{3}(.*?)\*{3}', r'\1', text)
    text = re.sub(r'\*{2}(.*?)\*{2}', r'\1', text)
    text = re.sub(r'\*(.*?)\*', r'\1', text)
    text = re.sub(r'_{2}(.*?)_{2}', r'\1', text)
    text = re.sub(r'_(.*?)_', r'\1', text)
    # Links → solo texto
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
    # Líneas horizontales vacías
    text = re.sub(r'^[-*_]{3,}\s*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def _safe_latin1(text: str) -> str:
    """Convierte texto a Latin-1 seguro para fuentes built-in de fpdf2."""
    text = _strip_emojis(text)
    replacements = {
        '\u2019': "'", '\u2018': "'", '\u201c': '"', '\u201d': '"',
        '\u2013': '-', '\u2014': '--', '\u2026': '...', '\u00b1': '+/-',
        '\u20ac': 'EUR', '\u00b0': 'deg', '\u2022': '-', '\u2192': '->',
        '\u2190': '<-', '\u2191': '^', '\u2193': 'v', '\u00d7': 'x',
        '\u00f7': '/', '\u2265': '>=', '\u2264': '<=', '\u2260': '!=',
    }
    for char, repl in replacements.items():
        text = text.replace(char, repl)
    return text.encode('latin-1', errors='replace').decode('latin-1')


def _mcell(pdf, h, text):
    """multi_cell que siempre resetea X al margen izquierdo al terminar."""
    try:
        pdf.multi_cell(0, h, text)
    except Exception:
        pass
    pdf.set_x(pdf.l_margin)


def export_analysis_to_pdf(
    title: str,
    module_name: str,
    content_text: str,
    ticker: str = "",
) -> bytes:
    """Genera un PDF del análisis y retorna los bytes."""
    try:
        from fpdf import FPDF
    except ImportError:
        raise RuntimeError("fpdf2 no instalado. Corre: py -m pip install fpdf2")

    pdf = FPDF()
    pdf.set_margins(15, 15, 15)
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()

    # ── Header band ─────────────────────────────────────────────────────────
    pdf.set_fill_color(12, 20, 34)
    pdf.rect(0, 0, 220, 28, style='F')

    pdf.set_y(6)
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(20, 184, 166)
    pdf.cell(0, 9, "InversionesIA", new_x="LMARGIN", new_y="NEXT", align="C")

    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(148, 163, 184)
    pdf.cell(0, 6, "Analisis financiero potenciado por IA", new_x="LMARGIN", new_y="NEXT", align="C")

    pdf.ln(8)

    # ── Título del análisis ──────────────────────────────────────────────────
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_text_color(20, 20, 30)
    titulo = title
    if ticker:
        titulo = titulo + " - " + ticker.upper()
    _mcell(pdf, 7, _safe_latin1(titulo))

    # ── Metadata ─────────────────────────────────────────────────────────────
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(100, 100, 110)
    fecha = datetime.now().strftime("%d/%m/%Y %H:%M")
    meta = "Modulo: " + module_name + "  |  Generado: " + fecha
    _mcell(pdf, 5, _safe_latin1(meta))
    pdf.ln(2)

    # ── Disclaimer ───────────────────────────────────────────────────────────
    pdf.set_fill_color(255, 248, 220)
    pdf.set_draw_color(245, 158, 11)
    pdf.set_font("Helvetica", "B", 7)
    pdf.set_text_color(120, 80, 0)
    disclaimer = (
        "AVISO LEGAL: Este analisis es generado por inteligencia artificial "
        "con fines informativos y educativos unicamente. NO constituye "
        "asesoria financiera ni recomendacion de inversion. Consulta a un "
        "asesor financiero certificado antes de tomar decisiones de inversion."
    )
    try:
        pdf.multi_cell(0, 4, _safe_latin1(disclaimer), border=1, fill=True)
    except Exception:
        pass
    pdf.set_x(pdf.l_margin)
    pdf.ln(4)

    # ── Línea decorativa ─────────────────────────────────────────────────────
    pdf.set_draw_color(20, 184, 166)
    pdf.set_line_width(0.5)
    pdf.line(15, pdf.get_y(), 195, pdf.get_y())
    pdf.ln(4)

    # ── Contenido ────────────────────────────────────────────────────────────
    clean = _clean_markdown(content_text)
    lines = clean.split('\n')

    for line in lines:
        line = line.strip()
        if not line:
            pdf.ln(2)
            continue

        # Header H3 (grande, teal, con línea)
        if line.startswith('H3:'):
            text = _safe_latin1(line[3:].strip())
            pdf.ln(3)
            pdf.set_font("Helvetica", "B", 12)
            pdf.set_text_color(20, 184, 166)
            _mcell(pdf, 6, text)
            pdf.set_draw_color(20, 184, 166)
            pdf.set_line_width(0.3)
            pdf.line(15, pdf.get_y(), 195, pdf.get_y())
            pdf.ln(2)

        # Header H2 (sub-sección)
        elif line.startswith('H2:'):
            text = _safe_latin1(line[3:].strip())
            pdf.ln(2)
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_text_color(20, 184, 166)
            _mcell(pdf, 5, text)
            pdf.ln(1)

        # Encabezados numéricos (ej: "1. Análisis de...")
        elif re.match(r'^\d+[\.\)]\s', line):
            pdf.ln(2)
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_text_color(12, 20, 34)
            _mcell(pdf, 5, _safe_latin1(line))

        # Bullets: "- ", "* " o "• "
        elif re.match(r'^[-*•]\s', line):
            text = '    - ' + _safe_latin1(line[2:].strip())
            pdf.set_font("Helvetica", "", 10)
            pdf.set_text_color(30, 30, 40)
            _mcell(pdf, 5, text)

        # Separadores tipo "--- sección ---"
        elif re.match(r'^[-=]{2,}', line):
            pdf.set_font("Helvetica", "B", 9)
            pdf.set_text_color(20, 184, 166)
            _mcell(pdf, 5, _safe_latin1(line))

        # Texto normal
        else:
            pdf.set_font("Helvetica", "", 10)
            pdf.set_text_color(30, 30, 40)
            _mcell(pdf, 5, _safe_latin1(line))

    # ── Footer ────────────────────────────────────────────────────────────────
    pdf.set_y(-14)
    pdf.set_font("Helvetica", "I", 7)
    pdf.set_text_color(160, 160, 160)
    footer = "InversionesIA - Solo para fines informativos - Pagina " + str(pdf.page_no())
    pdf.cell(0, 5, _safe_latin1(footer), align="C")

    return bytes(pdf.output())
