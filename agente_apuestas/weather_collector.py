import sys
sys.stdout.reconfigure(encoding="utf-8")

"""
weather_collector.py
Obtiene el pronóstico del tiempo para el estadio del partido.

Fuente: Open-Meteo API (https://api.open-meteo.com) — gratis, sin key.
        Para las coordenadas del estadio usa la Open-Meteo geocoding API o
        coordenadas hardcodeadas por ciudad de los estadios más comunes.

Variables meteorológicas:
  temperatura (°C), precipitación (mm/h), viento (km/h), código de clima

Impacto en el modelo:
  Lluvia fuerte (>5mm/h):  lambda_goles −10% (juego más lento, menos córners)
  Viento fuerte (>50km/h): lambda_goles −15% (balón impredecible, menos precisión)
  Nieve / tormenta:        lambda_goles −20% + confidence_penalty −10
  Condiciones normales:    sin ajuste
"""

import requests
from datetime import datetime, timezone
from pathlib import Path


# ─────────────────────────────────────────────────────────────────────────────
# COORDENADAS DE ESTADIOS / CIUDADES MÁS COMUNES
# ─────────────────────────────────────────────────────────────────────────────
# Fuente: aproximaciones a ciudad del estadio.
# Si la ciudad del fixture no está aquí, usamos geocoding de Open-Meteo.

CIUDADES_COORD = {
    # Inglaterra
    "London":      (51.505, -0.118),
    "Manchester":  (53.483, -2.200),
    "Liverpool":   (53.408, -2.991),
    "Birmingham":  (52.486, -1.890),
    # España
    "Madrid":      (40.416, -3.703),
    "Barcelona":   (41.385, 2.173),
    "Seville":     (37.389, -5.984),
    "Valencia":    (39.469, -0.376),
    # Italia
    "Rome":        (41.902, 12.496),
    "Milan":       (45.464, 9.190),
    "Turin":       (45.070, 7.687),
    "Naples":      (40.851, 14.268),
    # Alemania
    "Munich":      (48.135, 11.582),
    "Dortmund":    (51.514, 7.468),
    "Berlin":      (52.520, 13.405),
    "Hamburg":     (53.575, 9.995),
    # Francia
    "Paris":       (48.856, 2.352),
    "Lyon":        (45.748, 4.847),
    "Marseille":   (43.296, 5.381),
    # Chile
    "Santiago":    (-33.457, -70.648),
    "Concepcion":  (-36.820, -73.044),
    # Brasil / Libertadores
    "Sao Paulo":   (-23.548, -46.636),
    "Rio de Janeiro": (-22.906, -43.173),
    "Buenos Aires": (-34.614, -58.445),
    "Montevideo":  (-34.901, -56.165),
    "Bogota":      (4.711, -74.072),
    "Lima":        (-12.046, -77.043),
}

# Códigos de clima Open-Meteo → descripción + impacto
CODIGOS_CLIMA = {
    0:  ("Despejado",          0.00,   0),
    1:  ("Mayormente despejado",0.00,  0),
    2:  ("Parcialmente nublado",0.00,  0),
    3:  ("Nublado",             0.00,  0),
    45: ("Niebla",             -0.05,  -3),
    48: ("Niebla con escarcha", -0.05, -3),
    51: ("Llovizna ligera",    -0.03,  0),
    53: ("Llovizna moderada",  -0.05, -3),
    55: ("Llovizna densa",     -0.08, -5),
    61: ("Lluvia ligera",      -0.05, -3),
    63: ("Lluvia moderada",    -0.10, -5),
    65: ("Lluvia fuerte",      -0.15, -7),
    71: ("Nieve ligera",       -0.15, -7),
    73: ("Nieve moderada",     -0.20, -10),
    75: ("Nieve fuerte",       -0.25, -10),
    77: ("Granizo",            -0.20, -10),
    80: ("Chubascos ligeros",  -0.05, -3),
    81: ("Chubascos moderados",-0.10, -5),
    82: ("Chubascos violentos",-0.18, -8),
    95: ("Tormenta",           -0.20, -10),
    96: ("Tormenta con granizo",-0.25,-10),
    99: ("Tormenta fuerte",    -0.25, -10),
}


# ─────────────────────────────────────────────────────────────────────────────
# GEOCODING
# ─────────────────────────────────────────────────────────────────────────────

def _geocode(ciudad: str) -> tuple[float, float] | None:
    """
    Busca coordenadas de una ciudad.
    Primero revisa diccionario hardcodeado; si no, usa Open-Meteo geocoding.
    """
    # Buscar coincidencia parcial en el diccionario
    for key, coords in CIUDADES_COORD.items():
        if key.lower() in ciudad.lower() or ciudad.lower() in key.lower():
            return coords

    # Fallback: geocoding Open-Meteo
    try:
        r = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": ciudad, "count": 1, "language": "en", "format": "json"},
            timeout=8,
        )
        if r.status_code == 200:
            results = r.json().get("results", [])
            if results:
                return (results[0]["latitude"], results[0]["longitude"])
    except Exception:
        pass

    return None


# ─────────────────────────────────────────────────────────────────────────────
# FUNCIÓN PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────

def get_weather(ciudad: str, fecha_iso: str) -> dict:
    """
    Obtiene el pronóstico del tiempo para una ciudad en una fecha/hora dada.

    Args:
        ciudad:    ciudad del estadio (de fixture["ciudad"])
        fecha_iso: fecha+hora del partido en ISO 8601 (ej: "2026-03-22T15:00:00+00:00")

    Retorna dict con:
      disponible:           bool
      ciudad:               str
      temperatura:          float | None  (°C)
      precipitacion:        float | None  (mm/h)
      viento:               float | None  (km/h)
      codigo_clima:         int | None
      descripcion:          str
      ajuste_lambda:        float  (−0.25 a 0.0)
      confidence_penalty:   int    (−10 a 0)
      adverso:              bool   (True si condiciones afectan el partido)
    """
    resultado = {
        "disponible":         False,
        "ciudad":             ciudad or "Desconocida",
        "temperatura":        None,
        "precipitacion":      None,
        "viento":             None,
        "codigo_clima":       None,
        "descripcion":        "Sin datos",
        "ajuste_lambda":      0.0,
        "confidence_penalty": 0,
        "adverso":            False,
    }

    if not ciudad:
        print(f"  [INFO] weather — ciudad no disponible en el fixture")
        return resultado

    # Coordenadas
    coords = _geocode(ciudad)
    if not coords:
        print(f"  [INFO] weather — no se encontraron coords para '{ciudad}'")
        return resultado

    lat, lon = coords

    # Hora del partido
    try:
        if fecha_iso:
            dt = datetime.fromisoformat(fecha_iso)
            hora_utc = dt.astimezone(timezone.utc)
            fecha_str = hora_utc.strftime("%Y-%m-%d")
            hora_idx  = hora_utc.hour
        else:
            from datetime import date
            fecha_str = date.today().isoformat()
            hora_idx  = 15
    except Exception:
        from datetime import date
        fecha_str = date.today().isoformat()
        hora_idx  = 15

    # Consulta Open-Meteo
    try:
        r = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude":   lat,
                "longitude":  lon,
                "hourly":     "temperature_2m,precipitation,windspeed_10m,weathercode",
                "start_date": fecha_str,
                "end_date":   fecha_str,
                "timezone":   "UTC",
            },
            timeout=10,
        )
        if r.status_code != 200:
            print(f"  [FALLO] weather HTTP {r.status_code}")
            return resultado

        hourly = r.json().get("hourly", {})
        horas  = hourly.get("time", [])
        if not horas or hora_idx >= len(horas):
            hora_idx = min(hora_idx, len(horas) - 1) if horas else 0

        temp  = hourly.get("temperature_2m",  [None])[hora_idx]
        precip = hourly.get("precipitation",   [None])[hora_idx]
        viento = hourly.get("windspeed_10m",   [None])[hora_idx]
        codigo = hourly.get("weathercode",     [None])[hora_idx]

        # Ajustes por condición meteorológica
        clima_info = CODIGOS_CLIMA.get(int(codigo) if codigo is not None else 0,
                                       ("Desconocido", 0.0, 0))
        descripcion, ajuste_clima, pen_clima = clima_info

        # Ajuste adicional por viento
        ajuste_viento = 0.0
        pen_viento    = 0
        if viento and viento > 70:
            ajuste_viento = -0.20
            pen_viento    = -8
            print(f"  [INFO] weather — viento extremo {viento:.0f} km/h")
        elif viento and viento > 50:
            ajuste_viento = -0.10
            pen_viento    = -5

        ajuste_total = round(ajuste_clima + ajuste_viento, 3)
        pen_total    = pen_clima + pen_viento

        resultado.update({
            "disponible":         True,
            "ciudad":             ciudad,
            "temperatura":        round(temp,   1) if temp   is not None else None,
            "precipitacion":      round(precip, 2) if precip is not None else None,
            "viento":             round(viento, 1) if viento is not None else None,
            "codigo_clima":       codigo,
            "descripcion":        descripcion,
            "ajuste_lambda":      ajuste_total,
            "confidence_penalty": pen_total,
            "adverso":            ajuste_total < -0.05,
        })

        print(f"  [OK] weather {ciudad} — {descripcion} | "
              f"temp={temp}°C precip={precip}mm/h viento={viento}km/h | "
              f"ajuste_lambda={ajuste_total:+.2f} pen={pen_total}")

    except Exception as e:
        print(f"  [FALLO] weather — {e}")

    return resultado


# ─────────────────────────────────────────────────────────────────────────────
# TEST
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("TEST — weather_collector.py")
    print("=" * 60)
    print()

    test_casos = [
        ("London",    "2026-03-22T15:00:00+00:00"),
        ("Madrid",    "2026-03-22T20:00:00+00:00"),
        ("Santiago",  "2026-03-22T23:00:00+00:00"),
        ("CiudadXYZ", "2026-03-22T18:00:00+00:00"),  # ciudad desconocida
    ]

    for ciudad, fecha in test_casos:
        print(f"\n→ {ciudad} @ {fecha[:16]}")
        w = get_weather(ciudad, fecha)
        if w["disponible"]:
            print(f"  {w['descripcion']} | {w['temperatura']}°C | "
                  f"lluvia {w['precipitacion']}mm/h | viento {w['viento']}km/h")
            print(f"  ajuste_lambda={w['ajuste_lambda']:+.2f} | "
                  f"pen={w['confidence_penalty']} | adverso={w['adverso']}")
        else:
            print(f"  Sin datos ({w['descripcion']})")
