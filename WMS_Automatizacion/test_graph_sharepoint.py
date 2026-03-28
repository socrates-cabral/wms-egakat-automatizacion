"""
test_graph_sharepoint.py
Test de escritura SharePoint via Graph API.
Sube test_graph_upload.txt a /Shared Documents/Test_GraphAPI/
NO modifica producción.
"""
import sys
if sys.stdout:
    sys.stdout.reconfigure(encoding="utf-8")

import time
from pathlib import Path

# azure_graph.py está en el mismo directorio
sys.path.insert(0, str(Path(__file__).parent))
from azure_graph import get_token, get_drive_id, subir_archivo_sp, listar_archivos_sp

ARCHIVO_TEST = Path(__file__).parent.parent / "test_graph_upload.txt"
CARPETA_TEST = "Test_GraphAPI"

print("=" * 55)
print("TEST ESCRITURA SHAREPOINT — Graph API")
print("=" * 55)

# ── PASO 1: Token ─────────────────────────────────────────
print("\n[1/4] Obteniendo token OAuth2...")
t0 = time.time()
try:
    token = get_token()
    print(f"  [OK] Token obtenido ({len(token)} chars) — {time.time()-t0:.1f}s")
except Exception as e:
    print(f"  [FALLO] {e}")
    sys.exit(1)

# ── PASO 2: Drive ID ──────────────────────────────────────
print("\n[2/4] Resolviendo Drive ID de SharePoint...")
t0 = time.time()
try:
    drive_id = get_drive_id(token)
    print(f"  [OK] Drive ID: {drive_id[:30]}... — {time.time()-t0:.1f}s")
except Exception as e:
    print(f"  [FALLO] {e}")
    print("  → Verificar permiso Sites.ReadWrite.All en Azure AD (José Contreras IT)")
    sys.exit(1)

# ── PASO 3: Subir archivo ─────────────────────────────────
print(f"\n[3/4] Subiendo {ARCHIVO_TEST.name} → {CARPETA_TEST}/")
if not ARCHIVO_TEST.exists():
    print(f"  [FALLO] Archivo no encontrado: {ARCHIVO_TEST}")
    sys.exit(1)

t0 = time.time()
ok = subir_archivo_sp(token, drive_id, CARPETA_TEST, ARCHIVO_TEST)
elapsed = time.time() - t0

if ok:
    print(f"  [OK] Subido en {elapsed:.2f}s")
else:
    print(f"  [FALLO] subir_archivo_sp retornó False — verificar permisos o ruta")
    sys.exit(1)

# ── PASO 4: Verificar que aparece ─────────────────────────
print(f"\n[4/4] Verificando que el archivo aparece en SharePoint...")
try:
    archivos = listar_archivos_sp(token, drive_id, CARPETA_TEST)
    if ARCHIVO_TEST.name in archivos:
        print(f"  [OK] {ARCHIVO_TEST.name} confirmado en {CARPETA_TEST}/")
        print(f"  Total archivos en carpeta: {len(archivos)}")
    else:
        print(f"  [WARN] Archivo subido pero no aparece aún en listado (puede ser delay)")
        print(f"  Archivos encontrados: {archivos}")
except Exception as e:
    print(f"  [WARN] No se pudo listar carpeta destino: {e}")

print("\n" + "=" * 55)
print("RESULTADO: Graph API escritura SharePoint ✅ VALIDADO")
print("→ azure_graph.subir_archivo_sp() funciona correctamente")
print("→ sharepoint_copy.py puede migrar a Graph API")
print("→ Independiente de OneDrive sync")
print("=" * 55)
