"""Captura de audio via WinMM waveIn (sin PortAudio, sin COM, sin WASAPI).

Por qué: en la combinación Python 3.14 + Qt + gRPC + sounddevice, ningún host
de PortAudio (WASAPI/DirectSound/MME) puede abrir un InputStream — PortAudio
pasa parámetros inválidos a waveInOpen o falla por interferencia de COM.
WinMM es la API clásica de Windows que el kernel mixer siempre acepta.
"""
import ctypes
import ctypes.wintypes as wt
import time
import wave
import logging

logger = logging.getLogger("jarvis.winmm")

_winmm   = ctypes.WinDLL("winmm")
_kernel32 = ctypes.WinDLL("kernel32")

WAVE_FORMAT_PCM  = 1
WAVE_MAPPER      = 0xFFFFFFFF
CALLBACK_NULL    = 0x00000000
WHDR_DONE        = 0x00000001  # flag que WinMM pone en dwFlags cuando el buffer está lleno


class _WAVEFORMATEX(ctypes.Structure):
    _fields_ = [
        ("wFormatTag",      ctypes.c_uint16),
        ("nChannels",       ctypes.c_uint16),
        ("nSamplesPerSec",  ctypes.c_uint32),
        ("nAvgBytesPerSec", ctypes.c_uint32),
        ("nBlockAlign",     ctypes.c_uint16),
        ("wBitsPerSample",  ctypes.c_uint16),
        ("cbSize",          ctypes.c_uint16),
    ]


class _WAVEHDR(ctypes.Structure):
    _fields_ = [
        ("lpData",          ctypes.c_char_p),
        ("dwBufferLength",  ctypes.c_uint32),
        ("dwBytesRecorded", ctypes.c_uint32),
        ("dwUser",          ctypes.c_ulong),
        ("dwFlags",         ctypes.c_uint32),
        ("dwLoops",         ctypes.c_uint32),
        ("lpNext",          ctypes.c_void_p),
        ("reserved",        ctypes.c_ulong),
    ]


_MMSYSERR_NAMES = {
    0:  "MMSYSERR_NOERROR",
    2:  "MMSYSERR_BADDEVICEID",
    4:  "MMSYSERR_ALLOCATED (device in use)",
    7:  "MMSYSERR_NOMEM",
    10: "MMSYSERR_INVALFLAG",
    11: "MMSYSERR_INVALPARAM (invalid format?)",
    32: "WAVERR_BADFORMAT (unsupported format)",
    33: "WAVERR_STILLPLAYING",
}


def record(duration: float, samplerate: int = 16000,
           channels: int = 1, bits: int = 16) -> bytes | None:
    """Graba `duration` segundos y retorna los PCM bytes, o None si falla."""
    pcm, _ = record_with_rate(duration, samplerate, channels, bits)
    return pcm


def record_with_rate(duration: float, samplerate: int = 16000,
                     channels: int = 1, bits: int = 16) -> tuple[bytes | None, int]:
    """Como record() pero retorna (pcm, actual_samplerate) — 0 si falló."""
    for rate in _rates_to_try(samplerate):
        result = _record_one(duration, rate, channels, bits)
        if result is not None:
            return result, rate
    return None, 0


def _rates_to_try(preferred: int) -> list[int]:
    candidates = [preferred]
    for alt in (48000, 44100, 16000, 8000):
        if alt not in candidates:
            candidates.append(alt)
    return candidates


def _record_one(duration: float, samplerate: int,
                channels: int, bits: int) -> bytes | None:
    wfx = _WAVEFORMATEX(
        wFormatTag      = WAVE_FORMAT_PCM,
        nChannels       = channels,
        nSamplesPerSec  = samplerate,
        wBitsPerSample  = bits,
        nBlockAlign     = channels * bits // 8,
        nAvgBytesPerSec = samplerate * channels * bits // 8,
        cbSize          = 0,
    )

    hwi = wt.HANDLE()
    ret = _winmm.waveInOpen(
        ctypes.byref(hwi), WAVE_MAPPER,
        ctypes.byref(wfx),
        0, 0, CALLBACK_NULL,   # sin event: esperamos con time.sleep + WHDR_DONE
    )
    if ret != 0:
        name = _MMSYSERR_NAMES.get(ret, str(ret))
        logger.debug("waveInOpen %dHz → %s (%d)", samplerate, name, ret)
        if ret == 32:   # WAVERR_BADFORMAT → próxima rate
            return None
        if ret == 4:    # MMSYSERR_ALLOCATED → device ocupado
            logger.error("waveInOpen: device ocupado (exclusivo por otro proceso)")
            return None
        return None

    buf_size = int(duration * samplerate * channels * bits // 8)
    buf = ctypes.create_string_buffer(buf_size)

    hdr = _WAVEHDR()
    hdr.lpData         = ctypes.cast(buf, ctypes.c_char_p)
    hdr.dwBufferLength = ctypes.c_uint32(buf_size)
    hdr.dwFlags        = ctypes.c_uint32(0)

    _winmm.waveInPrepareHeader(hwi, ctypes.byref(hdr), ctypes.sizeof(_WAVEHDR))
    _winmm.waveInAddBuffer(hwi, ctypes.byref(hdr), ctypes.sizeof(_WAVEHDR))
    _winmm.waveInStart(hwi)

    # Esperar a que WinMM llene el buffer (WHDR_DONE) sin usar eventos.
    # CALLBACK_EVENT dispara también en WIM_OPEN (inmediato) — por eso 0 bytes antes.
    deadline = time.monotonic() + duration + 2.0   # 2s de gracia
    while time.monotonic() < deadline:
        if hdr.dwFlags & WHDR_DONE:
            break
        time.sleep(0.05)

    _winmm.waveInStop(hwi)
    _winmm.waveInReset(hwi)
    _winmm.waveInUnprepareHeader(hwi, ctypes.byref(hdr), ctypes.sizeof(_WAVEHDR))
    _winmm.waveInClose(hwi)

    recorded = int(hdr.dwBytesRecorded)
    if not (hdr.dwFlags & WHDR_DONE) or recorded == 0:
        logger.warning("waveInOpen %dHz: buffer vacio tras timeout — retornando None", samplerate)
        return None
    logger.info("waveInOpen %dHz OK — %d bytes grabados (%.2fs)",
                samplerate, recorded, recorded / (samplerate * channels * bits // 8))
    return bytes(buf[:recorded])


def write_wav(pcm: bytes, path: str,
              samplerate: int = 16000, channels: int = 1, bits: int = 16) -> None:
    with wave.open(path, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(bits // 8)
        wf.setframerate(samplerate)
        wf.writeframes(pcm)
