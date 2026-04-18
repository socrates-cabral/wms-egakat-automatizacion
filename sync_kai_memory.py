"""
sync_kai_memory.py
Sincroniza C--ClaudeWork/memory/ → C--KaiClaude/memory/
Ejecutado via hook PostToolUse cada vez que se escribe un archivo de memoria.
"""
import sys
import shutil
from pathlib import Path

SRC = Path(r"C:\Users\Socrates Cabral\.claude\projects\C--ClaudeWork\memory")
DST = Path(r"C:\Users\Socrates Cabral\.claude\projects\C--KaiClaude\memory")

def sync():
    if not SRC.exists():
        return
    DST.mkdir(parents=True, exist_ok=True)
    for f in SRC.glob("*.md"):
        dst_file = DST / f.name
        shutil.copy2(f, dst_file)
    print(f"[sync_kai_memory] Sincronizados {len(list(SRC.glob('*.md')))} archivos -> {DST}")

if __name__ == "__main__":
    sync()
