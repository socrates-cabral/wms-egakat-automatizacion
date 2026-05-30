import sys
sys.stdout.reconfigure(encoding="utf-8")

import asyncio
import os
import subprocess
import tempfile
import logging
from pathlib import Path

import speech_recognition as sr
import edge_tts

from jarvis.config import TTS_VOICE, TTS_RATE, STARTUP_SOUND

logger = logging.getLogger("jarvis.voice")


async def _tts_async(text: str, output: str):
    tts = edge_tts.Communicate(text, TTS_VOICE, rate=TTS_RATE)
    await tts.save(output)


def _play_audio(path: str):
    """Reproduce un MP3. Intenta playsound3, fallback a PowerShell."""
    try:
        from playsound3 import playsound
        playsound(path)
        return
    except Exception:
        pass
    # Fallback: PowerShell MediaPlayer (bloqueante)
    try:
        abs_path = str(Path(path).resolve()).replace("\\", "/")
        ps_script = (
            "Add-Type -AssemblyName presentationCore; "
            f"$p = New-Object System.Windows.Media.MediaPlayer; "
            f"$p.Open([uri]'{abs_path}'); "
            "$p.Play(); Start-Sleep -Milliseconds 500; "
            "while ($p.NaturalDuration.HasTimeSpan -eq $false) { Start-Sleep -Milliseconds 200 }; "
            "Start-Sleep -Seconds ([int]$p.NaturalDuration.TimeSpan.TotalSeconds + 1)"
        )
        subprocess.run(["powershell", "-Command", ps_script],
                       capture_output=True, timeout=30)
    except Exception as e:
        logger.error(f"Audio playback error: {e}")
        print(f"[audio] {path}")


def speak(text: str):
    """Convierte texto a voz (edge-tts) y lo reproduce."""
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
        tmp = f.name
    try:
        asyncio.run(_tts_async(text, tmp))
        _play_audio(tmp)
    except Exception as e:
        logger.error(f"TTS error: {e}")
        print(f"JARVIS: {text}")
    finally:
        try:
            os.unlink(tmp)
        except Exception:
            pass


def _find_wasapi_input() -> tuple[int | None, int]:
    """Busca el primer dispositivo de entrada WASAPI. Retorna (device_idx, sample_rate)."""
    try:
        import sounddevice as sd
        hostapis = sd.query_hostapis()
        wasapi_api = next((i for i, h in enumerate(hostapis) if "WASAPI" in h["name"]), None)
        if wasapi_api is None:
            return None, 44100
        for i, d in enumerate(sd.query_devices()):
            if d["hostapi"] == wasapi_api and d["max_input_channels"] > 0:
                return i, int(d["default_samplerate"])
    except Exception:
        pass
    return None, 44100


def listen(duration: int = 5, timeout: int = 5) -> str:
    """Escucha el micrófono y retorna texto. Usa sounddevice con WASAPI."""
    try:
        import sounddevice as sd
        import numpy as np
        import scipy.io.wavfile as wav_io

        device_idx, sample_rate = _find_wasapi_input()
        logger.debug("STT device=%s samplerate=%s", device_idx, sample_rate)

        print("🎤 Escuchando...")
        audio = sd.rec(
            int(duration * sample_rate),
            samplerate=sample_rate,
            channels=1,
            dtype="int16",
            device=device_idx,
        )
        sd.wait()

        # Guardar como WAV temporal
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            wav_path = f.name
        wav_io.write(wav_path, sample_rate, audio)

        # Transcribir con SpeechRecognition
        r = sr.Recognizer()
        with sr.AudioFile(wav_path) as source:
            audio_data = r.record(source)
        os.unlink(wav_path)

        text = r.recognize_google(audio_data, language="es-CL")
        return text

    except sr.UnknownValueError:
        return ""
    except sr.RequestError as e:
        logger.error(f"Google STT error: {e}")
        return ""
    except Exception as e:
        logger.error(f"listen() error: {e}")
        return ""


def play_startup():
    """Reproduce el sonido de arranque si el archivo existe."""
    if STARTUP_SOUND.exists():
        try:
            _play_audio(str(STARTUP_SOUND))
        except Exception as e:
            logger.debug(f"Startup sound error: {e}")
