import re
import logging
from pathlib import Path

logger = logging.getLogger("jarvis.ui.memory")

_DEFAULT_MEMORY_DIR = Path(r"C:\Users\Socrates Cabral\.claude\projects\C--ClaudeWork\memory")

_DEFAULT_PRIORITY_FILES = [
    "user_profile.md",
    "crypto_estrategia_bot.md",
    "project_kpi_ops.md",
    "project_agente_apuestas.md",
    "project_jarvis.md",
    "project_mirofish.md",
]

_FRONTMATTER_RE = re.compile(r"\A---\n.*?\n---\s*", re.DOTALL)


class MemoryClient:
    def __init__(
        self,
        memory_dir: Path = _DEFAULT_MEMORY_DIR,
        priority_files: list[str] | None = None,
    ):
        self.memory_dir = memory_dir
        self.priority_files = priority_files if priority_files is not None else _DEFAULT_PRIORITY_FILES

    def load_context(self) -> str:
        """Lee los archivos de memoria prioritarios y retorna un bloque de contexto."""
        blocks: list[str] = []
        for fname in self.priority_files:
            path = self.memory_dir / fname
            if not path.exists():
                continue
            try:
                raw = path.read_text(encoding="utf-8")
                content = _FRONTMATTER_RE.sub("", raw).strip()
                if content:
                    blocks.append(f"[{fname}]\n{content}")
            except Exception as e:
                logger.warning(f"No se pudo leer {fname}: {e}")
        return "\n\n".join(blocks)

    def persist_session(self, filename: str, content: str) -> None:
        """Escribe o sobreescribe un archivo en el directorio de memoria."""
        path = (self.memory_dir / filename).resolve()
        if not str(path).startswith(str(self.memory_dir.resolve())):
            logger.error(f"Ruta fuera del memory_dir rechazada: {filename}")
            return
        try:
            self.memory_dir.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            logger.info(f"Memory persistida: {filename}")
        except Exception as e:
            logger.error(f"Error persistiendo {filename}: {e}")
