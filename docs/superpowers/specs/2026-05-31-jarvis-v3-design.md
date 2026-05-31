# Jarvis v3 — Wake Word + STT Local
**Fecha:** 2026-05-31
**Autor:** Sócrates Cabral + Claude Sonnet 4.6
**Estado:** Aprobado para implementación

---

## Contexto

Jarvis v2.0 (tagueado 2026-05-31) funciona correctamente pero requiere Win+J para activarse. El principal punto de fricción es la dependencia del teclado. Adicionalmente, el STT usa una key pública de Chromium que puede romperse sin aviso.

v3 resuelve ambos problemas de forma ortogonal sin tocar `agent.py`, `overlay.py` ni `tools.py`.

---

## Objetivos

1. **Wake word "Hey Jarvis"** — activación manos libres, funciona en escritorio y moviéndose
2. **Win+J como fallback** — se mantiene sin cambios
3. **STT local offline** — reemplazar Google STT (key Chromium) con faster-whisper
4. **Degradación graceful** — si Porcupine falla, Win+J sigue; si faster-whisper falla, Google STT como backup

---

## Arquitectura

```
[Porcupine thread — siempre activo]    [Win+J — sin cambio]
   sounddevice stream 16kHz / 512 samp/frame    WM_HOTKEY
   Porcupine.process(frame) → keyword_index >= 0
              ↓                                       ↓
         harness.trigger()  ←──────────────────────┘
              ↓
   [VAD chunk-based — sin cambio]
   speech frames (int16 bytes) → stt.transcribe()   ← NUEVO
              ↓
   Gemini AFC → edge-tts → pill overlay              ← sin cambio
```

### Archivos nuevos

| Archivo | Responsabilidad |
|---------|-----------------|
| `jarvis/wakeword.py` | WakeWordDetector: Porcupine en thread daemon, llama callback al detectar |
| `jarvis/stt.py` | faster-whisper: modelo cargado lazy una vez, transcribe PCM int16 bytes |

### Archivos modificados

| Archivo | Cambio |
|---------|--------|
| `jarvis/voice.py` | `listen()` llama `stt.transcribe()` en vez de `_google_stt_raw()`. Google STT se mantiene como fallback si faster-whisper falla. |
| `jarvis/ui/harness.py` | `start()` instancia y arranca `WakeWordDetector`. `stop_wakeword()` para al salir. |
| `jarvis/config.py` | Agrega `PORCUPINE_ACCESS_KEY`, `WAKE_WORD_PATH`, `WAKE_WORD_SENSITIVITY`, `STT_MODEL`. |
| `jarvis/requirements.txt` | Agrega `pvporcupine>=3.0`, `faster-whisper>=1.0`. |
| `jarvis/main.py` | Conecta `app.aboutToQuit` → `harness.stop_wakeword()`. |

---

## Sección 1: Wake Word — `jarvis/wakeword.py`

### Tecnología: Porcupine (pvporcupine)

- **CPU**: ~1-2% constante (el menor del mercado)
- **Accuracy**: ~3% false negative, ~0.5% false positive
- **Formato requerido**: 16kHz, mono, int16, exactamente 512 samples/frame (32ms)
- **Keyword file**: `jarvis/jarvis_windows.ppn` — descargado de Picovoice Console (gratis)

### Diseño de clase

```python
class WakeWordDetector:
    def __init__(self, callback: Callable)
    def start(access_key: str, keyword_path: str, sensitivity: float = 0.5) -> bool
    def stop() -> None
    def _loop() -> None   # thread daemon: stream → Porcupine.process() → callback
```

### Flujo interno de `_loop()`

1. Abrir `sounddevice.InputStream(samplerate=16000, channels=1, dtype='int16', blocksize=512)`
2. En cada frame: `idx = porcupine.process(frame[:, 0].tolist())`
3. Si `idx >= 0`: log + llamar `self._callback()` (= `harness.trigger`)
4. `stop_event.is_set()` → salir limpiamente, `porcupine.delete()`

### Manejo de errores

- `pvporcupine` no instalado → `ImportError` atrapado, `start()` retorna `False`
- `AccessKey` inválida → excepción en `create()`, log warning, `start()` retorna `False`
- `.ppn` no encontrado → `FileNotFoundError`, log warning, `start()` retorna `False`
- Error en stream durante `_loop()` → log error, thread termina (Win+J sigue operativo)

### Conflict con VAD recorder

Porcupine y el VAD de sounddevice usan el mismo micrófono. **No es un conflicto**: Porcupine usa un `InputStream` continuo a 16kHz/512 samples. Cuando `harness.trigger()` se dispara, `WakeWordDetector` mantiene su stream abierto (solo escucha, no bloquea). El VAD en `_record_sounddevice_vad()` abre su propio stream con `sd.rec()` — en Windows, sounddevice comparte el dispositivo entre múltiples lectores en modo WASAPI Shared.

Si hubiera conflicto (WASAPI Exclusive), `WakeWordDetector._loop()` atrapa la excepción y loguea.

---

## Sección 2: STT local — `jarvis/stt.py`

### Tecnología: faster-whisper

- **Modelo**: `small` (~244MB, descarga automática en primer uso desde HuggingFace)
- **CPU**: ~1s para 5s de audio en CPU moderno
- **Idioma**: forzado a `"es"` (español, detecta CL naturalmente)
- **VAD interno**: `vad_filter=True` elimina silencio antes de transcribir
- **Carga**: lazy en primera llamada, cacheado en `_model` global

### API pública

```python
def transcribe(pcm_int16: bytes, samplerate: int = 16000) -> str
    """Convierte PCM int16 bytes a texto. Retorna '' si no hay habla o error."""
```

### Internamente

```
pcm_int16 bytes
  → np.frombuffer(dtype='<i2') → float32 / 32768.0  (normalizar a [-1, 1])
  → model.transcribe(audio, language="es", beam_size=1, vad_filter=True)
  → concatenar segment.text de todos los segments
  → strip() → return
```

### Primera ejecución

El modelo se descarga automáticamente a `~/.cache/huggingface/hub/`. El usuario no necesita hacer nada, pero la primera llamada tarda ~30-60s (descarga 244MB). Se puede predescargar con `py -c "from faster_whisper import WhisperModel; WhisperModel('small', device='cpu')"`.

---

## Sección 3: Cambios en `voice.py`

### `listen()` — nueva lógica

```
1. VAD sounddevice_vad → pcm bytes  (sin cambio)
2. Si VAD ok → stt.transcribe(pcm)  ← NUEVO (faster-whisper)
3. Si stt falla (ImportError/excepción) → fallback: _google_stt_raw(pcm)  ← mantener
4. Si VAD falla → winmm_fixed → stt.transcribe  (sin cambio en captura)
```

### Eliminar

- `_google_stt_raw()` pasa a ser función privada de fallback, no eliminar — solo dejar de llamar por defecto.

---

## Sección 4: Config — `jarvis/config.py`

```python
# Wake word
PORCUPINE_ACCESS_KEY  = os.getenv("PORCUPINE_ACCESS_KEY", "")
WAKE_WORD_PATH        = BASE_DIR / "jarvis" / "jarvis_windows.ppn"
WAKE_WORD_SENSITIVITY = 0.5   # 0.0 (menos sensible) – 1.0 (más sensible)

# STT local
STT_MODEL    = "small"   # faster-whisper: tiny | base | small | medium
STT_LANGUAGE = "es"
```

---

## Sección 5: Cambios en `harness.py`

### `start()` — agregar al final

```python
from jarvis.wakeword import WakeWordDetector
from jarvis.config import PORCUPINE_ACCESS_KEY, WAKE_WORD_PATH, WAKE_WORD_SENSITIVITY

self._wakeword = WakeWordDetector(callback=self.trigger)
if PORCUPINE_ACCESS_KEY and WAKE_WORD_PATH.exists():
    ok = self._wakeword.start(str(PORCUPINE_ACCESS_KEY),
                               str(WAKE_WORD_PATH), WAKE_WORD_SENSITIVITY)
    if ok:
        logger.info("Wake word 'Hey Jarvis' activo.")
    else:
        logger.warning("Wake word no pudo iniciar — solo Win+J disponible.")
else:
    logger.warning("Wake word desactivado: falta PORCUPINE_ACCESS_KEY o jarvis_windows.ppn")
```

### Agregar `stop_wakeword()`

```python
def stop_wakeword(self) -> None:
    if hasattr(self, "_wakeword"):
        self._wakeword.stop()
```

---

## Sección 6: Cambios en `main.py`

```python
app.aboutToQuit.connect(harness.stop_wakeword)
```

---

## Setup manual (una sola vez)

1. `py -m pip install pvporcupine faster-whisper`
2. Registrarse en https://console.picovoice.ai (gratis, sin tarjeta)
3. Crear AccessKey en el dashboard
4. Ir a Porcupine → Downloads → buscar "jarvis" → descargar `jarvis_windows.ppn`
5. Copiar a `C:\ClaudeWork\jarvis\jarvis_windows.ppn`
6. Agregar al `.env` raíz: `PORCUPINE_ACCESS_KEY=tu_key`
7. Predescargar modelo STT: `py -c "from faster_whisper import WhisperModel; WhisperModel('small', device='cpu', compute_type='int8')"`

---

## Archivos que NO cambian

- `agent.py` — sin tocar
- `ui/overlay.py` — sin tocar
- `ui/bridge.py` — sin tocar
- `ui/animations.py` — sin tocar
- `tools.py` — sin tocar

---

## Testing

| Test | Criterio |
|------|----------|
| Wake word sin config | Jarvis arranca, log warning, Win+J funciona |
| Wake word con config | Decir "Hey Jarvis" → pill aparece → STT transcribe → Gemini responde |
| Win+J con v3 | Funciona igual que v2 |
| STT faster-whisper | `stt.transcribe(pcm)` devuelve texto en español |
| STT fallback | Si faster-whisper falla, Google STT responde |
| Cierre limpio | `app.aboutToQuit` → `stop_wakeword()` → Porcupine se libera |

---

## No incluido en v3

- Wake word personalizado (más allá de "jarvis" de Picovoice)
- Gmail / Calendar tools
- Streaming TTS
- Multi-room / múltiples micrófonos
