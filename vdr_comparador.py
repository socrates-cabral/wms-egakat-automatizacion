"""
vdr_comparador.py — puente (raiz)
Redirige la ejecucion al script real en VDR_Comparador\
El Task Scheduler sigue apuntando a esta ruta sin cambios.
"""
import subprocess, sys, os

script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "VDR_Comparador", "vdr_comparador.py")
sys.exit(subprocess.run([sys.executable, script]).returncode)
