"""
run_todos.py — puente (raiz)
Redirige la ejecucion al script real en WMS_Automatizacion\
El Task Scheduler sigue apuntando a esta ruta sin cambios.
"""
import subprocess, sys, os

script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "WMS_Automatizacion", "run_todos.py")
sys.exit(subprocess.run([sys.executable, script]).returncode)
