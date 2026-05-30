# J.A.R.V.I.S. UI v2 — Overlay Harness

**Fecha:** 2026-05-29  
**Proyecto:** `C:\ClaudeWork\jarvis\`  
**Stack actual:** Python 3.14, Gemini 2.0 Flash, edge-tts, sounddevice, keyboard

---

## Objetivo

La UI de Jarvis no es una capa decorativa: **es el harness**. Orquesta el ciclo completo (STT → agente → tools → TTS), mantiene memoria persistente conectada al sistema de memory de Claude Code, muestra en tiempo real qué tool está ejecutando, y puede invocar tareas de Kai (Claude Code) mostrando su progreso.

---

## Decisiones de Diseño

| Pregunta | Decisión |
|----------|----------|
| Tipo de UI | Overlay activable (invisible en reposo) |
| Posición | Barra pill inferior centrada (bottom-center) |
| Modo respuesta | Pill expandida con texto typewriter + waveform |
| Stack UI | PyQt6 |
| Rol | **Harness orquestador** — no solo display |

---

## Arquitectura

```
jarvis/
├── main.py               ← Entry point: crea QApplication + inicia UI harness
├── agent.py              ← Gemini agent (sin cambios)
├── voice.py              ← STT/TTS + voice.stop() para interrumpir
├── config.py             ← sin cambios
├── tools.py              ← 7 tools existentes (sin cambios)
└── ui/
    ├── __init__.py
    ├── harness.py        ← JarvisHarness: orquestador central del ciclo
    ├── overlay.py        ← QWidget pill: visual states + animaciones
    ├── animations.py     ← WaveformWidget, TypewriterLabel, FadeEffect
    ├── bridge.py         ← JarvisBridge(QObject): signals Qt para thread-safety
    └── memory.py         ← MemoryClient: lee/escribe memory/ de Claude Code
```

### Cambio arquitectónico respecto a v1

**Antes (v1):** `main.py` controlaba el ciclo directamente.  
**Ahora (v2):** `JarvisHarness` en `ui/harness.py` es el orquestador. `main.py` solo arranca PyQt.

```
main.py
  └── QApplication + JarvisOverlay
        └── JarvisHarness (QThread)
              ├── MemoryClient.load_context()   ← lee memory/ al iniciar
              ├── voice.listen()
              ├── Agent.process_message()        ← con contexto de memory
              ├── tools ejecutados → bridge.tool_started(name)
              ├── voice.speak()
              └── MemoryClient.persist_session() ← escribe memory/ al cerrar
```

---

## Memoria Persistente — MemoryClient

Jarvis lee y escribe el mismo sistema de memoria que usa Claude Code.

**Directorio:** `C:\Users\Socrates Cabral\.claude\projects\C--ClaudeWork\memory\`

### Al iniciar (load_context)
```python
# Lee MEMORY.md para extraer contexto relevante
# Lee archivos específicos: user_profile.md, crypto_estrategia_bot.md,
#   project_agente_apuestas.md, project_kpi_ops.md
# Construye un "context block" que se inyecta en el system prompt de Gemini
```

El context block actualiza el system prompt de Jarvis con estado real:
- Estado del bot crypto (lee estado_grid.json además del memory)
- KPIs operativos actuales
- Proyectos activos

### Al cerrar / después de conversaciones significativas (persist_session)
```python
# Si Jarvis aprendió algo nuevo → escribe o actualiza archivo en memory/
# Ejemplo: usuario menciona nuevo KPI → actualizar project_kpi_ops.md
# Formato idéntico al que usa Claude Code (frontmatter YAML + body)
```

---

## Estados de la Ventana

### 1. Idle
- Ventana completamente oculta

### 2. Listening
- Pill compacta (320×52px) en bottom-center, fade-in 200ms
- Ícono cyan pulsante + "ESCUCHANDO" + waveform input animada

### 3. Processing (Gemini)
- "PROCESANDO..." + dots animados

### 4. Tool Executing ← **nuevo en v2**
- Pill muestra el nombre del tool activo:
  - `🔍 Consultando Kraken...`
  - `📊 Leyendo WMS KPI...`
  - `⚽ Consultando apuestas...`
  - `🤖 Invocando Kai...` ← Claude Code task
  - `⏱ Timer activo...`
- El bridge recibe `tool_started(tool_name)` / `tool_done(tool_name)` del agente

### 5. Speaking
- Pill expandida (360×120px), fade animado
- Header: ícono + "J.A.R.V.I.S." + waveform output
- Body: texto typewriter ~30 chars/s
- Click en pill → `voice.stop()` + cierra

### 6. Kai Task Running ← **nuevo en v2**
- Cuando `invoke_claude` se ejecuta, el overlay muestra un estado especial:
  - Pill expandida con barra de progreso indeterminada
  - Texto: "Kai ejecutando: [descripción de la tarea]"
  - Resultado de Kai aparece en typewriter cuando termina

### 7. Closing
- Fade-out 300ms → oculto

---

## Bridge de Signals

`JarvisBridge(QObject)` conecta el QThread del harness con el QWidget del overlay:

```python
class JarvisBridge(QObject):
    listening_started  = Signal()
    processing_started = Signal()
    tool_started       = Signal(str)   # nombre del tool
    tool_done          = Signal(str)
    kai_task_started   = Signal(str)   # descripción tarea Kai
    kai_task_done      = Signal(str)   # resultado Kai
    response_ready     = Signal(str)   # texto completo de respuesta
    speaking_done      = Signal()
    memory_updated     = Signal(str)   # qué se escribió en memory/
```

---

## Integración con Gemini Tool Calls

El agente necesita emitir signals cuando ejecuta tools. Se wrappea la ejecución:

```python
# En harness.py — antes de process_message
# Gemini automatic function calling ejecuta tools internamente
# Para capturar cuándo empieza cada tool: monkey-patch o callback wrapper
# en tools.py cada función llama bridge.tool_started() al inicio y bridge.tool_done() al final
```

Cada función en `tools.py` agrega al inicio:
```python
def get_wms_kpi() -> dict:
    _bridge.tool_started.emit("📊 Leyendo WMS KPI...")
    ...
    _bridge.tool_done.emit("📊 WMS KPI")
    return resultado
```

`_bridge` es una instancia singleton importada desde `ui/bridge.py`.

---

## Especificación PyQt6

### Flags de ventana
```python
Qt.WindowType.FramelessWindowHint |
Qt.WindowType.WindowStaysOnTopHint |
Qt.WindowType.Tool
```

### Transparencia
```python
setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
```

### Dimensiones y posición
```python
PILL_WIDTH_COLLAPSED  = 320   # px
PILL_HEIGHT_COLLAPSED = 52    # px
PILL_WIDTH_EXPANDED   = 360   # px
PILL_HEIGHT_EXPANDED  = 120   # px
PILL_MARGIN_BOTTOM    = 48    # px desde borde inferior

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
| Waveform | `#00d4ff` / `#4a9eff` |
| Tool indicator | `#f0a500` (ámbar) |
| Kai indicator | `#a371f7` (violeta) |

---

## Componentes UI

### WaveformWidget
- `QWidget` con `paintEvent` — 7 barras, `QTimer` 60ms
- Modo `input` (cyan) y `output` (azul)

### TypewriterLabel
- `QLabel` con `QTimer` a 33ms (~30 chars/s)
- Emite `finished` signal

### ToolStatusLabel
- `QLabel` con ícono + nombre del tool
- Color ámbar para tools estándar, violeta para Kai

### FadeEffect
- `QGraphicsOpacityEffect` + `QPropertyAnimation`
- Aparecer: 200ms, desaparecer: 300ms

---

## Qué NO cambia

- `voice.py`, `agent.py`, `config.py` — sin modificación
- Hotkey Win+J — sigue funcionando
- Startup sound — sigue funcionando
- Los 7 tools existentes — solo agregan bridge.tool_started/done

---

## Dependencias nuevas

```
PyQt6>=6.6.0
```

Agregar a `jarvis/requirements.txt`.

---

## Testing

1. `py jarvis/main.py` → overlay invisible en reposo, contexto de memory cargado
2. Win+J → pill listening con waveform
3. "¿cómo va el crypto?" → pill muestra "🔍 Consultando Kraken..." durante tool, luego respuesta typewriter
4. "abre Claude Code" → pill muestra estado tool, respuesta
5. TTS termina → pill desaparece
6. Click en pill durante habla → interrumpe con voice.stop()
7. ESC → cierra + persist_session() escribe memory si hubo aprendizaje

---

## Orden de implementación

1. `ui/bridge.py` — signals singleton
2. `ui/memory.py` — MemoryClient (load + persist)
3. `ui/animations.py` — WaveformWidget, TypewriterLabel
4. `ui/overlay.py` — QWidget pill con todos los estados
5. `ui/harness.py` — JarvisHarness QThread, orquestador
6. `tools.py` — agregar bridge.tool_started/done en cada función
7. `main.py` — reemplazar loop por QApplication + harness
