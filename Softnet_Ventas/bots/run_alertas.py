"""
Entrypoint para Task Scheduler / n8n.
py C:\\ClaudeWork\\Softnet_Ventas\\bots\\run_alertas.py
"""
import sys
sys.stdout.reconfigure(encoding="utf-8")

from pathlib import Path
from dotenv import load_dotenv

_BASE = Path(__file__).resolve().parent.parent
load_dotenv(_BASE / ".env")
load_dotenv(_BASE.parent / ".env")

sys.path.insert(0, str(Path(__file__).parent))
from alertas_engine import run_alertas_diarias

if __name__ == "__main__":
    resultado = run_alertas_diarias()
    sys.exit(0 if resultado is not None else 1)
