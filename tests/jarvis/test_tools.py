import sys, json
sys.path.insert(0, "C:\\ClaudeWork")
from unittest.mock import patch
from pathlib import Path


def test_get_estado_sistema_estructura():
    """get_estado_sistema retorna dict con claves esperadas."""
    with patch("requests.get") as mock_get:
        mock_get.return_value.json.return_value = {
            "current_condition": [{"temp_C": "15", "weatherDesc": [{"value": "Partly cloudy"}]}]
        }
        from jarvis.tools import get_estado_sistema
        result = get_estado_sistema()
    assert "hora" in result
    assert "btc" in result
    assert "eth" in result


def test_get_estado_sistema_sin_crypto(tmp_path, monkeypatch):
    """get_estado_sistema funciona aunque no existan archivos de estado."""
    import jarvis.tools as t
    monkeypatch.setattr(t, "CRYPTO_BTC", tmp_path / "no_existe.json")
    monkeypatch.setattr(t, "CRYPTO_ETH", tmp_path / "no_existe2.json")
    with patch("requests.get") as mock_get:
        mock_get.return_value.json.return_value = {
            "current_condition": [{"temp_C": "15", "weatherDesc": [{"value": "Clear"}]}]
        }
        result = t.get_estado_sistema()
    assert result["btc"]["pnl"] == "sin datos"


def test_tomar_nota(tmp_path, monkeypatch):
    """tomar_nota escribe en el archivo de notas."""
    import jarvis.tools as t
    monkeypatch.setattr(t, "NOTAS_PATH", tmp_path / "notas.txt")
    t.tomar_nota("Comprar pan mañana")
    assert "Comprar pan mañana" in (tmp_path / "notas.txt").read_text(encoding="utf-8")


def test_abrir_aplicacion_no_crash():
    """abrir_aplicacion retorna mensaje sin explotar para app desconocida."""
    from jarvis.tools import abrir_aplicacion
    result = abrir_aplicacion("app_que_no_existe_xyz_123")
    assert isinstance(result, str)
    assert len(result) > 0


def test_set_timer_retorna_mensaje():
    """set_timer retorna string confirmando el timer."""
    from jarvis.tools import set_timer
    result = set_timer(1, "test")
    assert "1 minuto" in result


def test_get_apuestas_sin_reporte(tmp_path, monkeypatch):
    """get_apuestas retorna mensaje claro si no hay reporte hoy."""
    import jarvis.tools as t
    monkeypatch.setattr(t, "APUESTAS_OUT", tmp_path)
    result = t.get_apuestas()
    assert "Sin reporte" in result.get("estado", "")
