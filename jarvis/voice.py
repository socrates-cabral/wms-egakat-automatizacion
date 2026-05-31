import sys
sys.stdout.reconfigure(encoding="utf-8")

import asyncio
import os
import socket
import subprocess
import tempfile
import logging
from pathlib import Path

import json
import requests as _requests
import edge_tts

from jarvis.config import TTS_VOICE, TTS_RATE, STARTUP_SOUND

logger = logging.getLogger("jarvis.voice")

# ─── Fix WinError 50: forzar IPv4 para Google STT ──────────────────────────
# El error OSError [WinError 50] ocurre cuando urllib intenta IPv6 en esta red.
_orig_getaddrinfo = socket.getaddrinfo
def _ipv4_only(host, port, family=0, type=0, proto=0, flags=0):
    results = _orig_getaddrinfo(host, port, family, type, proto, flags)
    ipv4 = [r for r in results if r[0] == socket.AF_INET]
    return ipv4 if ipv4 else results
socket.getaddrinfo = _ipv4_only

# ─── Constantes ────────────────────────────────────────────────────────────
_MIC_BOOST      = 25     # ganancia digital: Intel Smart Sound tiene ganancia baja
_MIC_SAMPLERATE = 48000  # nativo del Intel Smart Sound Technology
_STT_SAMPLERATE = 16000  # requerido por Google STT
_DOWNSAMPLE     = _MIC_SAMPLERATE // _STT_SAMPLERATE  # = 3


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


def _clean_for_tts(text: str) -> str:
    """Elimina markdown y símbolos que edge-tts leería literal."""
    import re
    t = text
    t = re.sub(r'\*{1,3}([^*]+)\*{1,3}', r'\1', t)   # **bold**, *italic*, ***
    t = re.sub(r'#{1,6}\s*', '', t)                    # ## headers
    t = re.sub(r'`{1,3}([^`]*)`{1,3}', r'\1', t)      # `code`, ```block```
    t = re.sub(r'^\s*[-•*]\s+', '', t, flags=re.M)     # - • * bullets
    t = re.sub(r'^\s*\d+\.\s+', '', t, flags=re.M)     # 1. numbered lists
    t = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', t)     # [link](url)
    t = re.sub(r'_{1,2}([^_]+)_{1,2}', r'\1', t)      # _italic_, __bold__
    t = re.sub(r'\n{2,}', '. ', t)                     # párrafos → pausa
    t = re.sub(r'\n', ', ', t)                         # saltos de línea → coma
    t = re.sub(r'\s{2,}', ' ', t)                      # espacios múltiples
    return t.strip()


def speak(text: str):
    """Convierte texto a voz (edge-tts) y lo reproduce."""
    text = _clean_for_tts(text)
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


def _find_mic_device() -> int | None:
    """Devuelve el índice del dispositivo de entrada preferido."""
    try:
        import sounddevice as sd
        devices = [(i, d) for i, d in enumerate(sd.query_devices())
                   if d['max_input_channels'] > 0]
        # Preferir Microphone Array 1 (Intel Smart Sound)
        for i, d in devices:
            name = d['name'].lower()
            if 'array 1' in name or 'intel' in name or 'smart sound' in name:
                return i
        return devices[0][0] if devices else None
    except Exception:
        return None


def _record_sounddevice(duration: int, device: int) -> bytes | None:
    """Graba con sounddevice (funciona sin Qt activo)."""
    try:
        import sounddevice as sd
        import numpy as np
        data = sd.rec(
            int(duration * _MIC_SAMPLERATE),
            samplerate=_MIC_SAMPLERATE,
            channels=2,
            dtype='int16',
            device=device,
            blocking=True,
        )
        # Boost + downsample + mono (canal L)
        boosted  = np.clip(data.astype('int32') * _MIC_BOOST, -32768, 32767).astype('int16')
        mono_16k = boosted[::_DOWNSAMPLE, 0]
        peak = int(abs(boosted).max())
        logger.info("sounddevice: %d bytes, peak=%d (%.0f%%)",
                    len(mono_16k)*2, peak, peak/32767*100)
        return mono_16k.tobytes()
    except Exception as e:
        logger.warning("sounddevice falló: %s", e)
        return None


def _record_winmm(duration: int) -> bytes | None:
    """Graba con WinMM (fallback cuando Qt bloquea sounddevice)."""
    try:
        import struct
        import numpy as np
        from jarvis import winmm_capture
        pcm = winmm_capture.record(duration, samplerate=_MIC_SAMPLERATE,
                                   channels=2, bits=16)
        if pcm is None:
            return None
        # Boost + downsample + mono
        n = len(pcm) // 2
        samples = np.frombuffer(pcm, dtype='<i2').reshape(-1, 2)
        boosted  = np.clip(samples.astype('int32') * _MIC_BOOST, -32768, 32767).astype('int16')
        mono_16k = boosted[::_DOWNSAMPLE, 0]
        peak = int(abs(boosted).max())
        logger.info("winmm: %d bytes, peak=%d (%.0f%%)",
                    len(mono_16k)*2, peak, peak/32767*100)
        return mono_16k.tobytes()
    except Exception as e:
        logger.warning("winmm falló: %s", e)
        return None


def _google_stt_raw(pcm_16k: bytes, language: str = "es-CL") -> str:
    """Llama a Google Speech API directamente con PCM raw.

    Evita speech_recognition.get_flac_data() que usa subprocess.Popen
    — el cual falla en Python 3.14/Windows con WinError 50 (DuplicateHandle).
    Enviamos audio/l16 (PCM 16-bit LE) directo; Google lo acepta sin conversión.
    """
    url = "https://www.google.com/speech-api/v2/recognize"
    params = {
        "client": "chromium",
        "lang":   language,
        "key":    "AIzaSyBOti4mM-6x9WDnZIjIeyEU21OpBXqWBgw",  # clave pública de Chromium
    }
    headers = {"Content-Type": f"audio/l16; rate={_STT_SAMPLERATE}"}
    try:
        resp = _requests.post(url, params=params, headers=headers,
                              data=pcm_16k, timeout=10)
        for line in resp.text.strip().split("\n"):
            if not line:
                continue
            data = json.loads(line)
            for result in data.get("result", []):
                alts = result.get("alternative", [])
                if alts:
                    return alts[0].get("transcript", "")
        return ""
    except Exception as e:
        logger.error("Google STT raw error: %s", e)
        return ""


def listen(duration: int = 5, timeout: int = 5) -> str:
    """Escucha el micrófono y retorna texto transcrito."""
    try:
        # 1. Grabar: sounddevice primero, winmm si Qt bloquea sounddevice
        device  = _find_mic_device()
        pcm_16k = _record_sounddevice(duration, device) if device is not None else None
        if pcm_16k is None:
            logger.info("sounddevice falló — usando winmm_capture")
            pcm_16k = _record_winmm(duration)
        if pcm_16k is None:
            logger.error("No se pudo capturar audio")
            return ""

        # 2. STT sin subprocess (evita WinError 50 de FLAC en Python 3.14)
        return _google_stt_raw(pcm_16k)

    except Exception as e:
        import traceback as _tb
        logger.error("listen() error: %s\n%s", e, _tb.format_exc())
        return ""


def play_startup():
    """Reproduce el sonido de arranque si el archivo existe."""
    if STARTUP_SOUND.exists():
        try:
            _play_audio(str(STARTUP_SOUND))
        except Exception as e:
            logger.debug(f"Startup sound error: {e}")
