import sys
sys.path.insert(0, "C:\\ClaudeWork")
from unittest.mock import patch, MagicMock


def test_process_message_retorna_string():
    """process_message siempre retorna un string no vacío."""
    mock_response = MagicMock()
    mock_response.text = "Son las 21:00, Señor Sócrates."

    with patch("google.generativeai.GenerativeModel") as MockModel:
        mock_chat = MagicMock()
        mock_chat.send_message.return_value = mock_response
        MockModel.return_value.start_chat.return_value = mock_chat

        from jarvis.agent import Agent
        a = Agent()
        a._chat = mock_chat
        result = a.process_message("¿qué hora es?")

    assert isinstance(result, str)
    assert len(result) > 0


def test_process_message_error_retorna_string():
    """process_message retorna string descriptivo si Gemini falla."""
    with patch("google.generativeai.GenerativeModel") as MockModel:
        mock_chat = MagicMock()
        mock_chat.send_message.side_effect = Exception("API error")
        MockModel.return_value.start_chat.return_value = mock_chat

        from jarvis.agent import Agent
        a = Agent()
        a._chat = mock_chat
        result = a.process_message("test")

    assert isinstance(result, str)
    assert "error" in result.lower() or "Error" in result
