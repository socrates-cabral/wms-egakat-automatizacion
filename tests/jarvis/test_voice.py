import sys
sys.path.insert(0, "C:\\ClaudeWork")


def test_speak_no_crash(monkeypatch):
    """speak() no explota si la reproducción de audio falla."""
    import jarvis.voice as v
    monkeypatch.setattr(v, "_play_audio", lambda path: None)
    # No debe lanzar excepción
    v.speak("Prueba de voz, Señor Sócrates.")


def test_play_startup_sin_archivo(tmp_path, monkeypatch):
    """play_startup no explota si no existe startup.mp3."""
    import jarvis.config as cfg
    import jarvis.voice as v
    monkeypatch.setattr(cfg, "STARTUP_SOUND", tmp_path / "no_existe.mp3")
    v.play_startup()  # No debe lanzar excepción
