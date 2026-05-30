from pathlib import Path
import pytest
from jarvis.ui.memory import MemoryClient


def test_load_context_returns_file_content(tmp_path):
    memory_dir = tmp_path / "memory"
    memory_dir.mkdir()
    (memory_dir / "user_profile.md").write_text(
        "---\nname: test\n---\n\nSócrates es Head of Control Management.",
        encoding="utf-8",
    )
    client = MemoryClient(memory_dir=memory_dir, priority_files=["user_profile.md"])
    ctx = client.load_context()
    assert "Sócrates es Head of Control Management." in ctx


def test_load_context_strips_frontmatter(tmp_path):
    memory_dir = tmp_path / "memory"
    memory_dir.mkdir()
    (memory_dir / "user_profile.md").write_text(
        "---\nname: test\ntype: user\n---\n\nContenido real.",
        encoding="utf-8",
    )
    client = MemoryClient(memory_dir=memory_dir, priority_files=["user_profile.md"])
    ctx = client.load_context()
    assert "---" not in ctx
    assert "Contenido real." in ctx


def test_load_context_skips_missing_files(tmp_path):
    memory_dir = tmp_path / "memory"
    memory_dir.mkdir()
    client = MemoryClient(memory_dir=memory_dir, priority_files=["no_existe.md"])
    ctx = client.load_context()
    assert ctx == ""


def test_persist_session_writes_file(tmp_path):
    memory_dir = tmp_path / "memory"
    memory_dir.mkdir()
    client = MemoryClient(memory_dir=memory_dir)
    client.persist_session("jarvis_session_test.md", "Contenido de sesión.")
    result = (memory_dir / "jarvis_session_test.md").read_text(encoding="utf-8")
    assert "Contenido de sesión." in result


def test_persist_session_overwrites_existing(tmp_path):
    memory_dir = tmp_path / "memory"
    memory_dir.mkdir()
    client = MemoryClient(memory_dir=memory_dir)
    client.persist_session("note.md", "Primera versión.")
    client.persist_session("note.md", "Segunda versión.")
    result = (memory_dir / "note.md").read_text(encoding="utf-8")
    assert "Segunda versión." in result
    assert "Primera versión." not in result
