import sys
sys.stdout.reconfigure(encoding="utf-8")

"""
lineup_collector.py
Obtiene equipos probables, formaciones, lesiones y jugadores en duda.
Fuente: api-sports.io /fixtures/lineups + /injuries

Logica:
  - Si el partido es dentro de < 1h: lineup CONFIRMADO disponible
  - Si el partido es hoy pero aun no hay oficial: retorna bajas + "Probable"
  - Si el partido es futuro: solo retorna lesiones/bajas conocidas
"""

import requests
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import HEADERS_APISPORTS, APISPORTS_BASE


# ─────────────────────────────────────────────────────────────────────────────
# LINEUP CONFIRMADO (disponible ~1h antes del partido)
# ─────────────────────────────────────────────────────────────────────────────

def get_lineup_confirmado(fixture_id: int) -> dict | None:
    """
    Consulta el lineup oficial de un partido.
    Retorna None si la API aun no lo tiene disponible.
    """
    url = f"{APISPORTS_BASE}/fixtures/lineups"
    response = requests.get(url, headers=HEADERS_APISPORTS,
                            params={"fixture": fixture_id}, timeout=30)

    if response.status_code != 200:
        print(f"[FALLO] lineup HTTP {response.status_code} fixture={fixture_id}")
        return None

    data = response.json().get("response", [])
    if not data:
        return None  # Lineup aun no publicado

    resultado = {}
    for equipo_data in data:
        equipo_id  = equipo_data["team"]["id"]
        equipo_nom = equipo_data["team"]["name"]
        formacion  = equipo_data.get("formation", "Desconocida")

        once = []
        for jugador in equipo_data.get("startXI", []):
            j = jugador["player"]
            once.append({
                "nombre":   j["name"],
                "numero":   j["number"],
                "posicion": j["pos"],   # G / D / M / F
                "id":       j["id"],
            })

        suplentes = []
        for jugador in equipo_data.get("substitutes", []):
            j = jugador["player"]
            suplentes.append({
                "nombre":   j["name"],
                "numero":   j["number"],
                "posicion": j["pos"],
                "id":       j["id"],
            })

        entrenador = equipo_data.get("coach", {}).get("name", "Desconocido")

        resultado[equipo_id] = {
            "nombre":     equipo_nom,
            "formacion":  formacion,
            "once":       once,
            "suplentes":  suplentes,
            "entrenador": entrenador,
            "confirmado": True,
        }

    return resultado if resultado else None


# ─────────────────────────────────────────────────────────────────────────────
# LESIONES Y BAJAS
# ─────────────────────────────────────────────────────────────────────────────

def get_lesiones(fixture_id: int) -> dict:
    """
    Retorna jugadores lesionados, suspendidos o en duda para un partido.

    Returns:
        Dict con 'home' y 'away', cada uno con listas 'bajas' y 'dudas'.
        Requiere que ambos home_team_id y away_team_id se lean del fixture.
    """
    url = f"{APISPORTS_BASE}/injuries"
    response = requests.get(url, headers=HEADERS_APISPORTS,
                            params={"fixture": fixture_id}, timeout=30)

    if response.status_code != 200:
        print(f"[FALLO] injuries HTTP {response.status_code} fixture={fixture_id}")
        return {"home": {"bajas": [], "dudas": []}, "away": {"bajas": [], "dudas": []}}

    data = response.json().get("response", [])

    # Separar por equipo (el primer equipo en la lista es el home)
    equipos_vistos = {}
    lesiones_por_equipo = {}

    for item in data:
        team_id  = item["team"]["id"]
        team_nom = item["team"]["name"]
        jugador  = item["player"]["name"]
        motivo   = item["player"]["reason"]  # "Injured" / "Suspended" / "Doubtful"

        if team_id not in equipos_vistos:
            equipos_vistos[team_id] = team_nom
            lesiones_por_equipo[team_id] = {
                "nombre": team_nom,
                "bajas":  [],
                "dudas":  [],
            }

        entrada = f"{jugador} ({motivo})"
        if "Doubtful" in motivo:
            lesiones_por_equipo[team_id]["dudas"].append(entrada)
        else:
            lesiones_por_equipo[team_id]["bajas"].append(entrada)

    # Convertir a formato home/away segun orden de aparicion
    equipos_lista = list(lesiones_por_equipo.keys())
    resultado = {
        "home": lesiones_por_equipo.get(equipos_lista[0], {"bajas": [], "dudas": []}) if len(equipos_lista) > 0 else {"bajas": [], "dudas": []},
        "away": lesiones_por_equipo.get(equipos_lista[1], {"bajas": [], "dudas": []}) if len(equipos_lista) > 1 else {"bajas": [], "dudas": []},
        "raw":  lesiones_por_equipo,  # Copia completa por team_id para cruzar con lineup
    }

    return resultado


# ─────────────────────────────────────────────────────────────────────────────
# FUNCION PRINCIPAL: lineup completo unificado
# ─────────────────────────────────────────────────────────────────────────────

def get_lineup_completo(fixture_id: int, home_id: int, away_id: int) -> dict:
    """
    Funcion central del modulo.
    Combina lineup confirmado + lesiones en un solo dict.

    Args:
        fixture_id: ID del partido
        home_id:    ID del equipo local (viene de fixtures_collector)
        away_id:    ID del equipo visitante

    Returns:
        {
          "fixture_id": int,
          "lineup_confirmado": bool,
          "home": {
              "nombre": str,
              "formacion": str,
              "once": [{"nombre", "numero", "posicion", "id"}],
              "suplentes": [...],
              "entrenador": str,
              "bajas": [str],
              "dudas": [str],
          },
          "away": { ...mismo esquema... },
          "nota": str | None   # Advertencia si lineup no disponible
        }
    """
    resultado = {
        "fixture_id":        fixture_id,
        "lineup_confirmado": False,
        "nota":              None,
        "home": {
            "nombre": "", "formacion": "?", "once": [],
            "suplentes": [], "entrenador": "?",
            "bajas": [], "dudas": [],
        },
        "away": {
            "nombre": "", "formacion": "?", "once": [],
            "suplentes": [], "entrenador": "?",
            "bajas": [], "dudas": [],
        },
    }

    # 1. Intentar lineup confirmado
    lineup = get_lineup_confirmado(fixture_id)

    if lineup:
        resultado["lineup_confirmado"] = True

        for lado, equipo_id in [("home", home_id), ("away", away_id)]:
            if equipo_id in lineup:
                eq = lineup[equipo_id]
                resultado[lado]["nombre"]     = eq["nombre"]
                resultado[lado]["formacion"]  = eq["formacion"]
                resultado[lado]["once"]       = eq["once"]
                resultado[lado]["suplentes"]  = eq["suplentes"]
                resultado[lado]["entrenador"] = eq["entrenador"]
            else:
                # Fallback: tomar el primer equipo disponible si home_id no matchea
                # (a veces los IDs difieren por temporada)
                for eq_id, eq_data in lineup.items():
                    if eq_id not in [home_id, away_id]:
                        continue
                    resultado[lado].update(eq_data)
    else:
        resultado["nota"] = "Lineup no confirmado aun — solo disponible ~1h antes del partido"

    # 2. Agregar lesiones (siempre, independiente del lineup)
    lesiones = get_lesiones(fixture_id)

    raw = lesiones.get("raw", {})
    for lado, equipo_id in [("home", home_id), ("away", away_id)]:
        if equipo_id in raw:
            resultado[lado]["bajas"] = raw[equipo_id]["bajas"]
            resultado[lado]["dudas"] = raw[equipo_id]["dudas"]
            if not resultado[lado]["nombre"]:
                resultado[lado]["nombre"] = raw[equipo_id]["nombre"]
        # Si no hay lesiones, las listas quedan vacias (correcto)

    # 3. Log resumen
    home_n = resultado["home"]["nombre"] or f"ID:{home_id}"
    away_n = resultado["away"]["nombre"] or f"ID:{away_id}"
    conf   = "CONFIRMADO" if resultado["lineup_confirmado"] else "PENDIENTE"
    bajas_h = len(resultado["home"]["bajas"])
    bajas_a = len(resultado["away"]["bajas"])

    print(f"[OK] lineup {home_n} vs {away_n} | {conf} | "
          f"Bajas: {home_n}={bajas_h} {away_n}={bajas_a}")

    return resultado


def formatear_lineup_texto(lineup: dict) -> str:
    """
    Convierte el dict de lineup en texto legible para el reporte.
    Usado por claude_agent.py para construir el bloque de equipos.
    """
    lineas = []
    conf = "CONFIRMADO" if lineup["lineup_confirmado"] else "PROBABLE (no confirmado)"
    lineas.append(f"EQUIPO [{conf}]")
    lineas.append("")

    for lado in ["home", "away"]:
        eq = lineup[lado]
        nombre    = eq.get("nombre", "?")
        formacion = eq.get("formacion", "?")
        entrenador = eq.get("entrenador", "?")
        once      = [j["nombre"] for j in eq.get("once", [])]

        # Posiciones
        porteros  = [j["nombre"] for j in eq.get("once", []) if j["posicion"] == "G"]
        defensas  = [j["nombre"] for j in eq.get("once", []) if j["posicion"] == "D"]
        medios    = [j["nombre"] for j in eq.get("once", []) if j["posicion"] == "M"]
        delanteros = [j["nombre"] for j in eq.get("once", []) if j["posicion"] == "F"]

        lineas.append(f"  {'LOCAL' if lado == 'home' else 'VISITANTE'}: {nombre} ({formacion})")
        lineas.append(f"  DT: {entrenador}")

        if once:
            lineas.append(f"  POR: {', '.join(porteros)}")
            lineas.append(f"  DEF: {', '.join(defensas)}")
            lineas.append(f"  MED: {', '.join(medios)}")
            lineas.append(f"  DEL: {', '.join(delanteros)}")
        else:
            lineas.append("  Once: No disponible aun")

        if eq["bajas"]:
            lineas.append(f"  Bajas: {' | '.join(eq['bajas'])}")
        if eq["dudas"]:
            lineas.append(f"  Dudas: {' | '.join(eq['dudas'])}")

        lineas.append("")

    return "\n".join(lineas)


# ─────────────────────────────────────────────────────────────────────────────
# TEST RAPIDO (py collectors\lineup_collector.py)
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("TEST — lineup_collector.py")
    print("=" * 60)
    print()
    print("Para probar necesitas un fixture_id valido.")
    print("Ejecuta primero: py collectors\\fixtures_collector.py")
    print("Luego reemplaza los IDs abajo y vuelve a correr.")
    print()

    # ──> Reemplaza con IDs reales obtenidos de fixtures_collector
    TEST_FIXTURE_ID = 1234567   # <-- cambiar
    TEST_HOME_ID    = 40        # <-- cambiar (ej: 40 = Liverpool)
    TEST_AWAY_ID    = 33        # <-- cambiar (ej: 33 = Manchester United)

    lineup = get_lineup_completo(TEST_FIXTURE_ID, TEST_HOME_ID, TEST_AWAY_ID)
    print()
    print(formatear_lineup_texto(lineup))
