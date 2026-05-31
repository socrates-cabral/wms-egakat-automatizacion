import sys
sys.stdout.reconfigure(encoding="utf-8")

import asyncio
import os
import socket
import subprocess
import tempfile
import threading
import logging
from pathlib import Path

import json
import requests as _requests
import edge_tts

from jarvis.config import TTS_VOICE, TTS_RATE, STARTUP_SOUND

logger = logging.getLogger("jarvis.voice")

# ─── TTS cancel support ────────────────────────────────────────────────────
_tts_cancel = threading.Event()
_tts_lock   = threading.Lock()                 # protege _tts_proc (Bug 1)
_tts_proc: subprocess.Popen | None = None      # proceso PS de playback activo
_last_tmp:  str | None             = None       # MP3 temp del ciclo anterior (Bug 8)


def cancel_tts() -> None:
    """Interrumpe el TTS en curso. Seguro desde cualquier thread."""
    _tts_cancel.set()
    with _tts_lock:
        proc = _tts_proc
    if proc is not None:
        try:
            proc.kill()
        except Exception:
            pass

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

# VAD (Voice Activity Detection) — chunk-based silence detection
_CHUNK_S         = 0.5   # duración de cada chunk de grabación (segundos)
_SILENCE_THRESH  = 3000  # pico mínimo para "voz" (post-boost ×25 → ~120 raw; Bug 5)
_MAX_SILENCE_S   = 1.5   # silencio post-habla antes de cortar
_PRESPEECH_S     = 5.0   # timeout si no hay voz al inicio
_MAX_TOTAL_S     = 10.0  # límite absoluto de grabación


async def _tts_async(text: str, output: str):
    tts = edge_tts.Communicate(text, TTS_VOICE, rate=TTS_RATE)
    await tts.save(output)


def _play_audio(path: str):
    """Reproduce un MP3. Intenta playsound3 (cancel best-effort), fallback PS (cancel real).
    Bug 2 nota: playsound3 daemon thread puede seguir ~1-2s tras cancel — comportamiento aceptable.
    """
    global _tts_proc
    if _tts_cancel.is_set():
        return
    try:
        from playsound3 import playsound
        t = threading.Thread(target=playsound, args=(path,), daemon=True)
        t.start()
        while t.is_alive():
            if _tts_cancel.is_set():
                return  # daemon termina solo; audio puede prolongarse ~1s
            t.join(timeout=0.1)
        return
    except Exception:
        pass
    # Fallback PowerShell — proceso mateable vía _tts_proc (Bug 1: lock en acceso)
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
        proc = subprocess.Popen(["powershell", "-Command", ps_script],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        with _tts_lock:
            _tts_proc = proc
        proc.wait()
    except Exception as e:
        logger.error(f"Audio playback error: {e}")
    finally:
        with _tts_lock:
            _tts_proc = None


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
    """Convierte texto a voz (edge-tts) y lo reproduce. Cancelable via cancel_tts()."""
    global _last_tmp
    # Bug 8: intentar borrar el MP3 del ciclo anterior (pudo quedar abierto por daemon playsound3)
    if _last_tmp:
        try:
            os.unlink(_last_tmp)
        except Exception:
            pass
        _last_tmp = None
    _tts_cancel.clear()
    text = _clean_for_tts(text)
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
        tmp = f.name
    _last_tmp = tmp
    try:
        asyncio.run(_tts_async(text, tmp))
        _play_audio(tmp)
    except Exception as e:
        logger.error(f"TTS error: {e}")
        print(f"JARVIS: {text}")
    finally:
        try:
            os.unlink(tmp)
            _last_tmp = None
        except PermissionError:
            pass  # daemon playsound3 aún tiene el archivo — se limpia en el próximo speak()
        except Exception:
            _last_tmp = None


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


def _record_sounddevice_vad(device: int) -> bytes | None:
    """Graba con sounddevice usando VAD chunk-based. Para cuando hay silencio."""
    try:
        import sounddevice as sd
        import numpy as np

        chunk_frames       = int(_CHUNK_S * _MIC_SAMPLERATE)
        max_silence_chunks = int(_MAX_SILENCE_S  / _CHUNK_S)
        max_prespeech      = int(_PRESPEECH_S    / _CHUNK_S)
        max_total          = int(_MAX_TOTAL_S    / _CHUNK_S)
        downsample         = _MIC_SAMPLERATE // _STT_SAMPLERATE

        speech_chunks: list = []
        speech_started   = False
        silence_chunks   = 0
        prespeech_chunks = 0

        for _ in range(max_total):
            chunk = sd.rec(chunk_frames, samplerate=_MIC_SAMPLERATE,
                           channels=2, dtype='int16', device=device, blocking=True)
            boosted = np.clip(chunk.astype('int32') * _MIC_BOOST,
                              -32768, 32767).astype('int16')
            peak = int(abs(boosted).max())

            if peak > _SILENCE_THRESH:
                speech_started = True
                silence_chunks = 0
                speech_chunks.append(boosted)
            elif speech_started:
                silence_chunks += 1
                speech_chunks.append(boosted)
                if silence_chunks >= max_silence_chunks:
                    break
            else:
                prespeech_chunks += 1
                if prespeech_chunks >= max_prespeech:
                    logger.debug("VAD: sin voz en %.1fs — timeout", _PRESPEECH_S)
                    return None

        if not speech_chunks or not speech_started:
            return None

        all_data = np.concatenate(speech_chunks)
        mono_16k = all_data[::downsample, 0]
        peak_all = int(abs(all_data).max())
        duration = len(all_data) / _MIC_SAMPLERATE
        logger.info("VAD sounddevice: %d bytes, peak=%d (%.0f%%), %.2fs capturado",
                    len(mono_16k) * 2, peak_all, peak_all / 32767 * 100, duration)
        return mono_16k.tobytes()
    except Exception as e:
        logger.warning("sounddevice VAD falló: %s", e)
        return None


def _record_winmm_fixed(duration: float = 5.0) -> tuple[bytes | None, int]:
    """Graba con WinMM (fallback). Retorna (pcm, actual_output_rate). Bug 9: rate real al STT."""
    try:
        import numpy as np
        from jarvis import winmm_capture
        pcm, actual_rate = winmm_capture.record_with_rate(
            duration, samplerate=_MIC_SAMPLERATE, channels=2, bits=16)
        if pcm is None or actual_rate == 0:
            return None, 0
        samples    = np.frombuffer(pcm, dtype='<i2').reshape(-1, 2)
        boosted    = np.clip(samples.astype('int32') * _MIC_BOOST, -32768, 32767).astype('int16')
        downsample = max(1, actual_rate // _STT_SAMPLERATE)
        mono_out   = boosted[::downsample, 0]
        out_rate   = actual_rate // downsample   # tasa real de salida (puede ser 22050 si 44100Hz)
        peak = int(abs(boosted).max())
        logger.info("winmm (%dHz→%dHz, ds=%d): %d bytes, peak=%d (%.0f%%)",
                    actual_rate, out_rate, downsample, len(mono_out) * 2, peak, peak / 32767 * 100)
        return mono_out.tobytes(), out_rate
    except Exception as e:
        logger.warning("winmm falló: %s", e)
        return None, 0


def _google_stt_raw(pcm: bytes, rate: int = _STT_SAMPLERATE, language: str = "es-CL") -> str:
    """Llama a Google Speech API directamente con PCM raw.
    rate: tasa real del audio (puede diferir de _STT_SAMPLERATE si winmm cayó a 44100Hz).
    """
    url = "https://www.google.com/speech-api/v2/recognize"
    params = {
        "client": "chromium",
        "lang":   language,
        "key":    "AIzaSyBOti4mM-6x9WDnZIjIeyEU21OpBXqWBgw",  # clave pública de Chromium
    }
    headers = {"Content-Type": f"audio/l16; rate={rate}"}
    try:
        resp = _requests.post(url, params=params, headers=headers,
                              data=pcm, timeout=10)
        if resp.status_code != 200:
            logger.warning("Google STT HTTP %d", resp.status_code)
            return ""
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


def listen() -> str:
    """Escucha con VAD y transcribe. Usa faster-whisper primero, fallback a Google STT."""
    try:
        device      = _find_mic_device()
        pcm_bytes   = _record_sounddevice_vad(device) if device is not None else None
        actual_rate = _STT_SAMPLERATE  # sounddevice VAD siempre produce 16kHz

        if pcm_bytes is None:
            logger.info("sounddevice VAD falló — usando winmm_capture (fijo 5s)")
            pcm_bytes, actual_rate = _record_winmm_fixed(5.0)

        if pcm_bytes is None:
            logger.error("No se pudo capturar audio")
            return ""

        try:
            from jarvis import stt
            return stt.transcribe(pcm_bytes, samplerate=actual_rate)
        except Exception as e:
            logger.warning("faster-whisper falló (%s) — usando Google STT", e)
            return _google_stt_raw(pcm_bytes, rate=actual_rate)

    except Exception as e:
        import traceback as _tb
        logger.error("listen() error: %s\n%s", e, _tb.format_exc())
        return ""


def play_startup():
    """Reproduce el sonido de arranque si el archivo existe."""
    if STARTUP_SOUND.exists():
        try:
            _tts_cancel.clear()  # Bug 13: asegurar que cancel no bloquee el startup sound
            _play_audio(str(STARTUP_SOUND))
        except Exception as e:
            logger.debug(f"Startup sound error: {e}")
