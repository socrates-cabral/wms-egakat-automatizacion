import sys
if sys.stdout:
    sys.stdout.reconfigure(encoding="utf-8")

"""
setup_nps_tokens.py
1. Descarga participantes del survey NPS (418429) desde LimeSurvey
2. Guarda tokens_nps.csv listo para nps_descarga.py
3. Elimina a Fabiola Segovia (Syntheon) — es proveedor, no cliente

Uso:
  py NPS_Encuesta\\setup_nps_tokens.py
"""

import csv
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

DIR = Path(__file__).parent
sys.path.insert(0, str(DIR))
from nps_descarga import LimeSurveyAPI, SURVEY_ID_NPS, LIMESURVEY_URL, LIMESURVEY_USER, LIMESURVEY_PASSWORD

TOKENS_NPS_PATH = DIR / "tokens_nps.csv"
EXCLUIR_EMAILS  = {"fabiola.segovia@syntheon.cl", "fsegovia@syntheon.cl"}  # Syntheon = proveedor IMO
EXCLUIR_NOMBRES = {"fabiola segovia"}


def _es_excluido(p: dict) -> bool:
    email  = (p.get("email") or "").strip().lower()
    nombre = f"{p.get('firstname', '')} {p.get('lastname', '')}".strip().lower()
    return email in EXCLUIR_EMAILS or nombre in EXCLUIR_NOMBRES


def main():
    print("=" * 60)
    print("SETUP NPS TOKENS — survey", SURVEY_ID_NPS)
    print("=" * 60)

    if not LIMESURVEY_USER or not LIMESURVEY_PASSWORD:
        print("[FALLO] LIMESURVEY_USER / LIMESURVEY_PASSWORD no están en .env")
        sys.exit(1)

    api = LimeSurveyAPI(LIMESURVEY_URL)
    try:
        api.open(LIMESURVEY_USER, LIMESURVEY_PASSWORD)

        # ── 1. Listar participantes ─────────────────────────────────────────────
        print(f"\nPaso 1 — Listando participantes survey {SURVEY_ID_NPS}...")
        participantes = api.list_participants(SURVEY_ID_NPS, limit=2000)
        print(f"  Encontrados: {len(participantes)}")

        if not participantes:
            print("[AVISO] No hay participantes aún en el survey NPS.")
            print("        Agrégalos en LimeSurvey y vuelve a correr este script.")
            return

        # ── 2. Identificar y eliminar excluidos ─────────────────────────────────
        a_eliminar = [p for p in participantes if _es_excluido(p)]
        a_conservar = [p for p in participantes if not _es_excluido(p)]

        if a_eliminar:
            print(f"\nPaso 2 — Eliminando {len(a_eliminar)} participante(s) excluido(s):")
            for p in a_eliminar:
                print(f"  - {p.get('firstname')} {p.get('lastname')} <{p.get('email')}> (Syntheon = proveedor)")
            tids = [str(p["tid"]) for p in a_eliminar]
            resultado = api.delete_participants(SURVEY_ID_NPS, tids)
            print(f"  [OK] Eliminados: {resultado}")
        else:
            print("\nPaso 2 — Ningún participante excluido encontrado (Fabiola Segovia ya no está).")

        # ── 3. Guardar tokens_nps.csv ────────────────────────────────────────────
        print(f"\nPaso 3 — Guardando {len(a_conservar)} tokens en {TOKENS_NPS_PATH.name}...")
        with open(TOKENS_NPS_PATH, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["token", "email", "firstname", "lastname"])
            writer.writeheader()
            for p in a_conservar:
                writer.writerow({
                    "token":     p.get("token", ""),
                    "email":     (p.get("email") or "").strip().lower(),
                    "firstname": p.get("firstname", ""),
                    "lastname":  p.get("lastname", ""),
                })
        print(f"  [OK] Guardado: {TOKENS_NPS_PATH}")

        # Mostrar muestra
        print(f"\n  Muestra (primeros 5):")
        for p in a_conservar[:5]:
            print(f"    {p.get('email'):<40} token: {p.get('token', '')[:12]}...")

        print(f"\n[OK] tokens_nps.csv listo — {len(a_conservar)} participantes")
        print("     Próximo paso: py NPS_Encuesta\\nps_descarga.py para procesar respuestas")

    finally:
        api.close()


if __name__ == "__main__":
    main()
