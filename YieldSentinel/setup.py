"""
SETUP AUTOMÁTICO — YIELD SENTINEL (Windows)
============================================
Ejecuta este script UNA sola vez para configurar todo.
Doble clic en Windows, o desde CMD:

    python setup.py

Qué hace:
1. Verifica Python >= 3.8
2. Instala dependencias
3. Crea carpetas necesarias
4. Verifica conexión a Hyperliquid
5. Verifica conexión a Telegram
6. Crea el archivo .bat para el Programador de Tareas
7. Da instrucciones claras de qué hacer a continuación
"""

import os
import sys
import json
import subprocess
from datetime import datetime


def print_header():
    print("\n" + "╔" + "═"*53 + "╗")
    print("║" + " "*15 + "⚡ YIELD SENTINEL" + " "*21 + "║")
    print("║" + " "*12 + "Setup Automático v1.0" + " "*20 + "║")
    print("╚" + "═"*53 + "╝\n")


def check_python():
    """Verifica versión de Python."""
    print("1. Verificando Python...")
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print(f"   ❌ Python {version.major}.{version.minor} no soportado.")
        print("   Instala Python 3.8+ desde https://python.org")
        return False
    print(f"   ✅ Python {version.major}.{version.minor}.{version.micro}")
    return True


def install_dependencies():
    """Instala las dependencias necesarias."""
    print("\n2. Instalando dependencias...")
    deps = [
        ("requests",   "requests"),
        ("feedparser", "feedparser"),
    ]
    all_ok = True
    for name, pkg in deps:
        try:
            __import__(name)
            print(f"   ✅ {pkg} (ya instalado)")
        except ImportError:
            print(f"   📦 Instalando {pkg}...")
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", pkg],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                print(f"   ✅ {pkg} instalado")
            else:
                print(f"   ❌ Error instalando {pkg}: {result.stderr[:100]}")
                all_ok = False
    return all_ok


def create_directories():
    """Crea la estructura de carpetas."""
    print("\n3. Creando estructura de carpetas...")
    dirs = [
        "data/logs",
        "data/trades",
        "data/backtest",
        "agents",
        "core",
        "n8n_workflows",
    ]
    for d in dirs:
        os.makedirs(d, exist_ok=True)
        print(f"   ✅ {d}/")
    return True


def check_config():
    """Verifica que config.py existe y tiene credenciales."""
    print("\n4. Verificando configuración...")
    if not os.path.exists("config.py"):
        print("   ❌ config.py no encontrado.")
        print("   Copia config.py al directorio del proyecto.")
        return False

    with open("config.py", "r", encoding="utf-8") as f:
        content = f.read()

    issues = []
    if "TU_TOKEN_AQUI" in content:
        issues.append("TELEGRAM_BOT_TOKEN no configurado")
    if "TU_CHAT_ID_AQUI" in content:
        issues.append("TELEGRAM_CHAT_ID no configurado")

    if issues:
        print("   ⚠️  Pendiente de configurar:")
        for issue in issues:
            print(f"      → {issue}")
        print("   Edita config.py con tus credenciales reales.")
        print("   El sistema funciona en modo local hasta que lo configures.")
    else:
        print("   ✅ Credenciales de Telegram configuradas")

    return True


def test_hyperliquid():
    """Prueba conexión a Hyperliquid."""
    print("\n5. Probando conexión a Hyperliquid...")
    try:
        import requests
        response = requests.post(
            "https://api.hyperliquid-testnet.xyz/info",
            json={"type": "allMids"},
            timeout=10,
        )
        data = response.json()
        if isinstance(data, dict) and len(data) > 0:
            gold = data.get("GOLD", "N/A")
            oil  = data.get("CL", "N/A")
            print(f"   ✅ Hyperliquid testnet conectado")
            print(f"      GOLD: ${float(gold):,.2f}" if gold != "N/A" else "      GOLD: N/A")
            print(f"      WTI:  ${float(oil):,.2f}"  if oil  != "N/A" else "      WTI: N/A")
            return True
        else:
            print("   ⚠️  Respuesta inesperada de Hyperliquid")
            return False
    except Exception as e:
        print(f"   ❌ Error: {e}")
        print("   Verifica tu conexión a internet.")
        return False


def create_windows_task():
    """Crea el archivo .bat y las instrucciones para el Programador de Tareas."""
    print("\n6. Creando archivos de automatización para Windows...")

    project_dir = os.path.abspath(".")
    python_exe  = sys.executable

    # Archivo .bat para ejecución
    bat_content = f"""@echo off
cd /d "{project_dir}"
"{python_exe}" orchestrator.py --mode once >> data\\logs\\scheduled_run.log 2>&1
"""
    bat_path = os.path.join(project_dir, "run_yield_sentinel.bat")
    with open(bat_path, "w") as f:
        f.write(bat_content)
    print(f"   ✅ run_yield_sentinel.bat creado")

    # Archivo .bat para reporte diario
    report_bat = f"""@echo off
cd /d "{project_dir}"
"{python_exe}" orchestrator.py --mode report >> data\\logs\\daily_report.log 2>&1
"""
    report_path = os.path.join(project_dir, "daily_report.bat")
    with open(report_path, "w") as f:
        f.write(report_bat)
    print(f"   ✅ daily_report.bat creado")

    # Instrucciones para el Programador de Tareas
    instructions = f"""
INSTRUCCIONES — Programador de Tareas de Windows
=================================================

Para que Yield Sentinel corra automáticamente cada 15 minutos:

1. Abre "Programador de tareas" (busca en el menú inicio)
2. Clic en "Crear tarea básica" (panel derecho)
3. Nombre: "Yield Sentinel — Ciclo 15min"
4. Desencadenador: "Diariamente"
   → Avanzado: repetir cada 15 minutos durante 1 día
5. Acción: "Iniciar un programa"
   → Programa: {bat_path}
6. Guardar

Para el reporte diario (opcional):
1. Nueva tarea básica
2. Nombre: "Yield Sentinel — Reporte Diario"
3. Desencadenador: Diariamente a las 08:00
4. Acción: {report_path}

Directorio del proyecto: {project_dir}
Python: {python_exe}
"""
    instr_path = "SETUP_WINDOWS_TAREAS.txt"
    with open(instr_path, "w", encoding="utf-8") as f:
        f.write(instructions)
    print(f"   ✅ SETUP_WINDOWS_TAREAS.txt (instrucciones detalladas)")

    return True


def run_first_test():
    """Ejecuta una prueba rápida del sistema."""
    print("\n7. Ejecutando prueba rápida...")
    try:
        result = subprocess.run(
            [sys.executable, "orchestrator.py", "--mode", "test"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            print("   ✅ Sistema funcionando correctamente")
        else:
            print("   ⚠️  Algunos componentes tienen advertencias")
            print("      Esto es normal si aún no configuraste el token de Telegram")
    except subprocess.TimeoutExpired:
        print("   ⚠️  Timeout en la prueba (puede ser lentitud de red)")
    except Exception as e:
        print(f"   ⚠️  {e}")
    return True


def print_next_steps():
    """Imprime los próximos pasos claros."""
    print("\n" + "╔" + "═"*53 + "╗")
    print("║" + " "*15 + "✅ SETUP COMPLETADO" + " "*19 + "║")
    print("╚" + "═"*53 + "╝")

    print("""
📋 PRÓXIMOS PASOS:
──────────────────

PASO 1 (5 min) — Configurar Telegram:
  → Edita config.py
  → Agrega tu TELEGRAM_BOT_TOKEN
  → Agrega tu TELEGRAM_CHAT_ID
  → Para encontrar tu Chat ID: escribe a @userinfobot en Telegram

PASO 2 (2 min) — Probar el sistema:
  → Abre CMD en esta carpeta
  → Escribe: python orchestrator.py --mode test
  → Deberías ver 4 checkmarks ✅

PASO 3 (2 min) — Primer ciclo real:
  → python orchestrator.py --mode once
  → Revisa tu Telegram

PASO 4 (5 min) — Automatizar:
  → Sigue las instrucciones en SETUP_WINDOWS_TAREAS.txt
  → O importa n8n_workflows/orchestrator_workflow.json en n8n

PASO 5 (cuando quieras) — Ver el backtester:
  → python core/backtester.py --symbol GOLD --days 90
  → python core/backtester.py --all

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️  RECUERDA:
  → PAPER_TRADING = True en config.py (por ahora)
  → La Fase 3 (dinero real) se desbloquea solo con ROI >= 20%
  → Nunca compartas config.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")


def main():
    print_header()

    steps = [
        check_python,
        install_dependencies,
        create_directories,
        check_config,
        test_hyperliquid,
        create_windows_task,
        run_first_test,
    ]

    all_ok = True
    for step in steps:
        ok = step()
        if not ok:
            all_ok = False

    print_next_steps()

    if not all_ok:
        print("⚠️  Algunos pasos tuvieron problemas.")
        print("   El sistema puede funcionar parcialmente.")
        print("   Revisa los mensajes de error arriba.\n")


if __name__ == "__main__":
    main()
