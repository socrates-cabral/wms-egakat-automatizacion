# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Automation platform for **Egakat SPA** (Chilean 3PL logistics company). Scripts download reports from WMS Egakat via browser automation (Playwright), process data, and sync to OneDrive. A secondary layer of Claude-powered AI agents enables analysis and code generation.

**Python command**: always `py` and `py -m pip`
**Working directory**: `C:\ClaudeWork\`

1. Think before acting. Read existing files before writing code.
2. Be concise in output but thorough in reasoning.
3. Prefer editing over rewriting whole files.
4. Do not re-read files you have already read unless the file may have changed.
5. Test your code before declaring done.
6. No sycophantic openers or closing fluff.
7. Keep solutions simple and direct.
8. User instructions always override this file.

## Running Scripts

```bash
# Orchestrator (runs all WMS modules in sequence)
py WMS_Automatizacion\run_todos.py

# Individual modules
py WMS_Automatizacion\wms_descarga.py
py WMS_Automatizacion\staging_descarga.py
py VDR_Comparador\vdr_comparador.py
py NPS_Encuesta\nps_descarga.py

# AI Agent CLI
py AI_Agent\ask_ai.py "pregunta"
# or from any folder:
ask_ai "pregunta"
```

## Architecture

### Data Flow
```
WMS Egakat (Web) → Playwright automation → OneDrive local sync → SharePoint Online → Power Automate trigger → Email notification
```

### Module Layout
- **WMS_Automatizacion/**: Modules 1-3, 6-8, 9 — WMS queries to OneDrive, orchestrated by `run_todos.py`; Module 9 = Validación Post-Ejecución (`validator_agent.py`)
- **VDR_Comparador/**: Module 4 — SAP vs. Physical inventory comparison (runs hourly)
- **NPS_Encuesta/**: Module 5 — NPS/CSAT download from LimeSurvey (monthly/quarterly)
- **AI_Agent/**: Claude-powered agents; `ask_ai.py` is the CLI entry point
- **Root `run_todos.py` / `vdr_comparador.py`**: Bridge scripts — Task Scheduler calls these, they redirect to the actual implementations in subfolders

### AI Agent Layers
| Layer | Tool | Role |
|-------|------|------|
| 0 | Claude.ai (browser) | Design — no code access |
| 1 | Claude Code (VS Code) | Orchestration |
| 2 | `AI_Agent/agentes/*.py` | Specialized execution (extractor, m365, analista, generador, power_bi) |
| 3 | `ask_ai` (terminal) | Quick queries |

## Code Conventions

### Mandatory header for every script
```python
import sys
sys.stdout.reconfigure(encoding="utf-8")
```

### .env loading
`.env` lives at repo root. Scripts in subfolders load it with:
```python
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")
```

### OneDrive destination
All output goes to OneDrive — never to `C:\ClaudeWork\Reportes\` or local folders.
```python
ONEDRIVE_BASE = Path(os.getenv("ONEDRIVE_PATH"))
```

### Playwright (headless only)
```python
browser = p.chromium.launch(headless=True)
```
Timeouts: 60 000 ms default, 180 000 ms for downloads. Use progressive retry (staging_descarga v2.5 pattern: 3 attempts with 60s/120s/180s).

### WMS failed report detection (staging_descarga v2.5+)
When WMS fails silently it returns `SCABRAL{timestamp}.csv` (no report prefix) with 0 bytes. Detection:
```python
re.match(r'^SCABRAL\d+\.csv$', nombre_archivo, re.IGNORECASE)
```
On detection: retry the full SEARCHBUTTON click. After 3 failed attempts: delete the file — empty = no stock for that client.

### Logging
Each script writes to `C:\ClaudeWork\logs\<scriptname>_YYYY-MM-DD_HHMMSS.log`. Log failures with `[FALLO]` prefix — `run_todos.py` scans for this marker to trigger email alerts.

### Email alerts (SMTP Office 365)
Use `smtp.office365.com:587` with credentials `SHAREPOINT_USER` / `SHAREPOINT_PASSWORD` from `.env`.

### pandas
Use `errors="coerce"` — `errors="ignore"` was removed in pandas 3.0.

### Module filenames (Modules 2 & 3)
**Do not rename** output files — Power Query references exact names.

## Environment Variables (key ones)
| Variable | Purpose |
|----------|---------|
| `WMS_PASSWORD` | WMS Egakat login |
| `SHAREPOINT_USER` / `SHAREPOINT_PASSWORD` | OneDrive + SMTP auth |
| `ONEDRIVE_PATH` | Base path for all OneDrive output |
| `ANTHROPIC_API_KEY` | Claude API (AI_Agent) |
| `LIMESURVEY_USER/PASSWORD/SURVEY_ID_*` | NPS module |

## Scheduled Tasks (do not break compatibility)
| Task | Script | Schedule |
|------|--------|----------|
| WMS Egakat - Descarga diaria | `run_todos.py` | Mon–Fri 8:00 AM |
| WMS Egakat - Watchdog Alerta | `wms_watchdog.py` | Mon–Fri 9:30 AM |
| VDR Comparador - EGA KAT | `vdr_comparador.py` | Every hour Mon–Fri 8–19 |
| NPS tasks (3) | `nps_descarga.py` | Monthly / quarterly |
| Maestro Artículos DERCO | `WMS_Automatizacion\ejecutar_maestro_silencioso.vbs` | Mon–Fri 9:00 AM |
| Agente Apuestas - Analisis Diario | `agente_apuestas\run_agent.py` | Daily 09:00 |
| Agente Apuestas - Backtesting Nocturno | `agente_apuestas\backtesting\run_backtesting.py` | Daily 23:00, WakeToRun=True |

## Security
- `.claudeignore` excludes `.env`, `logs/`, `Solicitudes_IT/`, `_debug_historico/`
- `.gitignore` rule: code goes up, data (xlsx, csv, pdf) does NOT
- Exception: `AI_Agent/Guia_AI_Agent_Egakat.docx` is allowed in GitHub
- Credentials: always from `.env`, never hardcoded

## Reference Architecture: kuberwastaken/claude-code
Repo con código fuente filtrado de Claude Code (Anthropic) — analizado 2026-03-31, LIMPIO sin malware.

### Patrones extraídos e implementados
| Patrón | Aplicado en | Detalle |
|--------|-------------|---------|
| Timeouts en API IA | `HackeaMetabolismo/src/alimentacion/vision_ia.py` | 30s Anthropic/OpenAI |
| Timeouts en API IA | `HackeaMetabolismo/src/alimentacion/recetas_ia.py` | 45s Anthropic |
| Retry con backoff exponencial | `vision_ia.py:_con_retry()` | 2 reintentos, 2s/4s, antes de cambiar proveedor |
| Sanitización input usuario | `HackeaMetabolismo/dashboard/pages/03_Registro.py` | strip + 120 chars + validación campos vacíos |

### Pendiente de explorar (spec/)
- `spec/11_special_systems.md` — memdir: memoria markdown+YAML con relevance scoring → mejorar sistema memory actual
- `spec/09_bridge_cli_remote.md` — Bridge JWT+WebSocket para agentes remotos → Paperclip
- `spec/01_core_entry_query.md` — Query loop + token budget → mejorar AI_Agent/

## Git Worktree Workflow (Multi-Task Development)

Use Git Worktree para trabajar en múltiples tareas en paralelo:

```bash
# Iniciar tareas paralelas
/worktree-init tarea1 | tarea2 | tarea3

# Cada worktree en panel separado (Ghostty)
# Terminal izq: /worktree-check
# Terminal derecha: editar código
# Otra terminal: tests/logs

# Entregar PR cuando la tarea esté completa
/worktree-deliver

# Limpiar worktrees y ramas mergeadas
/worktree-cleanup --all
```

**Ventaja:** Múltiples branches activos simultáneamente sin cambiar branch. Cada worktree aislado con su `.env` y node_modules.

## MCP Server Configuration

### SQLite Integration
```bash
claude mcp add sqlite -- npx -y @modelcontextprotocol/server-sqlite --db-path C:\ClaudeWork\finanzas.db
```

Otros MCP servers útiles:
- **n8n-mcp** — Orquestación workflows (instalado, ver `reference_n8n_mcp.md`)
- **SQLite** — Acceso directo a bases de datos
- **Webfetch / WebSearch** — APIs externas

### Configuración Actual
Ver `~/.claude/settings.json`:
- n8n-mcp: Activo (N8N_API_KEY, http://localhost:5678)
- Modelo default: Haiku 4.5

---

## Multi-Agent Orchestration

### Habilitar Agent Teams (una sola vez)
Agregar a `~/.claude/settings.json`:
```json
{
  "env": {
    "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"
  }
}
```

---

### PR Review: `/review-pr`

**Archivo:** `.claude/commands/review-pr.md`
**Uso:** Escribe `/review-pr` en Claude Code para lanzar 4 sub-agentes en paralelo.

| Agente | Foco | Verifica |
|--------|------|----------|
| `@automation` | Playwright, WMS, reintentos | headless, timeouts 60s/180s, retry backoff 3 intentos, SCABRAL detection |
| `@security` | Credenciales, rutas, git | sin hardcode, output → OneDrive, pandas 3.0 compat, Graph API tokens |
| `@data` | Transformaciones pandas | encoding, errors="coerce", nombres fijos Mód. 2-3, DataFrames vacíos |
| `@ai-integration` | Anthropic API, fallback LLM | modelo Haiku, max_tokens explícito, cadena Claude→OpenAI→Gemini→template |

**Output esperado:**
```
## Revisión PR — [título]
Agentes: automation ✅ | security ✅ | data ⚠ | ai-integration ✅

### 🚨 Bloqueantes
### ⚠ Mejoras recomendadas
### ✅ Correctos
### Veredicto: [APROBADO / APROBADO CON CONDICIONES / RECHAZADO]
```

---

### Agente Apuestas: `/run-apuestas`

**Archivo:** `.claude/commands/run-apuestas.md`
**Uso:** Escribe `/run-apuestas` para orquestar el pipeline de predicción en paralelo.

**Arquitectura:**
```
Orquestador
    ├── @scraper-futbol   → Serie A + La Liga + UCL + Bundesliga (paralelo)
    ├── @scraper-lesiones → /injuries endpoint api-sports por partido (paralelo, ~6 req/día)
    ├── @scraper-otros    → NBA + Tenis (cuando Sprint 17-18 estén activos)
    └── [merge — espera todos los scrapers]
         ├── predictor_tiempo_real.py → XGBoost (secuencial)
         ├── @narrativa   → analizar_con_claude() por partido (paralelo)
         └── telegram_bot.py → Telegram (secuencial, último paso)
```

**Reglas de integridad para todos los agentes:**
- `historico_apuestas.json` es fuente de verdad — nunca borrar entradas, solo actualizar nulls
- Logs en `C:\ClaudeWork\logs\agente_apuestas_YYYY-MM-DD_HHMMSS.log`
- `MODO_PAPER_TRADING = True` hasta ROI ≥ 20% sostenido en n ≥ 20 apuestas
- `MAX_REQUESTS_DAILY = 90` compartido entre agentes (buffer de 10 de los 100 gratuitos)
- Si un scraper falla → orquestador continúa con datos disponibles (no cancela todo)
- Telegram: prefijo `[PAPER]` cuando `MODO_PAPER_TRADING = True`

**Distribución de requests entre agentes paralelos:**
```python
# Límite compartido: 90 req/día total
# @scraper-futbol  → máx 50 req
# @scraper-lesiones→ máx  6 req (1 por partido analizado)
# @scraper-otros   → máx 30 req
# @narrativa       → 0 req api-sports (usa LLMs)
```

**Ligas activas (Serie A únicamente, umbral=0.70, value=0.10):**
- La Liga y Bundesliga: suspendidas hasta n ≥ 20 con ROI > 0
- UCL: monitoreando, no activar aún (pocas temporadas)

---

## LLM Wiki (patrón Karpathy)

Implementación del patrón de bases de conocimiento LLM de Andrej Karpathy (abril 2026).
El conocimiento se compila una vez y se mantiene, en vez de re-derivarse en cada consulta.

### Estructura de carpetas
```
C:\ClaudeWork\
├── raw\                     fuentes originales, inmutables (NUNCA editar)
│   ├── papers\              papers ML, documentos técnicos
│   ├── reportes\            reportes WMS, logs relevantes
│   └── docs_iso\            documentos ISO 9001 / 45001
├── wiki\                    conocimiento compilado por el LLM
│   ├── index.md             catálogo maestro (actualizar en cada ingest)
│   ├── log.md               registro cronológico append-only
│   ├── conceptos\           Pi-Rating, xG, Kelly, Value Betting, KPIs WMS
│   ├── decisiones\          por qué XGBoost, por qué Graph API, etc.
│   ├── proyectos\           estado WMS, Agente Apuestas, Chiquito, etc.
│   └── entidades\           api-sports, Understat, Egakat, Betano, etc.
└── CLAUDE.md                este archivo (schema)
```

### Reglas del wiki
1. `raw/` es inmutable — el LLM lee pero NUNCA escribe ahí
2. `wiki/` es propiedad del LLM — lo crea, actualiza y mantiene
3. **Todo proyecto nuevo → página wiki obligatoria** antes de cerrar la sesión en que se creó
4. **Toda actualización significativa de proyecto → actualizar su página wiki** (sprint nuevo, bug crítico, cambio de arquitectura, nueva tarea programada)
5. **Decisiones técnicas no obvias → `wiki/decisiones/`** (por qué una tecnología, por qué un parámetro, tradeoffs elegidos)
6. **Documentos técnicos, papers, configs importantes → copiar a `raw/`** y hacer ingest al wiki
7. Cada página wiki tiene frontmatter YAML:
```yaml
---
title: Nombre de la página
type: concepto | entidad | decision | proyecto | fuente
sources: [lista de archivos raw/ referenciados]
related: [lista de páginas wiki relacionadas]
updated: YYYY-MM-DD
confidence: high | medium | low
---
```
4. `wiki/log.md` es append-only — formato: `## [YYYY-MM-DD] ingest|query|lint | Título`
5. `wiki/index.md` se actualiza en cada ingest con link + resumen de 1 línea

### Operaciones

**Ingest** → "Ingest raw/[archivo]"
1. Leer el archivo fuente
2. Crear/actualizar página en `wiki/sources/` o categoría correspondiente
3. Actualizar páginas de conceptos y entidades relacionadas
4. Actualizar `wiki/index.md`
5. Agregar entrada a `wiki/log.md`

**Query** → hacer preguntas contra el wiki
1. Leer `wiki/index.md` para identificar páginas relevantes
2. Leer esas páginas
3. Sintetizar respuesta con referencias `[[wiki-link]]`
4. Si la respuesta es valiosa → archivarla como nueva página en `wiki/`

**Lint** → "Lint the wiki" (ejecutar periódicamente)
1. Detectar contradicciones entre páginas
2. Encontrar páginas huérfanas (sin links entrantes)
3. Identificar conceptos mencionados sin página propia
4. Sugerir preguntas a investigar

### Wiki vs MEMORY.md
| MEMORY.md | wiki/ |
|-----------|-------|
| Estado actual del proyecto | Conocimiento compilado y enlazado |
| Actualización manual frecuente | Actualización por el LLM al ingestir |
| Formato libre | Frontmatter YAML estructurado |
| Una sola sección por proyecto | Páginas granulares por concepto/entidad |

Ambos coexisten: MEMORY.md sigue siendo la fuente de verdad del estado operacional.
wiki/ es la base de conocimiento acumulada para consultas y síntesis.
