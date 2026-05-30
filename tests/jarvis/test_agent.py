import sys
sys.path.insert(0, "C:\\ClaudeWork")
from unittest.mock import patch, MagicMock


def test_process_message_retorna_string():
    """process_message siempre retorna un string no vacío."""
    mock_response = MagicMock()
    mock_response.text = "Son las 21:00, Señor Sócrates."

    with patch("google.genai.Client") as MockClient:
        mock_models = MagicMock()
        mock_models.generate_content.return_value = mock_response
        MockClient.return_value.models = mock_models

        from jarvis.agent import Agent
        a = Agent()
        result = a.process_message("¿qué hora es?")

    assert isinstance(result, str)
    assert len(result) > 0


def test_process_message_error_retorna_string():
    """process_message retorna string descriptivo si Gemini falla."""
    with patch("google.genai.Client") as MockClient:
        mock_models = MagicMock()
        mock_models.generate_content.side_effect = Exception("API error")
        MockClient.return_value.models = mock_models

        from jarvis.agent import Agent
        a = Agent()
        result = a.process_message("test")

    assert isinstance(result, str)
    assert "error" in result.lower() or "Error" in result
