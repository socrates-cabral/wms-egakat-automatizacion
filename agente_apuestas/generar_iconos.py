import sys
sys.stdout.reconfigure(encoding="utf-8")

"""
generar_iconos.py
Crea 3 iconos .ico para los accesos directos del escritorio.
  - agente_apuestas.ico   → fondo azul marino + cerebro/robot
  - dashboard_apuestas.ico → fondo verde oscuro + barras
  - ver_performance.ico    → fondo teal + flecha arriba
"""

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

OUT_DIR = Path(__file__).parent / "iconos"
OUT_DIR.mkdir(exist_ok=True)

SIZES = [256, 128, 64, 48, 32, 16]   # tamaños estándar .ico


def make_base(size, bg_color, radius_ratio=0.22):
    """Canvas cuadrado con fondo redondeado."""
    img  = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    r    = int(size * radius_ratio)
    draw.rounded_rectangle([0, 0, size - 1, size - 1], radius=r, fill=bg_color)
    return img, draw


def save_ico(frames, path):
    """Guarda lista de imágenes PIL como .ico multi-resolución."""
    frames[0].save(
        path,
        format="ICO",
        sizes=[(f.width, f.height) for f in frames],
        append_images=frames[1:],
    )
    print(f"[OK] {path.name}")


# ─────────────────────────────────────────────────────────────────
# 1. AGENTE APUESTAS — fondo azul índigo + ⚽ balón estilizado
# ─────────────────────────────────────────────────────────────────

def draw_agente(size):
    BG   = (30,  27,  75, 255)   # indigo-950
    C1   = (165, 180, 252, 255)  # indigo-300
    C2   = (255, 255, 255, 255)  # blanco

    img, draw = make_base(size, BG)
    cx = cy = size // 2
    r  = int(size * 0.30)        # radio del balón

    # Círculo exterior (balón)
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=C1, width=max(2, size // 40))

    # Pentágono central (huella del balón)
    import math
    pts = []
    r2  = int(r * 0.38)
    for i in range(5):
        angle = math.radians(-90 + i * 72)
        pts.append((cx + r2 * math.cos(angle), cy + r2 * math.sin(angle)))
    draw.polygon(pts, fill=C2)

    # 5 líneas radiales (costuras)
    r3  = int(r * 0.42)
    r4  = int(r * 0.95)
    for i in range(5):
        angle = math.radians(-90 + i * 72)
        x1 = cx + r3 * math.cos(angle)
        y1 = cy + r3 * math.sin(angle)
        x2 = cx + r4 * math.cos(angle)
        y2 = cy + r4 * math.sin(angle)
        draw.line([x1, y1, x2, y2], fill=C1, width=max(1, size // 50))

    return img


# ─────────────────────────────────────────────────────────────────
# 2. DASHBOARD APUESTAS — fondo verde + barras chart
# ─────────────────────────────────────────────────────────────────

def draw_dashboard(size):
    BG   = (5,  46,  22, 255)   # green-950
    BAR1 = (34, 197, 94, 255)   # green-500
    BAR2 = (74, 222, 128, 255)  # green-400
    BAR3 = (187, 247, 208, 255) # green-200
    LINE = (167, 243, 208, 255) # green-200

    img, draw = make_base(size, BG)

    pad  = int(size * 0.14)
    w    = size - 2 * pad
    h    = size - 2 * pad

    # Línea base (eje X)
    y_base = pad + h
    draw.line([pad, y_base, pad + w, y_base], fill=LINE, width=max(1, size // 64))

    # 3 barras verticales de distintas alturas
    bw   = int(w * 0.18)   # ancho de cada barra
    gap  = int(w * 0.10)
    total_bars = 3 * bw + 2 * gap
    x0   = pad + (w - total_bars) // 2

    heights = [0.55, 0.80, 0.45]   # relativo a h
    colors  = [BAR1, BAR2, BAR3]

    for i, (ht, col) in enumerate(zip(heights, colors)):
        bh   = int(h * ht)
        x    = x0 + i * (bw + gap)
        y_t  = y_base - bh
        r    = max(2, bw // 4)
        draw.rounded_rectangle([x, y_t, x + bw, y_base], radius=r, fill=col)

    # Línea de tendencia (por encima)
    pts = []
    for i, ht in enumerate(heights):
        bh  = int(h * ht)
        x   = x0 + i * (bw + gap) + bw // 2
        pts.append((x, y_base - bh - int(size * 0.04)))
    if len(pts) >= 2:
        draw.line(pts, fill=(255, 255, 255, 200), width=max(1, size // 48))
        for px, py in pts:
            cr = max(2, size // 32)
            draw.ellipse([px - cr, py - cr, px + cr, py + cr], fill=(255, 255, 255, 220))

    return img


# ─────────────────────────────────────────────────────────────────
# 3. VER PERFORMANCE — fondo teal + línea ascendente + flecha
# ─────────────────────────────────────────────────────────────────

def draw_performance(size):
    import math
    BG    = (8,  51,  68, 255)  # cyan-950
    LINE  = (34, 211, 238, 255) # cyan-400
    ARROW = (255, 255, 255, 255)
    FILL  = (34, 211, 238, 60)  # transparente

    img, draw = make_base(size, BG)

    pad    = int(size * 0.16)
    w      = size - 2 * pad
    h      = size - 2 * pad
    x0, y0 = pad, pad + h        # esquina inferior izquierda
    x1, y1 = pad + w, pad        # esquina superior derecha

    # Línea de tendencia (diagonal con suavizado)
    puntos = [
        (x0,                   y0),
        (x0 + int(w * 0.30),   y0 - int(h * 0.30)),
        (x0 + int(w * 0.55),   y0 - int(h * 0.45)),
        (x0 + int(w * 0.75),   y0 - int(h * 0.65)),
        (x1,                   y1 + int(h * 0.04)),
    ]

    # Área rellena bajo la curva
    poly = puntos + [(x1, y0), (x0, y0)]
    draw.polygon(poly, fill=FILL)

    # Línea principal
    lw = max(2, size // 36)
    draw.line(puntos, fill=LINE, width=lw)

    # Flecha al final
    tip    = puntos[-1]
    prev   = puntos[-2]
    angle  = math.atan2(tip[1] - prev[1], tip[0] - prev[0])
    alen   = int(size * 0.14)
    aspread = math.radians(28)
    for sign in (+1, -1):
        ax = tip[0] - alen * math.cos(angle + sign * aspread)
        ay = tip[1] - alen * math.sin(angle + sign * aspread)
        draw.line([tip, (ax, ay)], fill=ARROW, width=lw)

    return img


# ─────────────────────────────────────────────────────────────────
# GENERAR LOS 3 .ICO
# ─────────────────────────────────────────────────────────────────

def generar_todos():
    configs = [
        ("agente_apuestas.ico",    draw_agente),
        ("dashboard_apuestas.ico", draw_dashboard),
        ("ver_performance.ico",    draw_performance),
    ]
    for filename, fn_draw in configs:
        frames = []
        for s in SIZES:
            frame = fn_draw(s).convert("RGBA")
            frames.append(frame)
        save_ico(frames, OUT_DIR / filename)

    print(f"\nIconos guardados en: {OUT_DIR}")
    return OUT_DIR


if __name__ == "__main__":
    generar_todos()
