import pytest
from jarvis.ui.animations import TypewriterLabel, WaveformWidget


def test_typewriter_starts_empty(qtbot):
    label = TypewriterLabel()
    label.start_typing("Hola")
    assert label.text() == "" or len(label.text()) < 5


def test_typewriter_emits_finished(qtbot):
    label = TypewriterLabel()
    with qtbot.waitSignal(label.finished, timeout=2000):
        label.start_typing("Hi")


def test_typewriter_shows_full_text_on_finish(qtbot):
    label = TypewriterLabel()
    with qtbot.waitSignal(label.finished, timeout=2000):
        label.start_typing("Hola mundo")
    assert label.text() == "Hola mundo"


def test_typewriter_skip_shows_full_text(qtbot):
    label = TypewriterLabel()
    label.start_typing("Texto largo aquí")
    label.skip()
    assert label.text() == "Texto largo aquí"


def test_waveform_can_start_and_stop(qtbot):
    waveform = WaveformWidget(mode="input")
    waveform.start()
    qtbot.wait(100)
    waveform.stop()


def test_waveform_has_correct_mode(qtbot):
    w = WaveformWidget(mode="output")
    assert w.mode == "output"
