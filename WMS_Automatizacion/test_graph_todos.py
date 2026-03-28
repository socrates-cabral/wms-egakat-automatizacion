"""
test_graph_todos.py
Verifica todos los SP paths usados por M1, M3, M6, M7, M8 tras la migración Graph API.
  - Lectura: confirma que cada carpeta SP existe y es accesible
  - Escritura: sube archivo de prueba a Test_GraphAPI/{modulo}/ (NO a producción)
  - NO ejecuta Playwright ni descarga nada del WMS
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from azure_graph import get_token, get_drive_id, listar_archivos_sp, subir_archivo_sp

from datetime import datetime
HOY = datetime.today().strftime("%Y-%m-%d")

# ─── Paths SP a verificar ────────────────────────────────────────────────────

PATHS_LECTURA = {
    "M1 Stock WMS / Quilicura":    "Inventario/Stock WMS Semanal/Quilicura",
    "M1 Stock WMS / Pudahuel":     "Inventario/Stock WMS Semanal/Pudahuel",
    "M3 Posiciones / Quilicura":   "Inventario/Consulta de Posiciones/Quilicura",
    "M3 Posiciones / Pudahuel":    "Inventario/Consulta de Posiciones/Pudahuel",
    "M6 Inventario ABINBEV":       "Clientes EK/ABINBEV/Inventario",
    "M6 Inventario DAIKIN":        "Clientes EK/DAIKIN/Inventario",
    "M6 Inventario DERCO":         "Clientes EK/DERCO/Inventario",
    "M6 Inventario MASCOTAS":      "Clientes EK/MASCOTAS LATINAS/Inventario",
    "M6 Inventario POCHTECA":      "Clientes EK/POCHTECA/Inventario",
    "M7 Preparacion ABINBEV":      "Clientes EK/ABINBEV/Preparación",
    "M7 Preparacion DAIKIN":       "Clientes EK/DAIKIN/Preparación",
    "M7 Preparacion DERCO":        "Clientes EK/DERCO/Preparación",
    "M7 Preparacion MASCOTAS":     "Clientes EK/MASCOTAS LATINAS/Preparación",
    "M7 Preparacion POCHTECA":     "Clientes EK/POCHTECA/Preparación",
    "M8 Recepciones ABINBEV":      "Clientes EK/ABINBEV/Recepciones",
    "M8 Recepciones DAIKIN":       "Clientes EK/DAIKIN/Recepciones",
    "M8 Recepciones DERCO":        "Clientes EK/DERCO/Recepciones",
    "M8 Recepciones MASCOTAS":     "Clientes EK/MASCOTAS LATINAS/Recepciones",
    "M8 Recepciones POCHTECA":     "Clientes EK/POCHTECA/Recepciones",
}

# Escritura sólo en Test_GraphAPI/{modulo}/ — nunca en producción
PATHS_ESCRITURA = {
    "M1":  "Test_GraphAPI/M1_Stock_WMS",
    "M3":  "Test_GraphAPI/M3_Posiciones",
    "M6":  "Test_GraphAPI/M6_Inventario",
    "M7":  "Test_GraphAPI/M7_Preparacion",
    "M8":  "Test_GraphAPI/M8_Recepciones",
}

ARCHIVO_TEST = Path(__file__).parent.parent / "test_graph_upload.txt"

# ─── MAIN ────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("TEST GRAPH API — Todos los módulos migrados")
    print(f"Fecha: {HOY}")
    print("=" * 60)

    # 1. Token + Drive ID
    print("\n[AUTH] Obteniendo token y Drive ID...")
    t0 = time.time()
    try:
        token    = get_token()
        drive_id = get_drive_id(token)
        print(f"  [OK] Token + Drive ID en {time.time()-t0:.1f}s")
    except Exception as e:
        print(f"  [FALLO] {e}")
        sys.exit(1)

    # 2. Verificar lectura de cada carpeta SP
    print("\n[LECTURA] Verificando acceso a carpetas de producción...")
    resultados_lectura = []
    for label, folder_sp in PATHS_LECTURA.items():
        t0 = time.time()
        try:
            archivos = listar_archivos_sp(token, drive_id, folder_sp)
            elapsed  = time.time() - t0
            print(f"  [OK] {label:<35} {len(archivos):>4} archivos  ({elapsed:.1f}s)")
            resultados_lectura.append((label, True))
        except Exception as e:
            print(f"  [FALLO] {label:<35} {e}")
            resultados_lectura.append((label, False))

    # 3. Subir archivo de prueba a Test_GraphAPI/{modulo}/
    print("\n[ESCRITURA] Subiendo archivos de prueba (solo a Test_GraphAPI/)...")
    resultados_escritura = []
    for label, folder_sp in PATHS_ESCRITURA.items():
        t0 = time.time()
        try:
            ok      = subir_archivo_sp(token, drive_id, folder_sp, ARCHIVO_TEST)
            elapsed = time.time() - t0
            print(f"  {'[OK]' if ok else '[WARN]'} {label} → {folder_sp}  ({elapsed:.2f}s)")
            resultados_escritura.append((label, ok))
        except Exception as e:
            print(f"  [FALLO] {label} → {folder_sp}: {e}")
            resultados_escritura.append((label, False))

    # 4. Resumen
    print("\n" + "=" * 60)
    print("RESUMEN")
    print("=" * 60)
    ok_l = sum(1 for _, ok in resultados_lectura  if ok)
    ok_e = sum(1 for _, ok in resultados_escritura if ok)
    print(f"  Lectura:   {ok_l}/{len(resultados_lectura)} carpetas accesibles")
    print(f"  Escritura: {ok_e}/{len(resultados_escritura)} módulos subidos a Test_GraphAPI/")

    fallos_l = [l for l, ok in resultados_lectura  if not ok]
    fallos_e = [l for l, ok in resultados_escritura if not ok]
    if fallos_l:
        print(f"\n  FALLOS lectura:   {', '.join(fallos_l)}")
    if fallos_e:
        print(f"  FALLOS escritura: {', '.join(fallos_e)}")

    if ok_l == len(resultados_lectura) and ok_e == len(resultados_escritura):
        print("\n  RESULTADO: ✅ TODOS LOS PATHS OK — migración Graph API validada")
    else:
        print("\n  RESULTADO: ⚠ Hay paths con problemas — revisar arriba")
    print("=" * 60)

if __name__ == "__main__":
    main()
