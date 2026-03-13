# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Automation platform for **Egakat SPA** (Chilean 3PL logistics company). Scripts download reports from WMS Egakat via browser automation (Playwright), process data, and sync to OneDrive. A secondary layer of Claude-powered AI agents enables analysis and code generation.

**Python command**: always `py` and `py -m pip`
**Working directory**: `C:\ClaudeWork\`

## Running Scripts

```bash
# Orchestrator (runs all WMS modules in sequence)
py WMS_Automatizacion\run_todos.py

# Individual modules
py WMS_Automatizacion\wms_descarga.py
py WMS_Automatizacion\staging_descarga.py
py WMS_Automatizacion\vdr_comparador.py
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
- **WMS_Automatizacion/**: Modules 1-3, 6-8 — WMS queries to OneDrive, orchestrated by `run_todos.py`
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

## Security
- `.claudeignore` excludes `.env`, `logs/`, `Solicitudes_IT/`, `_debug_historico/`
- `.gitignore` rule: code goes up, data (xlsx, csv, pdf) does NOT
- Exception: `AI_Agent/Guia_AI_Agent_Egakat.docx` is allowed in GitHub
- Credentials: always from `.env`, never hardcoded
