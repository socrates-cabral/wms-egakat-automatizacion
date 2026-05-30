"""Lanzador silencioso de JARVIS — usar con pythonw para no abrir terminal."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from jarvis.main import main
main()
