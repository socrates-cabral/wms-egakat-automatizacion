import sys
from pathlib import Path

# Permite importar paquetes del proyecto (jarvis, crypto_bot, etc.) en pytest
sys.path.insert(0, str(Path(__file__).parent))
