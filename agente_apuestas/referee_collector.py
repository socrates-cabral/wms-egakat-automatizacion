import sys
sys.stdout.reconfigure(encoding="utf-8")

"""
referee_collector.py
Obtiene estadísticas del árbitro asignado a un fixture.

Fuente: api-sports.io /fixtures?id={fixture_id} (el árbitro está en la respuesta del fixture)
        No existe un endpoint /referees con stats en el plan gratuito.

Métricas calculadas a partir del historial del árbitro en la temporada:
  - tarjetas_por_partido:   promedio amarillas + rojas por partido
  - penaltis_por_partido:   promedio penaltis pitados por partido
  - perfil:                 "estricto" | "permisivo" | "normal"
  - impacto_confianza:      int (−5 a +5) para confidence_scorer

Si el árbitro no está disponible aún (< 2h antes del partido):
  Retorna {disponible: False, nombre: None, ...}
"""

import requests
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent))
from config import HEADERS_APISPORTS, APISPORTS_BASE, SEASON_ACTUAL


# ─────────────────────────────────────────────────────────────────────────────
# PERFIL DEL ÁRBITRO
# ─────────────────────────────────────────────────────────────────────────────

def _clasificar_perfil(tarjetas_pp: float, penaltis_pp: float) -> dict:
    """
    Clasifica el perfil del árbitro y calcula el impacto en confianza.

    Reglas:
      Tarjetas/partido > 4.5 → estricto  (más goles/penaltis → favorece Over)
      Tarjetas/partido < 2.5 → permisivo (menos interrupciones → partido fluido)
      Penaltis/partido > 0.5 → pitador   (aumenta probabilidad de Over y BTTS)
    """
    perfil = "normal"
    impacto = 0
    notas = []

    if tarjetas_pp >= 4.5:
        perfil = "estricto"
        notas.append(f"{tarjetas_pp:.1f} tarjetas/pj — árbitro estricto")
        impacto -= 3   # más interrupciones → partido más cerrado
    elif tarjetas_pp <= 2.5:
        perfil = "permisivo"
        notas.append(f"{tarjetas_pp:.1f} tarjetas/pj — árbitro permisivo")
        impacto += 2   # flujo continuo → más goles posibles

    if penaltis_pp >= 0.5:
        notas.append(f"{penaltis_pp:.2f} penaltis/pj — pitador frecuente")
        impacto += 3   # penaltis extra = más goles
    elif penaltis_pp <= 0.1:
        notas.append(f"{penaltis_pp:.2f} penaltis/pj — raro en pitarlos")

    return {
        "perfil":             perfil,
        "impacto_confianza":  impacto,
        "notas":              notas,
    }


# ─────────────────────────────────────────────────────────────────────────────
# FUNCIÓN PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────

def get_referee_stats(fixture_id: int) -> dict:
    """
    Obtiene el árbitro del fixture y busca sus stats históricas.

    Paso 1: GET /fixtures?id={fixture_id} → obtener nombre del árbitro
    Paso 2: GET /fixtures?referee={nombre}&season={SEASON_ACTUAL} → historial

    Retorna dict con:
      disponible:           bool
      nombre:               str | None
      partidos_arbitrados:  int
      tarjetas_amarillas:   int
      tarjetas_rojas:       int
      penaltis_pitados:     int
      tarjetas_por_partido: float | None
      penaltis_por_partido: float | None
      perfil:               "estricto"|"permisivo"|"normal"
      impacto_confianza:    int  (pasado a confidence_scorer)
      notas:                list[str]
    """
    resultado = {
        "disponible":           False,
        "nombre":               None,
        "partidos_arbitrados":  0,
        "tarjetas_amarillas":   0,
        "tarjetas_rojas":       0,
        "penaltis_pitados":     0,
        "tarjetas_por_partido": None,
        "penaltis_por_partido": None,
        "perfil":               "normal",
        "impacto_confianza":    0,
        "notas":                [],
    }

    # ── Paso 1: nombre del árbitro ────────────────────────────────────────────
    try:
        r = requests.get(
            f"{APISPORTS_BASE}/fixtures",
            headers=HEADERS_APISPORTS,
            params={"id": fixture_id},
            timeout=10,
        )
        if r.status_code != 200:
            print(f"  [FALLO] referee — fixture fetch HTTP {r.status_code}")
            return resultado

        fixtures = r.json().get("response", [])
        if not fixtures:
            print(f"  [INFO] referee — fixture {fixture_id} no encontrado")
            return resultado

        nombre_arbitro = fixtures[0].get("fixture", {}).get("referee")
        if not nombre_arbitro:
            print(f"  [INFO] referee — árbitro no asignado aún (fixture={fixture_id})")
            return resultado

        # Limpiar nombre (a veces viene como "Nombre Apellido, País")
        nombre_limpio = nombre_arbitro.split(",")[0].strip()
        resultado["nombre"] = nombre_limpio
        print(f"  [OK] referee — árbitro: {nombre_limpio}")

    except Exception as e:
        print(f"  [FALLO] referee — fixture fetch: {e}")
        return resultado

    # ── Paso 2: historial del árbitro en la temporada ─────────────────────────
    try:
        r2 = requests.get(
            f"{APISPORTS_BASE}/fixtures",
            headers=HEADERS_APISPORTS,
            params={
                "referee": nombre_limpio,
                "season":  SEASON_ACTUAL,
            },
            timeout=10,
        )
        if r2.status_code != 200:
            print(f"  [INFO] referee — historial HTTP {r2.status_code} (continuando sin stats)")
            resultado["disponible"] = True
            return resultado

        historial = r2.json().get("response", [])
        terminados = [
            f for f in historial
            if f.get("fixture", {}).get("status", {}).get("short") in {"FT", "AET", "PEN"}
        ]

        if not terminados:
            print(f"  [INFO] referee {nombre_limpio} — sin historial terminado en {SEASON_ACTUAL}")
            resultado["disponible"] = True
            return resultado

        # Agregar estadísticas
        amarillas = 0
        rojas     = 0
        penaltis  = 0

        for f in terminados:
            stats = f.get("statistics", [])
            for equipo_stats in stats:
                for s in equipo_stats if isinstance(equipo_stats, list) else [equipo_stats]:
                    tipo = (s.get("type") or "").lower()
                    val  = s.get("value") or 0
                    if "yellow" in tipo:
                        amarillas += int(val)
                    elif "red" in tipo:
                        rojas += int(val)
                    elif "penalty" in tipo and "scored" in tipo:
                        penaltis += int(val)

        n = len(terminados)
        tpp = (amarillas + rojas) / n if n else 0
        ppp = penaltis / n if n else 0

        clasificacion = _clasificar_perfil(tpp, ppp)

        resultado.update({
            "disponible":           True,
            "partidos_arbitrados":  n,
            "tarjetas_amarillas":   amarillas,
            "tarjetas_rojas":       rojas,
            "penaltis_pitados":     penaltis,
            "tarjetas_por_partido": round(tpp, 2),
            "penaltis_por_partido": round(ppp, 3),
            **clasificacion,
        })

        print(f"  [OK] referee {nombre_limpio} — {n} partidos | "
              f"tarjetas/pj={tpp:.1f} | penaltis/pj={ppp:.2f} | "
              f"perfil={clasificacion['perfil']}")

    except Exception as e:
        print(f"  [FALLO] referee — historial: {e}")
        resultado["disponible"] = True  # al menos tenemos el nombre

    return resultado


# ─────────────────────────────────────────────────────────────────────────────
# TEST
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("TEST — referee_collector.py")
    print("=" * 60)
    print()
    print("Requiere fixture_id válido con árbitro asignado.")
    print("Ejemplo: py fixtures_collector.py para obtener un fixture_id de hoy.")
    print()

    TEST_FIXTURE_ID = 1507116

    ref = get_referee_stats(TEST_FIXTURE_ID)
    print()
    print(f"Árbitro:    {ref['nombre'] or 'No disponible'}")
    print(f"Disponible: {ref['disponible']}")
    if ref["disponible"] and ref["nombre"]:
        print(f"Partidos:   {ref['partidos_arbitrados']}")
        print(f"Tarjetas/pj:{ref['tarjetas_por_partido']}")
        print(f"Penaltis/pj:{ref['penaltis_por_partido']}")
        print(f"Perfil:     {ref['perfil']}")
        print(f"Impacto:    {ref['impacto_confianza']:+d}")
        for nota in ref["notas"]:
            print(f"  - {nota}")
