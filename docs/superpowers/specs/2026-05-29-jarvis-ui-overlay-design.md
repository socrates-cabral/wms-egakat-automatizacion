# J.A.R.V.I.S. UI v2 — Overlay Pill

**Fecha:** 2026-05-29  
**Proyecto:** `C:\ClaudeWork\jarvis\`  
**Stack actual:** Python 3.14, Gemini 2.0 Flash, edge-tts, sounddevice, keyboard

---

## Objetivo

Agregar una interfaz visual dark al asistente de voz Jarvis: una pill flotante invisible en reposo que aparece al activarse con Win+J, muestra el estado de la conversación con texto en tiempo real, y desaparece al terminar.

---

## Decisiones de Diseño

| Pregunta | Decisión |
|----------|----------|
| Tipo de UI | Overlay activable (invisible en reposo) |
| Posición | Barra pill inferior centrada (bottom-center) |
| Modo respuesta | Pill se expande con texto typewriter + waveform |
| Stack UI | PyQt6 |

---

## Estados de la Ventana

### 1. Idle (default)
- Ventana completamente oculta — zero footprint visual
- El proceso corre en background esperando Win+J

### 2. Listening
- Pill aparece en bottom-center con fade-in (200ms)
- Contenido: ícono circular cyan pulsante + "ESCUCHANDO" + waveform animada del input de micrófono
- Tamaño: ~320×52px (compacta)

### 3. Processing
- Pill muestra tres puntos animados (ellipsis) mientras Gemini procesa
- Texto: "PROCESANDO..."

### 4. Speaking
- Pill se expande verticalmente (animación 200ms)
- Header: ícono + "J.A.R.V.I.S." + waveform de output de audio
- Body: texto de respuesta aparece en efecto typewriter (~30 chars/s)
- Tamaño expandido: 360×120px
- Click en la pill → llama `voice.stop()` (mata subprocess de playsound) + cierra overlay

### 5. Closing
- Fade-out (300ms) → ventana oculta de nuevo

---

## Arquitectura

```
jarvis/
├── main.py               ← entry point (no cambia la lógica)
├── agent.py              ← Gemini agent (sin cambios)
├── voice.py              ← STT/TTS (sin cambios)
├── config.py             ← sin cambios
└── ui/
    ├── __init__.py
    ├── overlay.py        ← QWidget principal: pill, estados, layout
    ├── animations.py     ← WaveformWidget, TypewriterLabel, FadeEffect
    └── bridge.py         ← JarvisBridge(QObject) con signals Qt para thread-safety
```

### Integración con main.py

`main.py` instancia `QApplication` + `JarvisOverlay` en el hilo principal. La lógica de voz corre en un `QThread` separado. Comunican vía signals:

```python
bridge.listening_started.connect(overlay.show_listening)
bridge.response_ready.connect(overlay.show_speaking)
bridge.speaking_done.connect(overlay.hide_overlay)
```

---

## Especificación PyQt6

### Flags de ventana
```python
Qt.WindowType.FramelessWindowHint |
Qt.WindowType.WindowStaysOnTopHint |
Qt.WindowType.Tool              # no aparece en taskbar
```

### Transparencia
```python
setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
# Fondo del widget root: transparent
# Pill: QFrame con background-color: rgba(10, 15, 26, 0.85)
#        border: 1px solid rgba(0, 212, 255, 0.4)
#        border-radius: 26px (para forma pill)
```

### Dimensiones y posición
```python
PILL_WIDTH_COLLAPSED  = 320   # px — estado listening/processing
PILL_HEIGHT_COLLAPSED = 52    # px
PILL_WIDTH_EXPANDED   = 360   # px — estado speaking
PILL_HEIGHT_EXPANDED  = 120   # px
PILL_MARGIN_BOTTOM    = 48    # px desde borde inferior de pantalla

screen = QApplication.primaryScreen().geometry()
x = (screen.width() - PILL_WIDTH_COLLAPSED) // 2
y = screen.height() - PILL_HEIGHT_COLLAPSED - PILL_MARGIN_BOTTOM
```

### Paleta de colores
| Elemento | Color |
|----------|-------|
| Fondo pill | `rgba(10, 15, 26, 0.85)` |
| Borde | `rgba(0, 212, 255, 0.4)` |
| Cyan accent | `#00d4ff` |
| Texto respuesta | `#e6edf3` |
| Texto estado | `#4a9eff` |
| Waveform barras | `#00d4ff` / `#4a9eff` |

---

## Componentes UI

### WaveformWidget
- `QWidget` custom con `paintEvent`
- 7 barras verticales con alturas aleatorias animadas
- `QTimer` a 60ms → actualiza alturas con interpolación suave
- Dos modos: `input` (verde-cyan) y `output` (azul-cyan)

### TypewriterLabel
- `QLabel` que recibe texto completo y lo muestra carácter a carácter
- `QTimer` a 33ms (~30 chars/s)
- Emite `finished` signal cuando completa

### FadeEffect
- `QGraphicsOpacityEffect` + `QPropertyAnimation`
- `duration=200ms` para aparecer, `300ms` para desaparecer

---

## Qué NO cambia

- `voice.py` — STT/TTS sin modificación
- `agent.py` — Gemini agent sin modificación
- `config.py` — configuración sin modificación
- Hotkey Win+J — sigue funcionando igual
- Startup sound — sigue funcionando igual

---

## Dependencias nuevas

```
PyQt6>=6.6.0
```

Agregar a `jarvis/requirements.txt`.

---

## Testing

1. `py jarvis/main.py` → pill NO aparece en reposo
2. Win+J → pill aparece en bottom-center, waveform animada
3. Hablar → texto aparece en tiempo real al responder
4. TTS termina → pill desaparece con fade
5. Click en pill durante respuesta → interrumpe y cierra
6. ESC → cierra todo (comportamiento actual preservado)
