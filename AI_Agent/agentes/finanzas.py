"""
finanzas.py — Agente Analista Financiero Multi-Rol con Memoria Evolutiva
Versión 2.0 — Aprende de cada análisis, feedback y datos de mercado en vivo.

ROLES:
  equity     — Renta Variable: fundamentales, valuación, tesis
  bonos      — Renta Fija: duración, spreads, curva tasas
  riesgo     — Riesgos/Crédito: VaR, scoring, IFRS 9
  fpa        — FP&A Corporativo: P&L, varianza, forecast
  banca      — Banca de Inversión: DCF, comps, LBO, M&A
  cartera    — Gestión de Cartera: Sharpe, SAA/TAA, rebalanceo
  tesoreria  — Tesorería: cash flow, FX, coberturas
  consulta   — Pregunta libre (sin archivo)

COMANDOS EVOLUTIVOS:
  actualizar            — Actualiza benchmarks con datos de mercado en vivo
  feedback <id> <1-5>   — Califica un análisis anterior (entrena few-shots)
  memoria               — Muestra estado actual de la memoria

USO CLI:
  py AI_Agent/agentes/finanzas.py equity    "empresa.xlsx" --nivel senior --guardar
  py AI_Agent/agentes/finanzas.py fpa       "presupuesto.xlsx" --pregunta "riesgo liquidez Q2"
  py AI_Agent/agentes/finanzas.py consulta  "¿Qué es el IPSA?" --nivel junior
  py AI_Agent/agentes/finanzas.py actualizar
  py AI_Agent/agentes/finanzas.py feedback  analisis_equity_20260316 5 --nota "perfecto análisis SQM"
  py AI_Agent/agentes/finanzas.py memoria

USO COMO MÓDULO:
  from agentes.finanzas import analizar_equity, consulta_libre, MemoriaFinanciera
"""
import sys
sys.stdout.reconfigure(encoding="utf-8")

import os
import json
import argparse
from pathlib import Path
from datetime import datetime, date
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent.parent.parent
load_dotenv(dotenv_path=BASE_DIR / ".env")

MAX_CHARS_CLAUDE  = 7000
MAX_TOKENS_JUNIOR = 1800
MAX_TOKENS_SENIOR = 3200
MAX_FEW_SHOTS     = 2   # máximo ejemplos por modo en el prompt


# ══════════════════════════════════════════════════════════════════════════════
#  MEMORIA FINANCIERA — aprende, persiste, evoluciona
# ══════════════════════════════════════════════════════════════════════════════

class MemoriaFinanciera:
    """
    Sistema de memoria persistente del agente.
    Almacena benchmarks de mercado, historial de análisis, feedback del usuario
    y ejemplos de referencia (few-shots) para mejorar futuras respuestas.

    Estructura en disco:
        AI_Agent/agentes/finanzas_memoria/
        ├── benchmarks.json      ← indicadores de mercado en vivo (UF, TPM, IPSA...)
        ├── historial.json       ← resumen de cada análisis realizado
        ├── feedback.json        ← calificaciones del usuario
        └── few_shots/           ← mejores análisis por modo (score >= 4)
    """

    DIR = Path(__file__).parent / "finanzas_memoria"
    BENCHMARKS_FILE = DIR / "benchmarks.json"
    HISTORIAL_FILE  = DIR / "historial.json"
    FEEDBACK_FILE   = DIR / "feedback.json"
    FEW_SHOTS_DIR   = DIR / "few_shots"

    def __init__(self):
        self.DIR.mkdir(exist_ok=True)
        self.FEW_SHOTS_DIR.mkdir(exist_ok=True)
        self.benchmarks = self._cargar(self.BENCHMARKS_FILE, self._benchmarks_default())
        self.historial  = self._cargar(self.HISTORIAL_FILE, [])
        self.feedback   = self._cargar(self.FEEDBACK_FILE, {})

    # ── I/O ───────────────────────────────────────────────────────────────────

    def _cargar(self, ruta: Path, default):
        if ruta.exists():
            try:
                return json.loads(ruta.read_text(encoding="utf-8"))
            except Exception:
                pass
        return default

    def _guardar(self, ruta: Path, data):
        ruta.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _guardar_todo(self):
        self._guardar(self.BENCHMARKS_FILE, self.benchmarks)
        self._guardar(self.HISTORIAL_FILE,  self.historial)
        self._guardar(self.FEEDBACK_FILE,   self.feedback)

    # ── Benchmarks por defecto (seeds manuales) ────────────────────────────────

    def _benchmarks_default(self) -> dict:
        return {
            "_actualizados": "nunca",
            "_fuente": "seeds manuales — ejecuta 'actualizar' para datos en vivo",
            "chile": {
                "UF":   37_500.0,
                "TPM":  5.0,
                "USD_CLP": 950.0,
                "EUR_CLP": 1_030.0,
                "IPC_12M": 4.2,
                "IPSA": 6_800.0,
                "BCP_5Y_UF": 2.3,
                "BCP_10Y_UF": 2.7,
                "swap_camara_360": 4.8,
            },
            "global": {
                "fed_funds": 4.5,
                "UST_2Y": 4.3,
                "UST_10Y": 4.6,
                "SP500": 5_600.0,
                "VIX": 18.0,
                "MSCI_World_PE": 18.5,
                "MSCI_EM_PE":    12.0,
                "IG_spread_bps": 110,
                "HY_spread_bps": 340,
            },
            "sectorial_chile_pe": {
                "retail":   16.0,
                "utilities": 14.0,
                "mineria":  11.0,
                "banca":    10.0,
                "inmobiliario": 18.0,
                "agroindustria": 13.0,
            },
            "sectorial_chile_ev_ebitda": {
                "retail":    8.5,
                "utilities": 9.0,
                "mineria":   7.0,
                "banca":     "N/A",
                "inmobiliario": 12.0,
                "agroindustria": 7.5,
            },
        }

    # ── Actualización de mercado en vivo ───────────────────────────────────────

    def actualizar_mercado(self) -> dict:
        """
        Actualiza benchmarks con datos en vivo.
        Fuentes:
          - mindicador.cl   → UF, TPM, USD/CLP, IPC (sin auth, gratuita)
          - yfinance         → IPSA, S&P 500, VIX (opcional)
        Degradación elegante: si falla una fuente, conserva el valor anterior.
        """
        import urllib.request, json as _json

        actualizados = []
        errores      = []

        def _get(url: str) -> dict | None:
            try:
                req  = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                resp = urllib.request.urlopen(req, timeout=8)
                raw  = resp.read()
                # CMF devuelve UTF-8 con BOM — decodificar con utf-8-sig
                texto = raw.decode("utf-8-sig", errors="replace")
                return _json.loads(texto)
            except Exception as e:
                errores.append(f"{url}: {e}")
                return None

        # ── mindicador.cl ────────────────────────────────────────────────────
        INDICADORES = {
            "UF":      "uf",
            "USD_CLP": "dolar",
            "EUR_CLP": "euro",
            "IPC_12M": "ipc",
            "TPM":     "tpm",
        }
        for clave, codigo in INDICADORES.items():
            data = _get(f"https://mindicador.cl/api/{codigo}")
            if data and "serie" in data and data["serie"]:
                valor = data["serie"][0]["valor"]
                self.benchmarks["chile"][clave] = round(float(valor), 4)
                actualizados.append(f"chile.{clave}={valor}")

        # ── yfinance (opcional) ───────────────────────────────────────────────
        try:
            import yfinance as yf

            tickers = {"IPSA": "^IPSA", "SP500": "^GSPC", "VIX": "^VIX"}
            for clave, sym in tickers.items():
                try:
                    t    = yf.Ticker(sym)
                    hist = t.history(period="2d")
                    if not hist.empty:
                        precio = round(float(hist["Close"].iloc[-1]), 2)
                        if clave == "IPSA":
                            self.benchmarks["chile"][clave] = precio
                        else:
                            self.benchmarks["global"][clave] = precio
                        actualizados.append(f"{clave}={precio}")
                except Exception as e:
                    errores.append(f"yf {sym}: {e}")

            # Tasas US Treasuries via yfinance
            # ^IRX = 13-week T-bill, ^TNX = 10Y yield  — yfinance devuelve % directamente
            ust_map = {"UST_2Y": "^IRX", "UST_10Y": "^TNX"}
            for clave, sym in ust_map.items():
                try:
                    hist = yf.Ticker(sym).history(period="2d")
                    if not hist.empty:
                        v = round(float(hist["Close"].iloc[-1]), 3)
                        self.benchmarks["global"][clave] = v
                        actualizados.append(f"{clave}={v}")
                except Exception as e:
                    errores.append(f"yf {sym}: {e}")

        except ImportError:
            errores.append("yfinance no instalado — solo mindicador.cl. Instala: py -m pip install yfinance")

        # ── CMF Bancos API v3 ─────────────────────────────────────────────────
        cmf_key = os.getenv("CMF_API_KEY", "")
        if cmf_key:
            CMF_BASE = "https://api.cmfchile.cl/api-sbifv3/recursos_api"
            cmf_data = self.benchmarks.setdefault("cmf", {})

            # TMC (Tasas Máximas Convencionales) — estructura: {"TMCs": [{Titulo, SubTitulo, Valor, Fecha}]}
            try:
                data = _get(f"{CMF_BASE}/tmc?apikey={cmf_key}&formato=json")
                if data and "TMCs" in data:
                    tmcs = data["TMCs"]
                    # Guardar segmentos clave por nombre corto
                    tmc_map = {}
                    for item in tmcs:
                        titulo    = str(item.get("Titulo")    or "")
                        subtitulo = str(item.get("SubTitulo") or "")
                        valor     = str(item.get("Valor")     or "")
                        fecha     = str(item.get("Fecha")     or "")
                        # Etiqueta corta descriptiva
                        if "menos de 90" in titulo and "Inferiores" in subtitulo:
                            tmc_map["CP_pequeño (<90d, <5kUF)"] = f"{valor}% ({fecha})"
                        elif "menos de 90" in titulo and "Superiores" in subtitulo:
                            tmc_map["CP_grande (<90d, >5kUF)"] = f"{valor}% ({fecha})"
                        elif "90 días" in titulo and "Inferiores" in subtitulo:
                            tmc_map["LP_pequeño (>=90d, <50UF)"] = f"{valor}% ({fecha})"
                        elif "90 días" in titulo and "Superiores" in subtitulo:
                            tmc_map["LP_grande (>=90d, >50UF)"] = f"{valor}% ({fecha})"
                        elif "reajustable" in titulo.lower():
                            tmc_map.setdefault("Reajustable_UF", f"{valor}% ({fecha})")
                    cmf_data["TMC"] = tmc_map
                    cmf_data["TMC_fecha"] = tmcs[0].get("Fecha", "") if tmcs else ""
                    actualizados.append(f"CMF.TMC ({len(tmc_map)} segmentos, {cmf_data['TMC_fecha']})")
            except Exception as e:
                errores.append(f"CMF TMC: {e}")

            # Dólar observado CMF (fuente oficial)
            try:
                data = _get(f"{CMF_BASE}/dolar?apikey={cmf_key}&formato=json")
                if data and "Dolares" in data and data["Dolares"]:
                    v = data["Dolares"][0]["Valor"].replace(",", ".")
                    cmf_data["USD_CLP_oficial"] = float(v)
                    actualizados.append(f"CMF.USD_CLP_oficial={v}")
            except Exception as e:
                errores.append(f"CMF dolar: {e}")

        else:
            errores.append("CMF_API_KEY no encontrada en .env")

        # ── Banco Central de Chile (BCCH) — series estadísticas ─────────────────
        bcch_user = os.getenv("BCCH_USER", "").strip()
        bcch_pass = os.getenv("BCCH_PASS", "").strip()
        if bcch_user and bcch_pass:
            BCCH_BASE = "https://si3.bcentral.cl/SieteRestWS/SieteRestWS.ashx"
            today     = datetime.now().strftime("%Y-%m-%d")
            # Fecha de inicio: 90 días atrás — BCP/BCU se licitán esporádicamente
            from datetime import timedelta
            desde = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
            bcch_data = self.benchmarks.setdefault("bcch", {})

            # Series clave — código: (label, destino_benchmarks, clave_bench)
            # IDs verificados via SearchSeries BCCH
            SERIES = {
                # TPM diaria
                "F022.TPM.TIN.D001.NO.Z.D":   ("TPM",              "chile", "TPM_BCCH"),
                # Tasas mercado secundario BCLP (reemplazaron licitaciones BCP directas)
                "F022.BCLP.TIS.AN02.NO.Z.D":  ("BCLP_2Y_sec",      "chile", "BCLP_2Y_BCCH"),
                "F022.BCLP.TIS.AN05.NO.Z.D":  ("BCLP_5Y_sec",      "chile", "BCLP_5Y_BCCH"),
                "F022.BCLP.TIS.AN10.NO.Z.D":  ("BCLP_10Y_sec",     "chile", "BCLP_10Y_BCCH"),
                # BCU mercado secundario (en UF)
                "F022.BCU.TIN.AN05.UF.Z.D":   ("BCU_5Y_UF",        "chile", "BCU_5Y_UF_BCCH"),
                "F022.BCU.TIN.AN10.UF.Z.D":   ("BCU_10Y_UF",       "chile", "BCU_10Y_UF_BCCH"),
                # IPC variación mensual empalmada
                "G073.IPC.VAR.2023.M":         ("IPC_var_mens",     "chile", "IPC_var_mens_BCCH"),
            }

            import urllib.parse
            for serie_id, (label, dest, clave_bench) in SERIES.items():
                try:
                    params = urllib.parse.urlencode({
                        "user":       bcch_user,
                        "pass":       bcch_pass,
                        "function":   "GetSeries",
                        "timeseries": serie_id,
                        "firstdate":  desde,
                        "lastdate":   today,
                    })
                    data = _get(f"{BCCH_BASE}?{params}")
                    if not data or data.get("Codigo") != 0:
                        errores.append(f"BCCH {label}: {data.get('Descripcion','sin respuesta') if data else 'timeout'}")
                        continue
                    obs = data.get("Series", {}).get("Obs", [])
                    # Buscar último valor con statusCode OK
                    ultimo = next(
                        (o for o in reversed(obs) if o.get("statusCode") == "OK"),
                        None
                    )
                    if ultimo:
                        valor = float(ultimo["value"].replace(",", "."))
                        fecha = ultimo["indexDateString"]
                        bcch_data[clave_bench] = {"valor": valor, "fecha": fecha}
                        # Actualizar también en benchmarks chile si aplica
                        if dest == "chile" and clave_bench in (
                            "TPM_BCCH", "USD_CLP_BCCH", "BCP_5Y_UF_BCCH", "BCP_10Y_UF_BCCH"
                        ):
                            # Actualizar clave base con fuente más oficial
                            map_clave = {
                                "TPM_BCCH":       "TPM",
                                "USD_CLP_BCCH":   "USD_CLP",
                                "BCP_5Y_UF_BCCH": "BCP_5Y_UF",
                                "BCP_10Y_UF_BCCH":"BCP_10Y_UF",
                            }
                            self.benchmarks["chile"][map_clave[clave_bench]] = valor
                        actualizados.append(f"BCCH.{label}={valor} ({fecha})")
                    else:
                        errores.append(f"BCCH {label}: sin obs OK en últimos 365 días (serie sin licitaciones recientes)")
                except Exception as e:
                    errores.append(f"BCCH {label}: {e}")
        else:
            errores.append("BCCH_USER/BCCH_PASS no encontradas en .env")

        self.benchmarks["_actualizados"] = datetime.now().isoformat()
        self.benchmarks["_fuente"]       = "mindicador.cl + yfinance + CMF API v3 + BCCH SI3"
        self._guardar(self.BENCHMARKS_FILE, self.benchmarks)

        return {"actualizados": actualizados, "errores": errores}

    # ── Historial ─────────────────────────────────────────────────────────────

    def registrar_analisis(self, modo: str, objetivo: str, nivel: str,
                           analisis_id: str, resumen_corto: str):
        """Guarda metadata de cada análisis en historial.json."""
        entrada = {
            "id":      analisis_id,
            "modo":    modo,
            "objetivo": objetivo,
            "nivel":   nivel,
            "fecha":   datetime.now().isoformat(),
            "resumen": resumen_corto[:300],
            "score":   None,
        }
        self.historial.append(entrada)
        # Mantener solo los últimos 200
        if len(self.historial) > 200:
            self.historial = self.historial[-200:]
        self._guardar(self.HISTORIAL_FILE, self.historial)

    # ── Feedback ──────────────────────────────────────────────────────────────

    def registrar_feedback(self, analisis_id: str, score: int, nota: str = "") -> bool:
        """Registra feedback (1-5). Si score>=4 guarda como few-shot."""
        # Buscar en historial
        entrada = next((h for h in self.historial if h["id"] == analisis_id), None)
        if not entrada:
            return False

        entrada["score"] = score
        self.feedback[analisis_id] = {
            "score": score,
            "nota":  nota,
            "modo":  entrada["modo"],
            "fecha": datetime.now().isoformat(),
        }
        self._guardar(self.HISTORIAL_FILE, self.historial)
        self._guardar(self.FEEDBACK_FILE, self.feedback)

        # Si es buen análisis, guardarlo como few-shot
        if score >= 4:
            self._promover_few_shot(analisis_id, entrada["modo"], score, nota, entrada["resumen"])

        return True

    def _promover_few_shot(self, analisis_id: str, modo: str, score: int,
                           nota: str, resumen: str):
        """Promueve un análisis bien valorado como ejemplo de referencia."""
        # Buscar el archivo completo en logs/
        archivos = list((BASE_DIR / "logs").glob(f"finanzas_{modo}_*.txt"))
        # Intentar encontrar el que corresponde al ID
        archivo_match = next(
            (f for f in archivos if analisis_id in f.name), None
        )

        contenido = resumen  # fallback: solo el resumen
        if archivo_match:
            try:
                contenido = archivo_match.read_text(encoding="utf-8")[:2000]
            except Exception:
                pass

        few_shot = {
            "id":      analisis_id,
            "score":   score,
            "nota":    nota,
            "resumen": contenido,
            "fecha":   datetime.now().isoformat(),
        }

        ruta_fs = self.FEW_SHOTS_DIR / f"{modo}.json"
        existentes = self._cargar(ruta_fs, [])
        existentes.append(few_shot)
        # Ordenar por score y mantener top 5
        existentes.sort(key=lambda x: x["score"], reverse=True)
        existentes = existentes[:5]
        self._guardar(ruta_fs, existentes)

    def obtener_few_shots(self, modo: str) -> list[dict]:
        ruta_fs = self.FEW_SHOTS_DIR / f"{modo}.json"
        return self._cargar(ruta_fs, [])[:MAX_FEW_SHOTS]

    # ── Contexto para inyectar en prompts ─────────────────────────────────────

    def contexto_prompt(self, modo: str) -> str:
        """
        Genera un bloque de contexto para inyectar en el user prompt.
        Incluye: benchmarks actuales + historial reciente del modo + few-shots.
        """
        lineas = []

        # 1. Benchmarks de mercado
        act = self.benchmarks.get("_actualizados", "nunca")
        ch  = self.benchmarks.get("chile", {})
        gl  = self.benchmarks.get("global", {})
        lineas.append("═══ BENCHMARKS DE MERCADO (contexto actualizado) ═══")
        lineas.append(f"[Última actualización: {act}]")
        lineas.append(
            f"Chile: UF={ch.get('UF','?')} | TPM={ch.get('TPM','?')}% | "
            f"USD/CLP={ch.get('USD_CLP','?')} | IPC12m={ch.get('IPC_12M','?')}% | "
            f"IPSA={ch.get('IPSA','?')}"
        )
        lineas.append(
            f"Chile Tasas: BCP5Y={ch.get('BCP_5Y_UF','?')}% (UF) | "
            f"BCP10Y={ch.get('BCP_10Y_UF','?')}% (UF) | "
            f"Swap360={ch.get('swap_camara_360','?')}%"
        )
        lineas.append(
            f"Global: FedFunds={gl.get('fed_funds','?')}% | "
            f"UST10Y={gl.get('UST_10Y','?')}% | S&P500={gl.get('SP500','?')} | "
            f"VIX={gl.get('VIX','?')} | IG_spread={gl.get('IG_spread_bps','?')}bps"
        )

        # Benchmarks sectoriales si es relevante
        if modo in ("equity", "banca", "fpa"):
            pe   = self.benchmarks.get("sectorial_chile_pe", {})
            eveb = self.benchmarks.get("sectorial_chile_ev_ebitda", {})
            if pe:
                lineas.append("P/E sectorial Chile: " +
                    " | ".join(f"{k}={v}x" for k, v in list(pe.items())[:4]))
            if eveb:
                lineas.append("EV/EBITDA sectorial Chile: " +
                    " | ".join(f"{k}={v}x" for k, v in list(eveb.items())[:4]
                               if v != "N/A"))

        # 1b. Datos CMF si existen
        cmf = self.benchmarks.get("cmf", {})
        if cmf:
            lineas.append("\n═══ DATOS CMF BANCOS (sistema financiero chileno) ═══")
            tmc = cmf.get("TMC")
            if tmc and isinstance(tmc, dict):
                lineas.append("TMC vigente: " +
                    " | ".join(f"{k[:20]}={v}%" for k, v in list(tmc.items())[:4]))
            tasas = cmf.get("tasas_bancarias")
            if tasas and isinstance(tasas, list):
                lineas.append(f"Tasas bancarias CMF: {len(tasas)} segmentos disponibles")

        # 2. Historial reciente del mismo modo
        recientes = [h for h in self.historial[-50:] if h["modo"] == modo][-5:]
        if recientes:
            lineas.append(f"\n═══ ANÁLISIS PREVIOS ({modo}) ═══")
            for h in recientes:
                score_txt = f" [★{h['score']}]" if h.get("score") else ""
                lineas.append(
                    f"• {h['fecha'][:10]} | {h['objetivo']}{score_txt}: "
                    f"{h['resumen'][:120]}…"
                )

        # 3. Few-shots del modo
        few_shots = self.obtener_few_shots(modo)
        if few_shots:
            lineas.append(f"\n═══ REFERENCIA: ANÁLISIS BIEN VALORADOS ({modo}) ═══")
            lineas.append("Usa estos como referencia de calidad y formato:")
            for fs in few_shots:
                lineas.append(f"[★{fs['score']}] {fs.get('nota','')} — {fs['resumen'][:400]}")

        return "\n".join(lineas)

    # ── Vista de estado ───────────────────────────────────────────────────────

    def mostrar_estado(self):
        print(f"\n{'═' * 60}")
        print("  MEMORIA DEL AGENTE FINANCIERO")
        print(f"{'═' * 60}")
        print(f"  Directorio : {self.DIR}")
        print(f"  Benchmarks : última actualización = {self.benchmarks.get('_actualizados','nunca')}")
        print(f"  Historial  : {len(self.historial)} análisis registrados")

        modos_hist = {}
        for h in self.historial:
            modos_hist[h["modo"]] = modos_hist.get(h["modo"], 0) + 1
        if modos_hist:
            print("  Por modo   : " + " | ".join(f"{k}:{v}" for k, v in modos_hist.items()))

        rated = [h for h in self.historial if h.get("score")]
        if rated:
            avg = sum(h["score"] for h in rated) / len(rated)
            print(f"  Feedback   : {len(rated)} calificados | score promedio = {avg:.1f}/5")

        # Few-shots por modo
        fs_count = {}
        for f in self.FEW_SHOTS_DIR.glob("*.json"):
            data = json.loads(f.read_text(encoding="utf-8"))
            fs_count[f.stem] = len(data)
        if fs_count:
            print("  Few-shots  : " + " | ".join(f"{k}:{v}" for k, v in fs_count.items()))

        print(f"\n  Benchmarks Chile:")
        ch = self.benchmarks.get("chile", {})
        for k, v in ch.items():
            print(f"    {k:<20} {v}")

        print(f"\n  Benchmarks Global:")
        gl = self.benchmarks.get("global", {})
        for k, v in gl.items():
            print(f"    {k:<20} {v}")

        # Últimos 5 análisis
        if self.historial:
            print(f"\n  Últimos análisis:")
            for h in self.historial[-5:]:
                score_txt = f" ★{h['score']}" if h.get("score") else ""
                print(f"    [{h['fecha'][:16]}] {h['modo']:10} {h['id']}{score_txt}")
        print()


# Singleton global (cargado una vez por proceso)
_memoria: MemoriaFinanciera | None = None

def _mem() -> MemoriaFinanciera:
    global _memoria
    if _memoria is None:
        _memoria = MemoriaFinanciera()
    return _memoria


# ══════════════════════════════════════════════════════════════════════════════
#  SYSTEM PROMPTS
# ══════════════════════════════════════════════════════════════════════════════

_BASE_CHILE = """
CONTEXTO MERCADO CHILENO:
- Reguladores: CMF, Banco Central de Chile, UAF (antilavado)
- Bolsa: BCS (Bolsa de Comercio de Santiago), BEC, MILA
- Índices: IPSA (30 más líquidas), IGPA, INTER-10, S&PCL
- Monedas/unidades: CLP, UF (indexada IPC diaria), UTM
- Tasas: TPM, TIR BCP (bono en UF), BCU (USD ajustado), swap promedio cámara (SPC)
- AFP (multifondos A-E), compañías de seguros, corredoras, family offices
- Renta fija local: BCP, BCU, depósitos a plazo, letras hipotecarias, bonos corporativos BCS
- Impuestos relevantes: primera categoría 27%, IVA 19%, impuesto único acciones, retención dividendos 35% extranjero
- IFRS (empresas CMF), NCGBancario para bancos, NCG 461 EEFF, FECU histórica
- APV, 57bis, DIPRES deuda pública, FMAM, FES
"""

_BASE_GLOBAL = """
CONTEXTO MERCADO GLOBAL:
- Índices: S&P 500, NASDAQ, DJIA, FTSE 100, DAX, Nikkei 225, MSCI World, MSCI EM, MSCI Latam
- Renta fija: UST (US Treasuries), IG/HY credit, EM bonds, transición LIBOR→SOFR
- Regulación: Basel III/IV (BIS), IFRS vs GAAP, Dodd-Frank, MiFID II, SEC/FINRA
- Derivados: futuros (CME, ICE), opciones, IRS, CDS, TRS, FX forwards/spots
- Ratings: Moody's / S&P / Fitch — IG (≥BBB-/Baa3), HY
- Benchmarks: Fed Funds Rate, SOFR, EURIBOR, OIS
- Private markets: PE, VC, infrastructure — J-curve, TVPI, DPI, RVPI
- ESG: SFDR, TCFD, SASB, GRI — integración en pricing de riesgo y due diligence
"""

SYSTEM_ROLES = {

    "equity": lambda nivel: f"""Eres un Analista de Renta Variable {"Senior con CFA Level III" if nivel == "senior" else "Junior (CFA Level I en proceso)"}.
Especialidad: análisis fundamental (DCF, DDM, EV/EBITDA, P/E relativo, SOTP) y técnico (RSI, MACD, soportes).
{"Profundiza en supuestos de valuación, sensibilidades, WACC por componente y riesgos de tesis de inversión." if nivel == "senior" else "Explica cada métrica antes de aplicarla. Usa ejemplos reales del mercado chileno."}
Estructura respuesta: Resumen Ejecutivo → Fundamentales → Métricas Valuación → Rango de Valor → Riesgos → Tesis.
{_BASE_CHILE}{_BASE_GLOBAL}""",

    "bonos": lambda nivel: f"""Eres un Analista de Renta Fija {"Senior" if nivel == "senior" else "Junior"} especializado en Chile y mercados globales.
Dominas: duración modificada, duración dólar, convexidad, curva Nelson-Siegel, spreads (OAS, Z-spread, G-spread), callable/puttable.
{"Incluye carry, roll-down, breakeven analysis, posicionamiento relativo valor y análisis de escenarios de tasa." if nivel == "senior" else "Explica duración, yield y spread con fórmulas y ejemplos antes de calcular."}
Estructura: Caracterización → Duration/Riesgo tasa → Curva y Spreads → Escenarios estrés → Posicionamiento → Recomendación.
{_BASE_CHILE}{_BASE_GLOBAL}""",

    "riesgo": lambda nivel: f"""Eres un Analista de Riesgos y Crédito {"Senior" if nivel == "senior" else "Junior"} con expertise en banca y corporativos chilenos.
Dominas: VaR (histórico/paramétrico/Monte Carlo), CVaR/ES, stress testing, backtesting. Crédito: PD/LGD/EAD, Altman Z-Score, IFRS 9 ECL (staging). Op risk: Basel AMA/BIA/TSA.
{"Detalla metodologías, hipótesis distribucionales, limitaciones del modelo y comparación vs peers." if nivel == "senior" else "Explica cada métrica de riesgo desde cero, con la fórmula y qué significa en términos de negocio."}
Estructura: Perfil Riesgo → Métricas Clave → Mapa Concentraciones → Alertas EWI → Provisiones → Mitigantes.
{_BASE_CHILE}{_BASE_GLOBAL}""",

    "fpa": lambda nivel: f"""Eres un Analista FP&A {"Senior" if nivel == "senior" else "Junior"} con experiencia en empresas medianas y grandes en Chile.
Dominas: modelamiento 3 estados integrado, presupuesto vs real, rolling forecast, varianza precio/volumen/mix, working capital (DSO/DPO/DIO), ROIC, WACC.
Chile: IVA, PPM, crédito fiscal, franquicia 24bis, EEFF IFRS, SII (F22/F29).
{"Profundiza en drivers de valor, sensibilidades, covenant analysis, waterfall bridge y leading indicators." if nivel == "senior" else "Explica cada ratio con su fórmula, qué mide y cómo impacta al negocio con ejemplos chilenos."}
Estructura: P&L Resumen → Varianza Drivers → Balance/WC → FCF → KPIs → Forecast → Riesgos/Oportunidades.
{_BASE_CHILE}{_BASE_GLOBAL}""",

    "banca": lambda nivel: f"""Eres un Analista de Banca de Inversión {"Senior (VP/Director)" if nivel == "senior" else "Junior (Analyst/Associate)"} con experiencia en Latam y mercados desarrollados.
Dominas: DCF (FCFF/FCFE), trading comps (EV/EBITDA, P/E, EV/Sales NTM), precedent transactions, LBO (IRR/MoM, estructura, covenants, waterfall).
M&A: due diligence financiero, sinergias (revenue+cost), accretion/dilution, fairness opinion. ECM/DCM: pricing IPO, roadshow, covenants.
{"Incluye tabla de sensibilidad, football field completo, consideration mix y análisis de management case vs downside." if nivel == "senior" else "Explica metodologías de valuación paso a paso con ejemplos numéricos chilenos o regionales."}
Estructura: Situación → Metodología Valuación → Rangos de Valor → Estructura Deal → Riesgos → Recomendación.
{_BASE_CHILE}{_BASE_GLOBAL}""",

    "cartera": lambda nivel: f"""Eres un Gestor de Cartera {"Senior (CIO/PM)" if nivel == "senior" else "Junior (analista buy-side)"} con experiencia en AFP, family office o asset manager chileno.
Dominas: Markowitz, CAPM, Fama-French 3/5 factores, Black-Litterman. Métricas: Sharpe, Sortino, Treynor, alfa Jensen, info ratio, máx drawdown, beta sectorial.
Construcción: SAA/TAA, rebalanceo por umbrales, restricciones AFP (Título V DL 3500), límites CMF por tipo fondo.
{"Incluye contribución marginal al riesgo, tracking error vs benchmark, análisis de escenarios macro y tilts factoriales." if nivel == "senior" else "Explica Sharpe, beta y alfa con ejemplos concretos antes de aplicar al portafolio."}
Estructura: Composición → Riesgo/Retorno → Correlaciones → Concentraciones → Rebalanceo → Tesis Macro.
{_BASE_CHILE}{_BASE_GLOBAL}""",

    "tesoreria": lambda nivel: f"""Eres un Analista de Tesorería {"Senior (CFO/Treasurer)" if nivel == "senior" else "Junior"} con experiencia en corporativos chilenos e internacionales.
Dominas: cash forecasting (directo/indirecto), gap analysis, inversiones CP (depósitos, fondos money market), FX (forwards, opciones, cobertura natural).
Financiamiento: créditos sindicados, bonos, leasing, factoring (CMF), supply chain finance. Cash pooling, netting multidivisa.
{"Incluye optimización de estructura de financiamiento, análisis de cost-of-carry, estrategia de cobertura dinámica y KPIs de riesgo financiero." if nivel == "senior" else "Explica instrumentos de cobertura FX y su funcionamiento antes de recomendar."}
Estructura: Posición Caja → Proyección Liquidez → Exposición FX → Coberturas → Financiamiento → KPIs → Recomendaciones.
{_BASE_CHILE}{_BASE_GLOBAL}""",

    "consulta": lambda nivel: f"""Eres un Asesor Financiero Integral {"Senior (CFA, MBA Finance, 15+ años)" if nivel == "senior" else "Junior con formación en finanzas"}.
Respondes preguntas financieras con precisión técnica y ejemplos concretos del mercado chileno y global.
{"Profundiza en matices técnicos, regulatorios y de mercado. Cita estándares (IFRS, Basel, CMF) cuando es relevante. Señala cuando la respuesta difiere entre Chile y mercados desarrollados." if nivel == "senior" else "Explica desde cero, con definiciones claras, fórmulas simples y analogías cotidianas. Prioriza ejemplos chilenos."}
Respondes en español.
{_BASE_CHILE}{_BASE_GLOBAL}""",
}


# ══════════════════════════════════════════════════════════════════════════════
#  HELPERS I/O
# ══════════════════════════════════════════════════════════════════════════════

def _buscar_archivo(nombre: str) -> Path | None:
    p = Path(nombre)
    if p.exists():
        return p
    for f in BASE_DIR.rglob(Path(nombre).name):
        return f
    return None


def _leer_excel(ruta: Path) -> "pd.DataFrame | None":
    import pandas as pd, openpyxl
    wb    = openpyxl.load_workbook(ruta, read_only=True)
    hojas = wb.sheetnames
    wb.close()
    mejor = None
    for h in hojas[:5]:
        try:
            df = pd.read_excel(ruta, sheet_name=h, engine="openpyxl").dropna(how="all")
            if mejor is None or len(df.columns) > len(mejor.columns):
                mejor = df
        except Exception:
            continue
    return mejor


def _leer_csv(ruta: Path) -> "pd.DataFrame | None":
    import pandas as pd
    for enc in ("utf-8", "latin-1", "cp1252"):
        try:
            return pd.read_csv(ruta, encoding=enc, sep=None, engine="python").dropna(how="all")
        except Exception:
            continue
    return None


def _resumen_df(df: "pd.DataFrame", max_filas: int = 12) -> str:
    resumen = f"Dimensiones: {len(df)} filas × {len(df.columns)} columnas\n"
    resumen += f"Columnas: {', '.join(str(c) for c in df.columns)}\n\n"
    num_cols = df.select_dtypes(include="number").columns.tolist()
    if num_cols:
        resumen += "Estadísticas numéricas:\n"
        for col in num_cols[:10]:
            s = df[col].dropna()
            if not s.empty:
                resumen += (
                    f"  {col}: min={s.min():,.2f} | max={s.max():,.2f} "
                    f"| media={s.mean():,.2f} | suma={s.sum():,.2f}\n"
                )
    resumen += f"\nPrimeras {min(max_filas, len(df))} filas:\n"
    resumen += df.head(max_filas).to_string(index=False, max_colwidth=25)
    return resumen


def _claude(system: str, user: str, nivel: str = "senior") -> str:
    from anthropic import Anthropic
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        return "ERROR: ANTHROPIC_API_KEY no está en .env"
    max_tokens = MAX_TOKENS_SENIOR if nivel == "senior" else MAX_TOKENS_JUNIOR
    client = Anthropic(api_key=api_key)
    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user[:MAX_CHARS_CLAUDE]}]
    )
    return resp.content[0].text


def _id_analisis(modo: str) -> str:
    return f"analisis_{modo}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"


def _guardar_resultado(texto: str, modo: str, analisis_id: str) -> Path:
    ruta = BASE_DIR / "logs" / f"{analisis_id}.txt"
    ruta.parent.mkdir(exist_ok=True)
    ruta.write_text(texto, encoding="utf-8")
    return ruta


# ══════════════════════════════════════════════════════════════════════════════
#  PROMPTS DE ANÁLISIS POR MODO
# ══════════════════════════════════════════════════════════════════════════════

PROMPT_ANALISIS = {
    "equity": (
        "Analiza este dataset desde la perspectiva de renta variable.\n\n"
        "Entrega:\n"
        "1) Estado financiero y calidad del negocio\n"
        "2) Métricas de valuación (P/E, EV/EBITDA, P/BV, ROE, ROIC) vs benchmarks sectoriales del contexto\n"
        "3) Tendencias de crecimiento (CAGR ingresos, EBITDA, FCF)\n"
        "4) Solidez del balance (deuda/EBITDA, cobertura intereses, liquidez)\n"
        "5) Comparación implícita vs sector chileno y global\n"
        "6) Tesis de inversión (Bull/Base/Bear) y catalizadores"
    ),
    "bonos": (
        "Analiza este portafolio/instrumento de renta fija.\n\n"
        "Entrega:\n"
        "1) Caracterización (duration, YTM, calidad crediticia promedio)\n"
        "2) Riesgo de tasa (DV01, duración modificada, convexidad)\n"
        "3) Análisis de spreads vs benchmarks del contexto (BCP, UST)\n"
        "4) Perfil de vencimientos y riesgo de reinversión\n"
        "5) Escenarios de estrés (+100bps / -100bps)\n"
        "6) Posicionamiento recomendado en curva"
    ),
    "riesgo": (
        "Analiza este dataset desde gestión de riesgos.\n\n"
        "Entrega:\n"
        "1) Identificación de riesgos principales (crédito, mercado, liquidez, op)\n"
        "2) Métricas de concentración (HHI, top-10, sector/geografía)\n"
        "3) Calidad de cartera (morosidad, provisiones, cobertura, staging IFRS 9)\n"
        "4) Pérdidas esperadas (EL = PD × LGD × EAD)\n"
        "5) Early Warning Indicators (EWI)\n"
        "6) Mitigantes y recomendaciones de capital"
    ),
    "fpa": (
        "Analiza estos datos financieros corporativos desde FP&A.\n\n"
        "Entrega:\n"
        "1) P&L: ingresos, EBITDA, EBIT, utilidad neta y márgenes\n"
        "2) Varianza real vs presupuesto por driver (precio/volumen/mix/FX)\n"
        "3) Capital de trabajo (DSO, DPO, DIO) y ciclo de caja\n"
        "4) Flujo de caja libre (FCF) y capacidad de pago\n"
        "5) KPIs financieros y operativos más relevantes\n"
        "6) Forecast y riesgos para el período siguiente"
    ),
    "banca": (
        "Analiza este target/empresa desde banca de inversión.\n\n"
        "Entrega:\n"
        "1) Perfil financiero (ingresos, EBITDA, crecimiento, márgenes)\n"
        "2) Valuación por múltiplos vs benchmarks del contexto\n"
        "3) Supuestos DCF implícitos (g, WACC, terminal value)\n"
        "4) Estructura de capital y capacidad de apalancamiento\n"
        "5) Rango de precio (football field simplificado)\n"
        "6) Due diligence clave y riesgos del deal"
    ),
    "cartera": (
        "Analiza este portafolio de inversión.\n\n"
        "Entrega:\n"
        "1) Composición actual (asset class, sectores, geografías, monedas)\n"
        "2) Métricas riesgo/retorno (Sharpe, Sortino, máx drawdown, volatilidad)\n"
        "3) Correlaciones y diversificación efectiva\n"
        "4) Concentraciones y riesgos de cola\n"
        "5) Comparación vs benchmark del contexto (IPSA, MSCI World)\n"
        "6) Propuesta de rebalanceo y tesis macro"
    ),
    "tesoreria": (
        "Analiza esta posición de tesorería / flujo de caja.\n\n"
        "Entrega:\n"
        "1) Posición de liquidez actual y proyectada\n"
        "2) Gap analysis por período (brechas de financiamiento)\n"
        "3) Exposición FX y estrategia de cobertura\n"
        "4) Costo de financiamiento vs mercado (usa tasas del contexto)\n"
        "5) KPIs tesorería (días de caja, ratio liquidez, cobertura líneas)\n"
        "6) Optimización de cash y gestión de riesgo financiero"
    ),
}


# ══════════════════════════════════════════════════════════════════════════════
#  MOTOR DE ANÁLISIS
# ══════════════════════════════════════════════════════════════════════════════

def _analizar_archivo(modo: str, ruta_str: str, nivel: str = "senior",
                      pregunta_extra: str = "", guardar: bool = False) -> dict:
    archivo = _buscar_archivo(ruta_str)
    if not archivo:
        return {"error": f"Archivo no encontrado: {ruta_str}"}

    ext = archivo.suffix.lower()
    if ext in (".xlsx", ".xls"):
        df = _leer_excel(archivo)
    elif ext == ".csv":
        df = _leer_csv(archivo)
    else:
        return {"error": f"Formato no soportado: {ext}. Usa .xlsx, .xls o .csv"}

    if df is None or df.empty:
        return {"error": "No se pudo leer el archivo o está vacío"}

    resumen_datos  = f"Archivo: {archivo.name}\n{_resumen_df(df)}"
    mem            = _mem()
    contexto       = mem.contexto_prompt(modo)

    prompt_base    = PROMPT_ANALISIS.get(modo, "Analiza este dataset financiero.")
    if pregunta_extra:
        prompt_base += f"\n\nPREGUNTA ADICIONAL: {pregunta_extra}"

    user_content = f"{prompt_base}\n\n{contexto}\n\nDATA FINANCIERA:\n{resumen_datos}"
    system       = SYSTEM_ROLES[modo](nivel)
    analisis     = _claude(system, user_content, nivel=nivel)

    analisis_id  = _id_analisis(modo)

    # Registrar en memoria
    resumen_corto = analisis[:250] if analisis else ""
    mem.registrar_analisis(modo, archivo.name, nivel, analisis_id, resumen_corto)

    resultado = {
        "modo":          modo,
        "nivel":         nivel,
        "archivo":       str(archivo),
        "analisis_id":   analisis_id,
        "resumen_datos": resumen_datos,
        "analisis":      analisis,
    }

    if guardar:
        contenido = (
            f"ANÁLISIS FINANCIERO — {modo.upper()}\n"
            f"Nivel: {nivel} | ID: {analisis_id} | Fecha: {datetime.now().isoformat()}\n"
            f"{'=' * 60}\n\n"
            f"DATOS:\n{resumen_datos}\n\n"
            f"ANÁLISIS:\n{analisis}"
        )
        ruta_log = _guardar_resultado(contenido, modo, analisis_id)
        resultado["guardado_en"] = str(ruta_log)
        print(f"\n  [guardado → {ruta_log.name}]")

    return resultado


# ══════════════════════════════════════════════════════════════════════════════
#  API PÚBLICA (uso como módulo)
# ══════════════════════════════════════════════════════════════════════════════

def analizar_afp(ruta: str, nivel: str = "senior", guardar: bool = False) -> dict:
    """
    Analiza archivo Excel de movimientos AFP (formato ProVida/cualquier AFP chilena).
    Los datos se procesan SOLO EN MEMORIA — nunca se persisten datos personales.
    Estructura esperada: columnas FECHA, GIROS, APORTES, DESCRIPCION (fila 3 = headers).
    """
    import pandas as pd

    archivo = _buscar_archivo(ruta)
    if not archivo:
        return {"error": f"Archivo no encontrado: {ruta}"}

    try:
        df = pd.read_excel(archivo, sheet_name=0, header=2, engine="openpyxl")
        df.columns = ["FECHA", "GIROS", "APORTES", "_", "DESCRIPCION", "RUT_PAGADOR", "FONDO"] + \
                     [f"_extra{i}" for i in range(max(0, len(df.columns) - 7))]
    except Exception as e:
        return {"error": f"No se pudo leer el archivo AFP: {e}"}

    # Limpiar
    df = df.dropna(subset=["FECHA"])
    for col in ["GIROS", "APORTES"]:
        df[col] = pd.to_numeric(
            df[col].astype(str).str.replace(".", "", regex=False).str.replace(",", ".", regex=False),
            errors="coerce"
        ).fillna(0)
    df["FECHA"] = pd.to_datetime(df["FECHA"], dayfirst=True, errors="coerce")
    df = df.dropna(subset=["FECHA"]).sort_values("FECHA")

    # KPIs
    total_aportes    = df["APORTES"].sum()
    total_comisiones = df[df["DESCRIPCION"].str.contains("Comisi", na=False)]["GIROS"].sum()
    total_cotizado   = df[df["DESCRIPCION"].str.contains("Aporte|Cotiz", na=False)]["APORTES"].sum()

    inicio = df["FECHA"].min()
    fin    = df["FECHA"].max()
    meses  = max(1, (fin.year - inicio.year) * 12 + (fin.month - inicio.month))

    # Flujo reciente (últimos 6 meses)
    corte = fin - pd.DateOffset(months=6)
    df_rec = df[df["FECHA"] >= corte]
    ap_rec = df_rec[df_rec["DESCRIPCION"].str.contains("Aporte|Cotiz", na=False)]["APORTES"]
    co_rec = df_rec[df_rec["DESCRIPCION"].str.contains("Comisi", na=False)]["GIROS"]
    aporte_prom   = ap_rec.mean() if not ap_rec.empty else 0
    comision_prom = co_rec.mean() if not co_rec.empty else 0
    neto_mensual  = aporte_prom - comision_prom

    # Empleadores
    empleadores = df[df["RUT_PAGADOR"].notna() & (df["RUT_PAGADOR"].astype(str) != "nan")
                     ]["RUT_PAGADOR"].value_counts().head(3).to_dict()

    # Benchmarks comisiones AFP Chile (datos públicos CMF, vigentes 2026)
    comisiones_afp = {
        "ProVida":    1.45, "Habitat":   1.27, "Capital":  1.44,
        "Cuprum":     1.44, "PlanVital": 1.16, "Modelo":   0.58,
    }

    resumen = (
        f"AFP — Cuenta Obligatoria\n"
        f"Período: {inicio.strftime('%b-%Y')} → {fin.strftime('%b-%Y')} ({meses} meses)\n"
        f"Total cotizado: ${total_cotizado:,.0f}\n"
        f"Total comisiones pagadas: ${total_comisiones:,.0f}\n"
        f"Aporte promedio reciente: ${aporte_prom:,.0f}/mes\n"
        f"Comisión promedio: ${comision_prom:,.0f}/mes ({comision_prom/aporte_prom*100:.1f}% del aporte)\n"
        f"Neto mensual al fondo: ${neto_mensual:,.0f}\n"
        f"Empleadores históricos: {empleadores}\n"
        f"\nBenchmark comisiones AFP Chile 2026 (% remuneración):\n"
        + "\n".join(f"  {k}: {v}%" for k, v in comisiones_afp.items())
    )

    mem    = _mem()
    ctx    = mem.contexto_prompt("riesgo")  # riesgo es el más cercano conceptualmente

    system = (
        f"Eres un Analista Previsional {'Senior' if nivel == 'senior' else 'Junior'} "
        f"especializado en el sistema AFP chileno (DL 3500, SP CMF, multifondos A-E). "
        f"Tu análisis es objetivo, considera el impacto a largo plazo, compara con benchmarks "
        f"del mercado y sugiere optimizaciones concretas (cambio de fondo, cambio de AFP, APV). "
        f"Respondes en español. Datos procesados solo en memoria — nunca persistidos.\n"
        f"CONTEXTO MERCADO:\n{ctx}"
    )

    prompt = (
        f"Analiza estos datos de cuenta AFP obligatoria (datos procesados en memoria, confidenciales):\n\n"
        f"{resumen}\n\n"
        f"Entrega:\n"
        f"1) Estado actual de la cuenta (nivel de acumulación vs promedio por años de cotización)\n"
        f"2) Eficiencia de comisiones (vs benchmark tabla AFP Chile)\n"
        f"3) Proyección a 30 años en 3 escenarios (pesimista 4%, base 6%, optimista 8%)\n"
        f"4) Análisis del fondo actual (si se puede inferir) — ¿es adecuado para la edad?\n"
        f"5) Recomendaciones concretas: cambio AFP, APV, cambio de fondo\n"
        f"6) Impacto de cotización en UF (protección inflación)"
    )

    analisis   = _claude(system, prompt, nivel=nivel)
    analisis_id = _id_analisis("afp")
    mem.registrar_analisis("afp", archivo.name, nivel, analisis_id, analisis[:250])

    resultado = {
        "modo": "afp", "nivel": nivel,
        "analisis_id": analisis_id,
        "kpis": {
            "total_cotizado": total_cotizado,
            "total_comisiones": total_comisiones,
            "aporte_prom_reciente": aporte_prom,
            "comision_prom": comision_prom,
            "neto_mensual_al_fondo": neto_mensual,
            "meses_historial": meses,
        },
        "resumen_datos": resumen,
        "analisis": analisis,
        "privacidad": "Datos procesados en memoria — no persistidos en disco",
    }

    if guardar:
        contenido = (
            f"ANÁLISIS AFP — CUENTA OBLIGATORIA\n"
            f"Nivel: {nivel} | ID: {analisis_id} | {datetime.now().isoformat()}\n"
            f"{'='*60}\n\n{resumen}\n\nANÁLISIS:\n{analisis}"
        )
        ruta_log = _guardar_resultado(contenido, "afp", analisis_id)
        resultado["guardado_en"] = str(ruta_log)

    return resultado


def analizar_equity   (ruta: str, nivel: str = "senior", pregunta: str = "", guardar: bool = False) -> dict:
    return _analizar_archivo("equity",    ruta, nivel, pregunta, guardar)

def analizar_bonos    (ruta: str, nivel: str = "senior", pregunta: str = "", guardar: bool = False) -> dict:
    return _analizar_archivo("bonos",     ruta, nivel, pregunta, guardar)

def analizar_riesgo   (ruta: str, nivel: str = "senior", pregunta: str = "", guardar: bool = False) -> dict:
    return _analizar_archivo("riesgo",    ruta, nivel, pregunta, guardar)

def analizar_fpa      (ruta: str, nivel: str = "senior", pregunta: str = "", guardar: bool = False) -> dict:
    return _analizar_archivo("fpa",       ruta, nivel, pregunta, guardar)

def analizar_banca    (ruta: str, nivel: str = "senior", pregunta: str = "", guardar: bool = False) -> dict:
    return _analizar_archivo("banca",     ruta, nivel, pregunta, guardar)

def analizar_cartera  (ruta: str, nivel: str = "senior", pregunta: str = "", guardar: bool = False) -> dict:
    return _analizar_archivo("cartera",   ruta, nivel, pregunta, guardar)

def analizar_tesoreria(ruta: str, nivel: str = "senior", pregunta: str = "", guardar: bool = False) -> dict:
    return _analizar_archivo("tesoreria", ruta, nivel, pregunta, guardar)

def consulta_libre    (pregunta: str, nivel: str = "senior", guardar: bool = False) -> dict:
    mem      = _mem()
    contexto = mem.contexto_prompt("consulta")
    system   = SYSTEM_ROLES["consulta"](nivel)
    analisis = _claude(system, f"{pregunta}\n\n{contexto}", nivel=nivel)
    analisis_id = _id_analisis("consulta")
    mem.registrar_analisis("consulta", pregunta[:60], nivel, analisis_id, analisis[:250])
    resultado = {"modo": "consulta", "nivel": nivel, "pregunta": pregunta,
                 "analisis_id": analisis_id, "analisis": analisis}
    if guardar:
        contenido = (
            f"CONSULTA FINANCIERA\nNivel: {nivel} | ID: {analisis_id}\n"
            f"Pregunta: {pregunta}\n{'=' * 60}\n\n{analisis}"
        )
        ruta_log = _guardar_resultado(contenido, "consulta", analisis_id)
        resultado["guardado_en"] = str(ruta_log)
    return resultado


# ══════════════════════════════════════════════════════════════════════════════
#  CLI
# ══════════════════════════════════════════════════════════════════════════════

MODOS_ANALISIS = ["equity", "bonos", "riesgo", "fpa", "banca", "cartera", "tesoreria", "afp"]
MODOS_ESPECIALES = ["consulta", "actualizar", "feedback", "memoria"]
TODOS_LOS_MODOS  = MODOS_ANALISIS + MODOS_ESPECIALES

DESCRIPCION = {
    "equity":    "Análisis de Renta Variable (acciones, valuación, fundamentales)",
    "bonos":     "Análisis de Renta Fija (duración, spreads, curva de tasas)",
    "riesgo":    "Análisis de Riesgos y Crédito (VaR, scoring, IFRS 9)",
    "fpa":       "FP&A Corporativo (P&L, presupuesto, varianza, forecast)",
    "banca":     "Banca de Inversión (DCF, comps, LBO, M&A)",
    "cartera":   "Gestión de Cartera (Sharpe, diversificación, SAA/TAA)",
    "tesoreria": "Tesorería Corporativa (cash flow, liquidez, FX)",
    "afp":       "AFP y Previsión (cuenta obligatoria, proyección, optimización) — datos en memoria",
    "consulta":  "Pregunta financiera libre (sin archivo)",
    "actualizar":"Actualiza benchmarks con datos de mercado en vivo",
    "feedback":  "Califica un análisis anterior → entrena few-shots",
    "memoria":   "Muestra estado actual de la memoria del agente",
}


def main():
    parser = argparse.ArgumentParser(
        description="Agente Analista Financiero Multi-Rol v2.0 — Memoria Evolutiva",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="\n".join(f"  {k:<12} {v}" for k, v in DESCRIPCION.items())
    )
    parser.add_argument("modo",     choices=TODOS_LOS_MODOS, help="Rol o comando")
    parser.add_argument("objetivo", nargs="?", default="",
                        help="Archivo (.xlsx/.csv) o pregunta (consulta) o ID análisis (feedback)")
    parser.add_argument("--nivel",    choices=["junior", "senior"], default="senior")
    parser.add_argument("--pregunta", default="", help="Pregunta adicional sobre el archivo")
    parser.add_argument("--nota",     default="", help="Nota para el feedback")
    parser.add_argument("--score",    type=int, choices=range(1, 6),
                        help="Score 1-5 para feedback (alternativa: segundo argumento posicional)")
    parser.add_argument("--guardar",  action="store_true", help="Guardar análisis en logs/")
    parser.add_argument("--json",     action="store_true", help="Output en JSON")

    args = parser.parse_args()

    # ── memoria ───────────────────────────────────────────────────────────────
    if args.modo == "memoria":
        _mem().mostrar_estado()
        return

    # ── actualizar ────────────────────────────────────────────────────────────
    if args.modo == "actualizar":
        print("\nActualizando benchmarks de mercado…")
        res = _mem().actualizar_mercado()
        if res["actualizados"]:
            print(f"✅ Actualizados ({len(res['actualizados'])}): {', '.join(res['actualizados'])}")
        if res["errores"]:
            print(f"⚠ Errores: {'; '.join(res['errores'])}")
        print("\nBenchmarks actuales:")
        _mem().mostrar_estado()
        return

    # ── feedback ──────────────────────────────────────────────────────────────
    if args.modo == "feedback":
        analisis_id = args.objetivo
        # score puede venir como --score o como segundo arg posicional (objetivo)
        score = args.score
        if not score:
            # Intentar parsear objetivo como "analisis_equity_xxx 4"
            partes = analisis_id.split()
            if len(partes) >= 2:
                try:
                    score = int(partes[-1])
                    analisis_id = " ".join(partes[:-1])
                except ValueError:
                    pass
        if not analisis_id or not score:
            print("Uso: py finanzas.py feedback <analisis_id> --score 1-5 [--nota 'comentario']")
            print("  o: py finanzas.py feedback \"analisis_equity_20260316 5\"")
            sys.exit(1)

        ok = _mem().registrar_feedback(analisis_id, score, args.nota)
        if ok:
            promoted = "→ promovido como few-shot de referencia" if score >= 4 else ""
            print(f"✅ Feedback registrado: {analisis_id} | ★{score}/5 {promoted}")
        else:
            print(f"[ERROR] ID no encontrado en historial: {analisis_id}")
            print("Consulta IDs disponibles con: py finanzas.py memoria")
        return

    # ── análisis ──────────────────────────────────────────────────────────────
    if not args.objetivo:
        print(f"[ERROR] El modo '{args.modo}' requiere un archivo o pregunta.")
        sys.exit(1)

    if args.modo == "consulta":
        resultado = consulta_libre(args.objetivo, args.nivel, args.guardar)
    elif args.modo == "afp":
        resultado = analizar_afp(args.objetivo, args.nivel, args.guardar)
    else:
        resultado = _analizar_archivo(args.modo, args.objetivo, args.nivel,
                                      args.pregunta, args.guardar)

    if "error" in resultado:
        print(f"[ERROR] {resultado['error']}")
        sys.exit(1)

    # Output JSON
    if args.json:
        salida = {k: v for k, v in resultado.items() if k != "resumen_datos"}
        print(json.dumps(salida, ensure_ascii=False, indent=2))
        return

    # Output legible
    modo_label = DESCRIPCION.get(args.modo, args.modo)
    print(f"\n{'═' * 70}")
    print(f"  {modo_label.upper()}")
    print(f"  Nivel: {args.nivel.upper()} | {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"  ID: {resultado.get('analisis_id','')}")
    print(f"{'═' * 70}\n")

    if args.modo != "consulta":
        print("─── DATOS ──────────────────────────────────────────────────────────────")
        print(resultado.get("resumen_datos", ""))
        print()

    print("─── ANÁLISIS ───────────────────────────────────────────────────────────")
    print(resultado.get("analisis", ""))

    print(f"\n  → Para calificar: py AI_Agent/agentes/finanzas.py feedback "
          f"{resultado.get('analisis_id','')} --score 5")


if __name__ == "__main__":
    main()
