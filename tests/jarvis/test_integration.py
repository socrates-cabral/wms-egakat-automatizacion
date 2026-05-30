import sys
sys.path.insert(0, "C:\\ClaudeWork")
from unittest.mock import patch
from pathlib import Path


def test_config_rutas_base_existe():
    """BASE_DIR y APUESTAS_OUT apuntan a directorios que existen."""
    from jarvis.config import BASE_DIR, APUESTAS_OUT
    assert BASE_DIR.exists(), f"BASE_DIR no existe: {BASE_DIR}"
    assert APUESTAS_OUT.exists(), f"APUESTAS_OUT no existe: {APUESTAS_OUT}"


def test_get_estado_sistema_no_crash_sin_api():
    """get_estado_sistema no explota aunque la API de clima falle."""
    from jarvis.tools import get_estado_sistema
    with patch("requests.get", side_effect=Exception("timeout")):
        result = get_estado_sistema()
    assert isinstance(result, dict)
    assert "hora" in result


def test_tomar_nota_ciclo_completo(tmp_path, monkeypatch):
    """Ciclo completo: escribir nota y verificar que está en el archivo."""
    import jarvis.tools as t
    monkeypatch.setattr(t, "NOTAS_PATH", tmp_path / "notas.txt")
    t.tomar_nota("Test nota Jarvis integración")
    contenido = (tmp_path / "notas.txt").read_text(encoding="utf-8")
    assert "Test nota Jarvis integración" in contenido


def test_get_apuestas_sin_reporte_hoy(tmp_path, monkeypatch):
    """get_apuestas retorna mensaje claro si no hay reporte."""
    import jarvis.tools as t
    monkeypatch.setattr(t, "APUESTAS_OUT", tmp_path)
    result = t.get_apuestas()
    assert "Sin reporte" in result.get("estado", "")


def test_system_prompt_contiene_identidad():
    """SYSTEM_PROMPT contiene los elementos clave de identidad."""
    from jarvis.config import SYSTEM_PROMPT
    assert "J.A.R.V.I.S" in SYSTEM_PROMPT
    assert "Señor Sócrates" in SYSTEM_PROMPT
    assert "Egakat" in SYSTEM_PROMPT
