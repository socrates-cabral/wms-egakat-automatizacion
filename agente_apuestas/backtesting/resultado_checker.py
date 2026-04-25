import sys
sys.stdout.reconfigure(encoding="utf-8")

"""
resultado_checker.py
Verifica el resultado real de cada apuesta pendiente en historico_apuestas.json.

Proceso:
  1. Lee apuestas con resultado_real=None
  2. Para cada una, consulta api-sports /fixtures?id={fixture_id}
  3. Si el partido terminó (FT/AET/PEN): determina si la apuesta ganó
  4. Calcula retorno y actualiza el JSON
  5. Muestra resumen de la sesión

Ejecutar: py backtesting\resultado_checker.py
O desde run_backtesting.py (automático cada noche).
"""

import requests
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import HEADERS_APISPORTS, APISPORTS_BASE
from backtesting.simulador import leer_historico, guardar_historico

# Estados finales MLB StatsAPI
MLB_ESTADOS_FINALES = {"Final", "Game Over", "Completed Early"}

# Estados finales válidos en api-sports
ESTADOS_FINALES = {"FT", "AET", "PEN", "WO"}


# ─────────────────────────────────────────────────────────────────────────────
# CONSULTAR RESULTADO REAL EN API-SPORTS
# ─────────────────────────────────────────────────────────────────────────────

def get_resultado_fixture(fixture_id: int) -> dict | None:
    """
    Consulta el resultado real de un partido en api-sports.

    Returns:
        {
          "estado": str,       # "FT" | "1H" | "NS" | etc
          "home_goles": int,
          "away_goles": int,
          "score": str,        # "2-1"
          "terminado": bool,
        }
        o None si HTTP error.
    """
    url = f"{APISPORTS_BASE}/fixtures"
    response = requests.get(url, headers=HEADERS_APISPORTS,
                            params={"id": fixture_id}, timeout=30)

    if response.status_code != 200:
        print(f"[FALLO] fixture HTTP {response.status_code} id={fixture_id}")
        return None

    data = response.json().get("response", [])
    if not data:
        return None

    f         = data[0]
    estado    = f["fixture"]["status"]["short"]
    home_g    = f["goals"]["home"]
    away_g    = f["goals"]["away"]

    return {
        "estado":     estado,
        "home_goles": home_g if home_g is not None else 0,
        "away_goles": away_g if away_g is not None else 0,
        "score":      f"{home_g}-{away_g}" if home_g is not None else "?-?",
        "terminado":  estado in ESTADOS_FINALES,
    }


# ─────────────────────────────────────────────────────────────────────────────
# CONSULTAR RESULTADO MLB VIA STATSAPI (para hash fixture_ids de The Odds API)
# ─────────────────────────────────────────────────────────────────────────────

def _get_resultado_mlb(home: str, away: str, fecha: str) -> dict | None:
    """
    Busca el resultado de un partido MLB usando MLB-StatsAPI (gratis, sin key).
    Reutiliza la lógica de mlb_features._buscar_partido_mlb().

    Returns:
        {"estado": str, "home_goles": int, "away_goles": int,
         "score": str, "terminado": bool}
        o None si no se encuentra o statsapi no está instalado.
    """
    try:
        import statsapi
        from datetime import date, timedelta

        fecha_base = fecha or date.today().isoformat()

        for delta in (0, 1, -1, 2):
            d = (date.fromisoformat(fecha_base[:10]) + timedelta(days=delta)).strftime("%Y-%m-%d")
            schedule = statsapi.schedule(date=d)
            for g in schedule:
                ah = g.get("away_name", "").lower()
                hh = g.get("home_name", "").lower()
                home_l = home.lower()
                away_l = away.lower()
                # Coincidencia flexible (primeros 6 chars)
                if ((home_l[:6] in hh or hh[:6] in home_l) and
                        (away_l[:6] in ah or ah[:6] in away_l)):
                    estado   = g.get("status", "")
                    terminado = estado in MLB_ESTADOS_FINALES
                    home_g   = g.get("home_score", 0) or 0
                    away_g   = g.get("away_score", 0) or 0
                    return {
                        "estado":     estado,
                        "home_goles": int(home_g),
                        "away_goles": int(away_g),
                        "score":      f"{home_g}-{away_g}",
                        "terminado":  terminado,
                    }
        return None
    except ImportError:
        print("[AVISO] statsapi no instalado — py -m pip install mlb-statsapi")
        return None
    except Exception as e:
        print(f"[AVISO] MLB StatsAPI error: {e}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# DETERMINAR SI LA APUESTA GANÓ
# ─────────────────────────────────────────────────────────────────────────────

def evaluar_apuesta(tipo: str, seleccion: str, home_g: int, away_g: int) -> bool | None:
    """
    Determina si una apuesta ganó dado el marcador final.

    Args:
        tipo:      "1X2" | "BTTS" | "OVER_UNDER" | "DOUBLE_CHANCE"
        seleccion: "HOME" | "DRAW" | "AWAY" | "SI" | "NO" | "Over 2.5" | "Under 2.5" |
                   "1X" | "X2" | "12"
        home_g:   goles equipo local
        away_g:   goles equipo visitante

    Returns:
        True si ganó, False si perdió, None si no se puede determinar.
    """
    total = home_g + away_g

    if tipo == "1X2":
        if seleccion == "HOME":  return home_g > away_g
        if seleccion == "DRAW":  return home_g == away_g
        if seleccion == "AWAY":  return away_g > home_g

    elif tipo == "BTTS":
        btts_ocurrio = home_g > 0 and away_g > 0
        if seleccion in ("SI", "Yes", "Sí"):  return btts_ocurrio
        if seleccion in ("NO", "No"):          return not btts_ocurrio

    elif tipo == "OVER_UNDER":
        # seleccion ej: "Over 2.5" | "Under 2.5" | "Over 3.5"
        partes = seleccion.split()
        if len(partes) == 2:
            direccion = partes[0].lower()
            linea     = float(partes[1])
            if direccion == "over":  return total > linea
            if direccion == "under": return total < linea

    elif tipo == "DOUBLE_CHANCE":
        if seleccion == "1X":  return home_g >= away_g   # home gana o empata
        if seleccion == "X2":  return away_g >= home_g   # away gana o empata
        if seleccion == "12":  return home_g != away_g   # cualquier equipo gana (no empate)

    elif tipo == "HALF_TIME":
        # Se necesita score HT — no disponible aquí; marcar como None para revisión manual
        return None

    return None


# ─────────────────────────────────────────────────────────────────────────────
# FUNCIÓN PRINCIPAL: verificar todas las apuestas pendientes
# ─────────────────────────────────────────────────────────────────────────────

def verificar_pendientes(verbose: bool = True) -> dict:
    """
    Itera las apuestas pendientes, consulta api-sports y actualiza el historico.

    Returns:
        Resumen de la sesión: {"verificadas": int, "ganadas": int, "perdidas": int,
                               "pendientes": int, "no_determinadas": int,
                               "retorno_neto": float}
    """
    apuestas = leer_historico()
    pendientes = [a for a in apuestas if a.get("resultado_real") is None]

    if not pendientes:
        print("[INFO] No hay apuestas pendientes de verificar.")
        return {}

    print(f"[INFO] Verificando {len(pendientes)} apuesta(s) pendiente(s)...")
    print()

    resumen = {
        "verificadas":    0,
        "ganadas":        0,
        "perdidas":       0,
        "pendientes":     0,
        "no_determinadas": 0,
        "retorno_neto":   0.0,
    }

    # Índice para actualización in-place
    idx_por_id = {a["id"]: i for i, a in enumerate(apuestas)}

    for apuesta in pendientes:
        fixture_id = apuesta["fixture_id"]

        # Detectar fixture_ids de The Odds API (hashes string como "48b9e30cc5595d9696cc12db0aef6114")
        es_hash_externo = isinstance(fixture_id, str) and not fixture_id.isdigit()
        if es_hash_externo:
            liga = apuesta.get("liga", "")

            # MLB: intentar resolver via MLB StatsAPI (gratis, sin key)
            if liga == "MLB":
                resultado_mlb = _get_resultado_mlb(
                    apuesta["home"], apuesta["away"],
                    (apuesta.get("fecha_partido") or "")[:10]
                )
                if resultado_mlb and resultado_mlb["terminado"]:
                    home_g = resultado_mlb["home_goles"]
                    away_g = resultado_mlb["away_goles"]
                    ganado = evaluar_apuesta(
                        apuesta["tipo_apuesta"], apuesta["seleccion"],
                        home_g, away_g,
                    )
                    retorno = (round(apuesta["monto_apostado"] * apuesta["cuota"]
                                     - apuesta["monto_apostado"], 2)
                               if ganado is True else
                               (-apuesta["monto_apostado"] if ganado is False else 0.0))
                    resumen["verificadas"] += 1
                    resumen["ganadas"]  += (1 if ganado is True  else 0)
                    resumen["perdidas"] += (1 if ganado is False else 0)
                    resumen["no_determinadas"] += (1 if ganado is None else 0)
                    resumen["retorno_neto"] += retorno

                    idx = idx_por_id[apuesta["id"]]
                    apuestas[idx]["resultado_real"] = resultado_mlb["score"]
                    apuestas[idx]["score_final"]    = resultado_mlb["score"]
                    apuestas[idx]["ganado"]         = ganado
                    apuestas[idx]["retorno"]        = retorno

                    if verbose:
                        icono = "✅" if ganado else ("❌" if ganado is False else "❓")
                        print(f"  {icono} [{apuesta['id'][:8]}] {apuesta['home']} vs {apuesta['away']} "
                              f"| Score: {resultado_mlb['score']} "
                              f"| {apuesta['tipo_apuesta']} {apuesta['seleccion']} "
                              f"@ {apuesta['cuota']} "
                              f"| Retorno: ${retorno:+,.0f} [MLB-StatsAPI]")
                    continue
                elif resultado_mlb and not resultado_mlb["terminado"]:
                    resumen["pendientes"] += 1
                    if verbose:
                        print(f"  ⏳ [{apuesta['id'][:8]}] {apuesta['home']} vs {apuesta['away']} "
                              f"(MLB) → Estado: {resultado_mlb['estado']} (no terminado)")
                    continue

            # Otros deportes con hash o MLB sin datos: pendiente manual
            resumen["pendientes"] += 1
            if verbose:
                print(f"  🔎 [{apuesta['id'][:8]}] {apuesta['home']} vs {apuesta['away']} "
                      f"({liga}) → ID externo — verificar resultado manualmente")
            continue

        resultado  = get_resultado_fixture(fixture_id)

        if resultado is None:
            resumen["pendientes"] += 1
            if verbose:
                print(f"  ⚠️  [{apuesta['id'][:8]}] {apuesta['home']} vs {apuesta['away']} "
                      f"→ Error al consultar API")
            continue

        if not resultado["terminado"]:
            resumen["pendientes"] += 1
            if verbose:
                print(f"  ⏳ [{apuesta['id'][:8]}] {apuesta['home']} vs {apuesta['away']} "
                      f"→ Estado: {resultado['estado']} (no terminado)")
            continue

        # Partido terminado: evaluar apuesta
        home_g = resultado["home_goles"]
        away_g = resultado["away_goles"]
        ganado = evaluar_apuesta(
            apuesta["tipo_apuesta"],
            apuesta["seleccion"],
            home_g, away_g,
        )

        # Calcular retorno
        if ganado is True:
            retorno = round(apuesta["monto_apostado"] * apuesta["cuota"]
                            - apuesta["monto_apostado"], 2)
            resumen["ganadas"] += 1
        elif ganado is False:
            retorno = -apuesta["monto_apostado"]
            resumen["perdidas"] += 1
        else:
            retorno = 0.0   # No determinado — no afecta bankroll
            resumen["no_determinadas"] += 1

        resumen["verificadas"] += 1
        resumen["retorno_neto"] += retorno

        # Actualizar apuesta en la lista
        idx = idx_por_id[apuesta["id"]]
        apuestas[idx]["resultado_real"]  = resultado["score"]
        apuestas[idx]["score_final"]     = resultado["score"]
        apuestas[idx]["ganado"]          = ganado
        apuestas[idx]["retorno"]         = retorno

        if verbose:
            icono = "✅" if ganado else ("❌" if ganado is False else "❓")
            print(f"  {icono} [{apuesta['id'][:8]}] {apuesta['home']} vs {apuesta['away']} "
                  f"| Score: {resultado['score']} "
                  f"| {apuesta['tipo_apuesta']} {apuesta['seleccion']} "
                  f"@ {apuesta['cuota']} "
                  f"| Retorno: ${retorno:+,.0f}")

    guardar_historico(apuestas)

    # Sprint 18: actualizar CLV de las apuestas recién resueltas
    try:
        from backtesting.clv_tracker import actualizar_clv_pendientes
        n_clv = actualizar_clv_pendientes()
        if n_clv > 0:
            print(f"[OK] CLV actualizado para {n_clv} apuesta(s)")
    except ImportError:
        try:
            from clv_tracker import actualizar_clv_pendientes
            n_clv = actualizar_clv_pendientes()
            if n_clv > 0:
                print(f"[OK] CLV actualizado para {n_clv} apuesta(s)")
        except Exception as e:
            print(f"[WARN] CLV update falló: {e}")
    except Exception as e:
        print(f"[WARN] CLV update falló: {e}")

    print()
    print(f"[OK] Sesión completada: "
          f"✅ {resumen['ganadas']} ganadas | "
          f"❌ {resumen['perdidas']} perdidas | "
          f"⏳ {resumen['pendientes']} pendientes | "
          f"❓ {resumen['no_determinadas']} no determinadas")
    print(f"     Retorno neto sesión: ${resumen['retorno_neto']:+,.0f} CLP")

    return resumen


# ─────────────────────────────────────────────────────────────────────────────
# TEST / USO MANUAL
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("RESULTADO CHECKER — verificar apuestas pendientes")
    print("=" * 60)
    print()
    verificar_pendientes(verbose=True)
