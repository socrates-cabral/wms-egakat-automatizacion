---
title: Servidor Egakat 24/7 — Migración Automatizaciones
type: proyecto
sources: []
related: [project_wms.md, project_softnet_ventas.md, project_agente_apuestas.md, crypto_estrategia_bot.md]
updated: 2026-04-29
confidence: high
status: planificación
---

# Servidor Egakat 24/7 — Plan de Migración

## Objetivo

Migrar **todas las automatizaciones de producción de Egakat** desde laptop personal a servidor dedicado 24/7, eliminando dependencia de equipo personal y garantizando disponibilidad continua.

**Alcance:** WMS, Softnet Ventas, VDR, NPS, Productividad, FillRate, bots Telegram, APIs Flask, n8n workflows, agente apuestas, crypto bot.

**Fuera de alcance:** Proyectos personales (HackeaMetabolismo, Finanzas, InversionesIA, NutriMetab_BI) permanecen en laptop.

---

## 📦 Inventario de Migración

### ✅ Proyectos → Servidor 24/7 (Egakat)

| Proyecto | Descripción | Task Scheduler | APIs/Servicios | Dependencias Críticas |
|----------|-------------|----------------|-----------------|----------------------|
| **WMS_Automatizacion** | 9 módulos descarga WMS | ✓ (diario 8:00) | api_operaciones.py:5001 | OneDrive sync, Playwright |
| **Softnet_Ventas** | Libro Ventas → SharePoint | ✓ (diario 7:00) | api_cobranza.py:5000 | Graph API, OneDrive |
| **wms_despacho** | Despacho PLTs automático | ✓ (on-demand) | - | Playwright, OneDrive |
| **VDR_Comparador** | SAP vs Stock físico | ✓ (cada hora) | - | Playwright, OneDrive |
| **NPS_Encuesta** | LimeSurvey descarga | ✓ (mensual) | - | Playwright |
| **Productividad_Automatizacion** | 15 clientes FillRate | ✓ (diario 6:30) | - | Graph API, OneDrive |
| **FillRate_Automatizacion** | 13 clientes checkpoint | ✓ (diario 6:45) | - | Graph API, OneDrive |
| **agente_apuestas** | Predicciones ML fútbol | ✓ (diario 9:00 + backtesting 23:00) | - | api-sports, Anthropic, Telegram |
| **crypto_bot** | Grid trading BTC/ETH | ✓ (cada 15 min) | - | Crypto.com API |
| **n8n** | Orquestador workflows | Servicio continuo | localhost:5678 | APIs externas (Tavily, Supabase) |

**Total tareas programadas:** ~15 (Task Scheduler Windows)  
**APIs Flask corriendo:** 2 (puerto 5000, 5001)  
**Servicios continuos:** n8n (Docker)

### ❌ Proyectos → Laptop Personal

- **HackeaMetabolismo** — Dashboard Streamlit, Supabase Auth, puerto 8501
- **finanzas_personales** — Dashboard personal, puerto 8502
- **inversiones_ia** — Dashboard IA inversiones, puerto 8506
- **NutriMetab_BI** — Dashboard clínico, puerto 8503
- **chiquito_financiero** — (archivado, no activo)

---

## 🏗️ Arquitectura del Servidor

### Requisitos Técnicos Mínimos

**Sistema Operativo:** Windows 10/11 Pro (por OneDrive Business sync + Task Scheduler)

**Hardware:**
- **CPU:** 4 cores / 8 threads (Intel i5-12400 / Ryzen 5 5600 o superior)
- **RAM:** 16 GB DDR4 (mínimo 12 GB, recomendado 16 GB)
- **Almacenamiento:** 512 GB NVMe SSD (OneDrive requiere ~200 GB, sistema + logs ~100 GB, margen 200 GB)
- **Red:** Ethernet 1 Gbps (WiFi como respaldo, NO primario)
- **GPU:** Integrada suficiente (no requiere dedicada)

**Software Core:**
- Python 3.12+ (`py` como alias)
- Node.js 20 LTS (para n8n)
- Git 2.44+
- Playwright (navegadores Chromium, Firefox, Webkit)
- OneDrive Business (Microsoft 365 sync)
- Docker Desktop (para n8n, opcional pero recomendado)

**Infraestructura:**
- **UPS** (fuente ininterrumpida) — obligatorio para evitar corrupción Task Scheduler + OneDrive
- **Respaldo de Internet** (móvil 4G/5G como failover) — recomendado
- **Monitoreo remoto** (TeamViewer / AnyDesk / RDP habilitado)

### Dependencias Críticas

1. **OneDrive Business Sync** — BLOCKING
   - Todos los reportes WMS/Softnet → OneDrive → Power Automate → Emails
   - Requiere autenticación Microsoft 365 con cuenta `SHAREPOINT_USER`
   - Sync bidireccional: servidor escribe, Power BI lee desde SharePoint

2. **Task Scheduler** — BLOCKING
   - 15+ tareas programadas (ver tabla arriba)
   - Requiere usuario Windows con password permanente (no PIN, no Windows Hello)
   - Tareas configuradas con "Run whether user is logged on or not"

3. **Flask APIs** — CRITICAL
   - `api_cobranza.py` (puerto 5000) — n8n agent Telegram cobranza
   - `api_operaciones.py` (puerto 5001) — n8n agent Telegram @EgakatOpsBot
   - Requieren `API_COBRANZA_SECRET` y `API_OPS_SECRET` en `.env`

4. **n8n** — CRITICAL
   - Workflows activos: agente cobranza, agente ops (bloqueado), scrapers agente apuestas (futuro)
   - Puerto 5678 (localhost)
   - Requiere `N8N_API_KEY` en `.env`

5. **Playwright** — BLOCKING
   - Navegador headless para WMS, Softnet, VDR, NPS
   - Requiere instalación navegadores: `py -m playwright install chromium`

6. **APIs Externas**
   - **Microsoft Graph API** — Productividad, FillRate, Softnet (tokens en `.env`)
   - **api-sports.io** — Agente apuestas (100 req/día gratis, `API_SPORTS_KEY`)
   - **Anthropic** — Agente apuestas, WMS validator (`ANTHROPIC_API_KEY`)
   - **Crypto.com API** — Crypto bot (`CRYPTO_API_KEY`, `CRYPTO_SECRET_KEY`)
   - **Telegram Bot API** — Bots cobranza, ops, apuestas (`TELEGRAM_BOT_TOKEN_*`)

---

## 💻 Recomendaciones de Hardware

### Opción 1: Mini PC / NUC (⭐ RECOMENDADO para oficina)

**Pros:**
- Bajo consumo eléctrico (~15-65W vs 150-300W PC tower)
- Silencioso (ideal para oficina)
- Compacto (cabe en escritorio, no requiere torre)
- Precio competitivo (~USD 400-700 usado, ~USD 800-1200 nuevo)
- Fácil de montar en pared / debajo escritorio

**Contras:**
- Menos upgradeable (RAM soldada en algunos modelos)
- SSD M.2 limitado a 1-2 slots

**Modelos Recomendados:**

| Modelo | CPU | RAM | SSD | Precio Aprox. | Nota |
|--------|-----|-----|-----|---------------|------|
| **Intel NUC 12 Pro** | i5-1240P | 16 GB | 512 GB | USD 700-900 | Excelente relación precio/rendimiento |
| **Lenovo ThinkCentre M75q Gen 2** | Ryzen 5 Pro 5650GE | 16 GB | 512 GB | USD 500-700 (usado) | Muy confiable, ThinkPad de escritorio |
| **HP EliteDesk 800 G9 Mini** | i5-12500T | 16 GB | 512 GB | USD 650-850 | Enterprise-grade, garantía HP |
| **ASUS PN53** | Ryzen 7 5700U | 16 GB | 512 GB | USD 600-800 | AMD eficiente, bajo ruido |

**Donde comprar en Chile:**
- **PC Factory** — nuevos, garantía local
- **SoloTodo** — comparador precios Chile
- **Mercado Libre** — usados (corporativos lease-return)

### Opción 2: PC Tower Refurbished (💰 Más barato)

**Pros:**
- Muy barato (USD 250-450 usado)
- Upgradeable (RAM, SSD, GPU fácil de cambiar)
- Abundante en mercado de lease-return corporativo
- Componentes estándar (fuente ATX, etc.)

**Contras:**
- Mayor consumo eléctrico (~150W idle, ~250W load)
- Más ruidoso
- Requiere espacio físico (torre)

**Modelos Recomendados:**

| Modelo | CPU | RAM | SSD | Precio Aprox. | Nota |
|--------|-----|-----|-----|---------------|------|
| **Dell OptiPlex 7070** | i5-9500 | 16 GB | 256 GB + HDD | USD 300-400 | Abundante en lease-return |
| **HP ProDesk 600 G5** | i5-9500 | 16 GB | 512 GB | USD 350-450 | Buena construcción |
| **Lenovo ThinkCentre M920** | i5-9500 | 16 GB | 256 GB + HDD | USD 300-400 | ThinkPad calidad |

**Upgrade recomendado:** Agregar SSD NVMe 512 GB (~USD 40-60) si viene con HDD SATA.

### Opción 3: VPS Windows Cloud (☁️ Sin hardware local)

**Pros:**
- Sin mantenimiento físico
- Uptime garantizado (99.9% SLA)
- Conexión estable (datacenter)
- Escalable (upgrade RAM/CPU sin cambiar hardware)
- Respaldo automático (snapshots)

**Contras:**
- **OneDrive sync complejo** — Microsoft recomienda OneDrive solo en PC físico, no VMs (workarounds existen pero no oficiales)
- Costo mensual recurrente (vs inversión única hardware)
- Latencia si datacenter lejos de Chile
- RDP remoto puede ser lento para debugging Playwright

**Proveedores Recomendados:**

| Proveedor | Plan | CPU | RAM | SSD | Precio Mensual | Datacenter |
|-----------|------|-----|-----|-----|----------------|------------|
| **Contabo** | Windows VPS M | 4 vCPU | 16 GB | 400 GB | USD 13/mes | EU (latencia ~200ms Chile) |
| **Hetzner** | CX32 Windows | 4 vCPU | 16 GB | 240 GB | EUR 15/mes (~USD 16) | EU/US (latencia ~150-250ms) |
| **Azure** | B4ms | 4 vCPU | 16 GB | 128 GB | USD 140/mes | Chile (latencia ~20ms) ⚠️ CARO |
| **AWS EC2** | t3a.xlarge | 4 vCPU | 16 GB | 100 GB EBS | USD 120/mes | Sao Paulo (~50ms) ⚠️ CARO |

**Veredicto Cloud:** ❌ **NO recomendado** por:
1. OneDrive sync no oficial en VMs
2. Costo anual (USD 156-1680) vs inversión única hardware (USD 300-900)
3. Latencia debugging Playwright desde Chile

### Opción 4: Laptop Usado (🚫 NO recomendado)

**Pros:**
- UPS integrado (batería)
- Monitor integrado

**Contras:**
- Bisagras, teclado, touchpad se degradan con uso continuo 24/7
- Batería se hincha si está conectada 24/7 (riesgo incendio)
- Térmica pobre (throttling CPU)
- Pantalla encendida 24/7 (desgaste, consumo)

**Veredicto:** ❌ Evitar laptops para servidor 24/7.

---

## 📋 Decisión Recomendada

### 🏆 Opción Ganadora: Mini PC (Intel NUC / Lenovo ThinkCentre)

**Modelo específico sugerido:**  
**Lenovo ThinkCentre M75q Gen 2** (Ryzen 5 Pro 5650GE, 16 GB, 512 GB NVMe)

**Por qué:**
- ✅ Precio razonable (USD 500-700 usado en Mercado Libre Chile)
- ✅ Enterprise-grade (diseñado para 24/7)
- ✅ Bajo consumo (~35W idle, ~65W load) → ~USD 8/mes electricidad
- ✅ Silencioso (oficina-compatible)
- ✅ Compacto (11.6 x 11.2 x 3.6 cm, montable en pared)
- ✅ Upgradeable (1x SO-DIMM libre, 1x M.2 2280 libre)
- ✅ OneDrive sync nativo (Windows)
- ✅ Garantía Lenovo si compras nuevo

**Configuración mínima:**
- CPU: Ryzen 5 Pro 5650GE (6 cores, 12 threads, 15W-65W TDP)
- RAM: 16 GB DDR4-3200 (8 GB soldado + 8 GB SO-DIMM)
- SSD: 512 GB NVMe PCIe 3.0
- OS: Windows 11 Pro
- Red: Ethernet 1 Gbps + WiFi 6

**Extras necesarios:**
- **UPS:** APC Back-UPS 600VA (~USD 80-120 en PC Factory)
- **Monitor pequeño:** Solo para setup inicial, luego RDP (opcional, ~USD 80-150 usado)
- **Teclado/Mouse USB:** Setup inicial (puedes reutilizar existentes)

**Costo total estimado:**
- Mini PC usado: USD 600
- UPS 600VA: USD 100
- Total: **USD 700** (inversión única)

**Costo operacional mensual:**
- Electricidad (35W × 24h × 30 días × USD 0.15/kWh): ~USD 4/mes
- Internet (ya existente): USD 0
- **Total mensual: USD 4**

**ROI vs Cloud:** En 6 meses ya recuperaste la inversión vs VPS Windows (USD 13-16/mes).

---

## 🚀 Plan de Migración — 7 Fases

### Fase 0: Preparación (1 día)

**Tareas:**
1. ✅ Comprar Mini PC + UPS
2. ✅ Preparar checklist de credenciales `.env`
3. ✅ Exportar tareas Task Scheduler actuales:
   ```powershell
   Get-ScheduledTask | Where-Object {$_.TaskName -match 'WMS|Softnet|VDR|NPS|Productividad|FillRate|Apuesta|Crypto'} | Export-Csv C:\ClaudeWork\_admin\scheduled_tasks_export.csv
   ```
4. ✅ Inventariar puertos en uso:
   - 5000 → api_cobranza
   - 5001 → api_operaciones
   - 5678 → n8n
5. ✅ Backup completo laptop:
   ```bash
   git bundle create C:\ClaudeWork_backup.bundle --all
   ```

**Deliverables:**
- [ ] Mini PC recibido, probado (boot, BIOS, disco)
- [ ] UPS conectado, autonomía testeada (desconectar AC 10 min)
- [ ] Checklist credenciales completo

---

### Fase 1: Instalación Base (medio día)

**Tareas:**
1. Instalar Windows 11 Pro (licencia OEM incluida en Mini PC usado)
2. Configurar usuario administrador:
   - Usuario: `egakat_admin`
   - Password **fuerte** (no PIN, no Windows Hello)
   - Guardar en 1Password / LastPass
3. Deshabilitar suspensión / hibernación:
   ```powershell
   powercfg /change standby-timeout-ac 0
   powercfg /change hibernate-timeout-ac 0
   powercfg /change monitor-timeout-ac 30
   ```
4. Habilitar RDP:
   ```powershell
   Set-ItemProperty -Path 'HKLM:\System\CurrentControlSet\Control\Terminal Server' -name "fDenyTSConnections" -Value 0
   Enable-NetFirewallRule -DisplayGroup "Remote Desktop"
   ```
5. Configurar IP estática en router (DHCP reservation por MAC)
6. Instalar actualizaciones Windows (Windows Update completo)

**Deliverables:**
- [ ] Windows 11 Pro instalado, actualizado
- [ ] RDP accesible desde laptop (`mstsc /v:192.168.x.x`)
- [ ] IP estática asignada

---

### Fase 2: Software Core (1 día)

**Tareas:**
1. Instalar Python 3.12:
   ```powershell
   winget install Python.Python.3.12
   ```
   - Verificar: `py --version` → `Python 3.12.x`
   - Verificar PATH: `py -m pip --version`

2. Instalar Git:
   ```powershell
   winget install Git.Git
   ```
   - Configurar:
     ```bash
     git config --global user.name "Socrates Cabral"
     git config --global user.email "scabral20@yahoo.com.ar"
     ```

3. Instalar Node.js 20 LTS:
   ```powershell
   winget install OpenJS.NodeJS.LTS
   ```
   - Verificar: `node --version` → `v20.x.x`

4. Instalar Docker Desktop (para n8n):
   ```powershell
   winget install Docker.DockerDesktop
   ```
   - Configurar: WSL 2 backend, autostart habilitado

5. Instalar Playwright:
   ```bash
   py -m pip install playwright
   py -m playwright install chromium
   ```

6. Instalar VSCode (opcional, para mantenimiento):
   ```powershell
   winget install Microsoft.VisualStudioCode
   ```

**Deliverables:**
- [ ] `py --version` → Python 3.12.x
- [ ] `git --version` → 2.44+
- [ ] `node --version` → v20.x.x
- [ ] `docker --version` → 24.x.x
- [ ] `py -m playwright --version` → 1.x.x

---

### Fase 3: Migración Código + Credenciales (medio día)

**Tareas:**
1. Clonar repositorio desde laptop:
   ```bash
   cd C:\
   git clone C:\ClaudeWork_backup.bundle ClaudeWork
   # O desde GitHub si ya está pusheado (sin .env):
   git clone https://github.com/scabral/egakat-automation.git ClaudeWork
   ```

2. **Migrar `.env` (CRÍTICO):**
   - ⚠️ **NO subir a GitHub**
   - Copiar manualmente desde laptop vía USB / RDP clipboard / archivo cifrado
   - Ubicación: `C:\ClaudeWork\.env`
   - Verificar permisos: Solo `egakat_admin` puede leer (Windows ACL)

3. Instalar dependencias Python globales:
   ```bash
   cd C:\ClaudeWork
   py -m pip install --upgrade pip
   py -m pip install -r WMS_Automatizacion/requirements.txt
   py -m pip install -r Softnet_Ventas/requirements.txt
   py -m pip install -r crypto_bot/requirements.txt
   py -m pip install -r agente_apuestas/requirements.txt
   # ... repetir para cada módulo
   ```

4. Configurar OneDrive Business:
   - Iniciar sesión con `SHAREPOINT_USER` (de `.env`)
   - Verificar carpeta sync: `%ONEDRIVE%\Egakat - Documentos\Reportes WMS` existe
   - Probar escritura: crear archivo test, verificar aparece en SharePoint

**Deliverables:**
- [ ] Repo clonado en `C:\ClaudeWork`
- [ ] `.env` copiado, verificado (variables críticas presentes)
- [ ] Dependencias Python instaladas (sin errores)
- [ ] OneDrive sync activo, carpetas sincronizadas

---

### Fase 4: Configuración n8n (medio día)

**Tareas:**
1. Crear carpeta persistencia n8n:
   ```bash
   mkdir C:\ClaudeWork\.n8n
   ```

2. Configurar `docker-compose.yml`:
   ```yaml
   version: '3.8'
   services:
     n8n:
       image: n8nio/n8n:latest
       restart: always
       ports:
         - "5678:5678"
       environment:
         - N8N_BASIC_AUTH_ACTIVE=true
         - N8N_BASIC_AUTH_USER=admin
         - N8N_BASIC_AUTH_PASSWORD=${N8N_PASSWORD}
         - N8N_ENCRYPTION_KEY=${N8N_ENCRYPTION_KEY}
       volumes:
         - C:\ClaudeWork\.n8n:/home/node/.n8n
   ```

3. Iniciar n8n:
   ```bash
   cd C:\ClaudeWork
   docker-compose up -d
   ```

4. Importar workflows desde laptop:
   - Exportar desde n8n laptop: Settings → Import/Export → Export all workflows
   - Importar en n8n servidor: Settings → Import/Export → Import from file

5. Actualizar credenciales n8n:
   - API keys (Tavily, Supabase, api-sports)
   - Webhook URLs (si cambiaron IPs)

**Deliverables:**
- [ ] n8n accesible en `http://localhost:5678`
- [ ] Workflows importados, credenciales configuradas
- [ ] Docker autostart habilitado (restart: always)

---

### Fase 5: Configuración Task Scheduler (1 día)

**Tareas:**
1. Crear tareas desde PowerShell (script automatizado):

```powershell
# Script: C:\ClaudeWork\_admin\crear_tareas_programadas.ps1

# WMS Egakat - Descarga diaria
$action = New-ScheduledTaskAction -Execute "py" -Argument "C:\ClaudeWork\WMS_Automatizacion\run_todos.py" -WorkingDirectory "C:\ClaudeWork"
$trigger = New-ScheduledTaskTrigger -Daily -At "08:00AM"
$principal = New-ScheduledTaskPrincipal -UserId "egakat_admin" -LogonType Password -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
Register-ScheduledTask -TaskName "WMS Egakat - Descarga diaria" -Action $action -Trigger $trigger -Principal $principal -Settings $settings

# Softnet Ventas - Descarga diaria
$action = New-ScheduledTaskAction -Execute "py" -Argument "C:\ClaudeWork\Softnet_Ventas\src\run_ventas.py" -WorkingDirectory "C:\ClaudeWork"
$trigger = New-ScheduledTaskTrigger -Daily -At "07:00AM"
Register-ScheduledTask -TaskName "Softnet Ventas - Descarga diaria" -Action $action -Trigger $trigger -Principal $principal -Settings $settings

# VDR Comparador - Cada hora
$action = New-ScheduledTaskAction -Execute "py" -Argument "C:\ClaudeWork\vdr_comparador.py" -WorkingDirectory "C:\ClaudeWork"
$trigger = New-ScheduledTaskTrigger -Once -At "08:00AM" -RepetitionInterval (New-TimeSpan -Hours 1) -RepetitionDuration ([TimeSpan]::MaxValue)
Register-ScheduledTask -TaskName "VDR Comparador - EGA KAT" -Action $action -Trigger $trigger -Principal $principal -Settings $settings

# Productividad - Diario 6:30 AM
$action = New-ScheduledTaskAction -Execute "py" -Argument "C:\ClaudeWork\Productividad_Automatizacion\productividad_diario.py" -WorkingDirectory "C:\ClaudeWork"
$trigger = New-ScheduledTaskTrigger -Daily -At "06:30AM"
Register-ScheduledTask -TaskName "Productividad - Descarga Diaria" -Action $action -Trigger $trigger -Principal $principal -Settings $settings

# FillRate - Diario 6:45 AM
$action = New-ScheduledTaskAction -Execute "py" -Argument "C:\ClaudeWork\FillRate_Automatizacion\fillrate_diario.py" -WorkingDirectory "C:\ClaudeWork"
$trigger = New-ScheduledTaskTrigger -Daily -At "06:45AM"
Register-ScheduledTask -TaskName "FillRate - Descarga Diaria" -Action $action -Trigger $trigger -Principal $principal -Settings $settings

# Agente Apuestas - Diario 9:00 AM
$action = New-ScheduledTaskAction -Execute "py" -Argument "C:\ClaudeWork\agente_apuestas\run_agent.py" -WorkingDirectory "C:\ClaudeWork"
$trigger = New-ScheduledTaskTrigger -Daily -At "09:00AM"
Register-ScheduledTask -TaskName "Agente Apuestas - Analisis Diario" -Action $action -Trigger $trigger -Principal $principal -Settings $settings

# Agente Apuestas - Backtesting nocturno 23:00 (WakeToRun)
$action = New-ScheduledTaskAction -Execute "py" -Argument "C:\ClaudeWork\agente_apuestas\backtesting\run_backtesting.py" -WorkingDirectory "C:\ClaudeWork"
$trigger = New-ScheduledTaskTrigger -Daily -At "11:00PM"
$settings_wake = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -WakeToRun
Register-ScheduledTask -TaskName "Agente Apuestas - Backtesting Nocturno" -Action $action -Trigger $trigger -Principal $principal -Settings $settings_wake

# Crypto Bot - Cada 15 minutos
$action = New-ScheduledTaskAction -Execute "py" -Argument "C:\ClaudeWork\crypto_bot\run_bot.py" -WorkingDirectory "C:\ClaudeWork"
$trigger = New-ScheduledTaskTrigger -Once -At "08:00AM" -RepetitionInterval (New-TimeSpan -Minutes 15) -RepetitionDuration ([TimeSpan]::MaxValue)
Register-ScheduledTask -TaskName "Crypto Bot - Grid Trading" -Action $action -Trigger $trigger -Principal $principal -Settings $settings

# APIs (autostart con Windows)
$action = New-ScheduledTaskAction -Execute "py" -Argument "C:\ClaudeWork\Softnet_Ventas\bots\api_cobranza.py" -WorkingDirectory "C:\ClaudeWork"
$trigger = New-ScheduledTaskTrigger -AtStartup
Register-ScheduledTask -TaskName "API Cobranza - Autostart" -Action $action -Trigger $trigger -Principal $principal -Settings $settings

$action = New-ScheduledTaskAction -Execute "py" -Argument "C:\ClaudeWork\WMS_Automatizacion\api_operaciones.py" -WorkingDirectory "C:\ClaudeWork"
$trigger = New-ScheduledTaskTrigger -AtStartup
Register-ScheduledTask -TaskName "API Operaciones - Autostart" -Action $action -Trigger $trigger -Principal $principal -Settings $settings
```

2. Ejecutar script:
   ```powershell
   cd C:\ClaudeWork\_admin
   .\crear_tareas_programadas.ps1
   ```

3. Verificar tareas creadas:
   ```powershell
   Get-ScheduledTask | Where-Object {$_.TaskName -match 'WMS|Softnet|VDR|Productividad|FillRate|Apuesta|Crypto|API'}
   ```

**Deliverables:**
- [ ] 10+ tareas creadas en Task Scheduler
- [ ] Tareas configuradas con "Run whether user is logged on or not"
- [ ] Password guardado en Task Scheduler (se pedirá al crear tareas)

---

### Fase 6: Pruebas Funcionales (1 día)

**Tareas:**
1. **Probar manualmente cada script principal:**
   ```bash
   py WMS_Automatizacion\run_todos.py
   py Softnet_Ventas\src\run_ventas.py
   py vdr_comparador.py
   py Productividad_Automatizacion\productividad_diario.py
   py FillRate_Automatizacion\fillrate_diario.py
   py agente_apuestas\run_agent.py
   py crypto_bot\run_bot.py
   ```

2. **Verificar salidas:**
   - Logs en `C:\ClaudeWork\logs\` (con timestamp correcto)
   - Reportes en OneDrive (sincronizados a SharePoint)
   - Emails enviados (WMS, Softnet)
   - APIs respondiendo (curl/Postman):
     ```bash
     curl http://localhost:5000/health
     curl http://localhost:5001/health
     curl http://localhost:5678
     ```

3. **Probar Task Scheduler:**
   - Ejecutar manualmente cada tarea desde Task Scheduler (botón Run)
   - Verificar "Last Run Result" → 0x0 (éxito)
   - Revisar logs para errores

4. **Probar n8n workflows:**
   - Ejecutar manualmente workflow "Agente Cobranza"
   - Verificar llamada a `api_cobranza.py`
   - Revisar logs n8n (Docker logs)

5. **Probar failover:**
   - Desconectar Internet, verificar scripts manejan timeout
   - Desconectar AC (UPS), verificar autonomía 10+ minutos
   - Reiniciar servidor, verificar autostart (Docker, APIs, Task Scheduler)

**Deliverables:**
- [ ] Todos los scripts ejecutan sin errores
- [ ] Reportes generados, sincronizados OneDrive
- [ ] APIs respondiendo, n8n activo
- [ ] Task Scheduler tareas OK (Last Run Result 0x0)
- [ ] UPS mantiene servidor 10+ minutos sin AC

---

### Fase 7: Puesta en Producción (medio día)

**Tareas:**
1. **Deshabilitar Task Scheduler en laptop:**
   ```powershell
   Get-ScheduledTask | Where-Object {$_.TaskName -match 'WMS|Softnet|VDR|Productividad|FillRate|Apuesta|Crypto'} | Disable-ScheduledTask
   ```

2. **Actualizar documentación:**
   - `CLAUDE.md` → actualizar IP servidor, rutas
   - `wiki/proyectos/servidor_egakat_24x7.md` → marcar estado: `producción`
   - Memory: `project_wms.md`, `project_softnet_ventas.md` → agregar nota "servidor dedicado desde 2026-04-29"

3. **Configurar monitoreo:**
   - Instalar TeamViewer / AnyDesk para acceso remoto
   - Configurar email alertas (ya incluido en scripts)
   - Crear dashboard simple (opcional):
     ```python
     # C:\ClaudeWork\_admin\monitor_dashboard.py
     # Streamlit dashboard con estado Task Scheduler + APIs + OneDrive sync
     ```

4. **Validar por 48h:**
   - Dejar corriendo 2 días completos
   - Verificar Task Scheduler ejecuta en horario correcto
   - Revisar logs diarios (sin errores críticos)
   - Confirmar emails WMS/Softnet llegan

5. **Apagar laptop → servidor 100% producción**
   - Backup final laptop (git bundle)
   - Apagar Task Scheduler laptop (ya hecho paso 1)
   - Servidor ahora es fuente de verdad

**Deliverables:**
- [ ] Laptop Task Scheduler deshabilitado
- [ ] Servidor corriendo 48h sin intervención
- [ ] Todos los emails/reportes llegando correctamente
- [ ] Monitoreo remoto configurado (TeamViewer/AnyDesk)

---

## ✅ Checklist de Validación Post-Migración

### Hardware & SO
- [ ] Mini PC enciende, POST correcto
- [ ] UPS conectado, autonomía 10+ minutos
- [ ] Windows 11 Pro activado
- [ ] RDP accesible desde red local
- [ ] IP estática asignada (DHCP reservation)
- [ ] Suspensión/hibernación deshabilitada

### Software Base
- [ ] Python 3.12+ instalado (`py --version`)
- [ ] Git instalado, configurado
- [ ] Node.js 20 LTS instalado
- [ ] Docker Desktop instalado, autostart
- [ ] Playwright navegadores instalados
- [ ] OneDrive Business sincronizado

### Código & Credenciales
- [ ] Repo clonado en `C:\ClaudeWork`
- [ ] `.env` presente, variables verificadas
- [ ] Dependencias Python instaladas (todos los módulos)
- [ ] Carpeta `C:\ClaudeWork\logs\` existe
- [ ] Permisos carpeta correctos (egakat_admin owner)

### n8n
- [ ] Docker container corriendo (`docker ps`)
- [ ] n8n accesible en `http://localhost:5678`
- [ ] Workflows importados (agente cobranza, agente ops)
- [ ] Credenciales configuradas (Tavily, Supabase, api-sports)

### Task Scheduler
- [ ] Tareas creadas (10+)
- [ ] Tareas habilitadas (Enabled = True)
- [ ] "Run whether user is logged on or not" activo
- [ ] Password guardado (no pide autenticación al ejecutar)
- [ ] Last Run Result = 0x0 (éxito)

### APIs Flask
- [ ] api_cobranza.py corriendo (puerto 5000)
- [ ] api_operaciones.py corriendo (puerto 5001)
- [ ] `/health` responde HTTP 200
- [ ] n8n puede llamar APIs (test workflow)

### Funcionalidad End-to-End
- [ ] WMS run_todos.py ejecuta completo, genera reportes
- [ ] Softnet Ventas genera Libro Ventas, sube SharePoint
- [ ] VDR Comparador genera reporte, emails enviados
- [ ] Productividad genera resumen 15 clientes
- [ ] FillRate genera resumen 13 clientes
- [ ] Agente Apuestas genera predicciones, Telegram bot envía
- [ ] Crypto Bot ejecuta sin errores (paper trading)
- [ ] OneDrive sync bidireccional funciona (escribe local → SharePoint)
- [ ] Emails SMTP Office365 llegan (WMS, Softnet)

### Monitoreo & Acceso Remoto
- [ ] TeamViewer / AnyDesk instalado, ID anotado
- [ ] Dashboard monitoreo (opcional) corriendo
- [ ] Logs diarios generándose sin errores
- [ ] Email alertas funcionan (probar `[FALLO]` forzado)

### Seguridad
- [ ] `.env` NO en GitHub (gitignored)
- [ ] Permisos `.env` solo lectura egakat_admin
- [ ] RDP solo accesible red local (no puerto forwarding)
- [ ] Windows Firewall activo
- [ ] Windows Defender activo (antivirus)
- [ ] Actualizaciones Windows automáticas habilitadas

---

## 💰 Análisis de Costos

### Inversión Inicial (Opción Mini PC)

| Componente | Precio (USD) |
|------------|--------------|
| Lenovo ThinkCentre M75q Gen 2 (usado, 16 GB, 512 GB) | 600 |
| APC Back-UPS 600VA | 100 |
| Monitor 19" usado (setup inicial, opcional) | 100 |
| **TOTAL** | **800** |

*Si omites monitor (usar RDP desde laptop): **USD 700***

### Costos Operacionales Mensuales

| Concepto | Costo (USD/mes) |
|----------|-----------------|
| Electricidad (35W × 24h × 30d × $0.15/kWh) | 4 |
| Internet (ya existente) | 0 |
| Mantenimiento (estimado, limpieza anual) | 2 |
| **TOTAL** | **6** |

### Comparativa 3 Años (Mini PC vs VPS)

| Escenario | Año 1 | Año 2 | Año 3 | Total 3 años |
|-----------|-------|-------|-------|--------------|
| **Mini PC** | 800 + 72 = 872 | 72 | 72 | **1,016** |
| **VPS Contabo** | 156 | 156 | 156 | **468** |
| **VPS Azure** | 1,680 | 1,680 | 1,680 | **5,040** |

**Consideraciones:**
- ✅ VPS Contabo más barato **PERO** OneDrive sync no oficial (riesgo)
- ✅ Mini PC payback en 5 meses vs VPS Contabo
- ✅ Mini PC control total, no latencia, OneDrive nativo
- ❌ VPS Azure prohibitivo para este caso de uso

**Veredicto:** Mini PC gana en TCO 3 años + confiabilidad OneDrive.

---

## 🔒 Consideraciones de Seguridad

1. **Backup `.env`:**
   - Guardar copia cifrada en 1Password / LastPass
   - Nunca commitear a GitHub
   - Revisar `.gitignore` pre-push

2. **Acceso Remoto:**
   - RDP solo red local (192.168.x.x)
   - NO port forwarding RDP en router (riesgo ataques)
   - Usar VPN (WireGuard / Tailscale) si acceso remoto desde afuera oficina

3. **Task Scheduler Password:**
   - Usuario `egakat_admin` con password fuerte (20+ chars)
   - NO compartir password (solo en 1Password team vault)

4. **Windows Updates:**
   - Configurar actualización automática fuera de horario laboral
   - Reinicio automático solo domingos 3:00 AM

5. **Antivirus:**
   - Windows Defender suficiente (ya incluido)
   - Exclusión carpeta `C:\ClaudeWork\logs\` (falsos positivos scrapers)

---

## 📊 Cronograma Estimado

| Fase | Duración | Dependencias |
|------|----------|--------------|
| 0. Preparación | 1 día | Compra Mini PC |
| 1. Instalación Base | 0.5 días | Fase 0 |
| 2. Software Core | 1 día | Fase 1 |
| 3. Migración Código | 0.5 días | Fase 2 |
| 4. Configuración n8n | 0.5 días | Fase 3 |
| 5. Task Scheduler | 1 día | Fase 3 |
| 6. Pruebas Funcionales | 1 día | Fases 4-5 |
| 7. Producción | 0.5 días | Fase 6 |
| **TOTAL** | **6 días** | — |

**Calendario sugerido (1 semana):**
- **Lun:** Fase 0-1 (setup Windows)
- **Mar:** Fase 2 (software, dependencias)
- **Mié:** Fase 3-4 (código, n8n)
- **Jue:** Fase 5 (Task Scheduler)
- **Vie:** Fase 6 (pruebas)
- **Sáb-Dom:** Fase 7 (validación 48h, producción)

---

## 🚨 Riesgos & Mitigaciones

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|--------------|---------|------------|
| OneDrive sync falla | Media | Alto | Validar sync en Fase 3, rollback a laptop si falla |
| Task Scheduler no ejecuta | Baja | Alto | Probar manualmente en Fase 5, verificar password guardado |
| UPS falla en corte luz | Media | Medio | Probar UPS en Fase 1, comprar UPS enterprise (APC/Tripp Lite) |
| APIs no accesibles desde n8n | Baja | Medio | Firewall Windows, verificar localhost en Fase 6 |
| Credenciales `.env` perdidas | Baja | Crítico | Backup cifrado en 1Password antes de Fase 3 |
| Mini PC falla hardware | Baja | Alto | Garantía Lenovo (1 año nuevo, 0 usado), mantener laptop como respaldo |

---

## 🎯 Próximos Pasos (Post-Migración)

1. **Monitoreo Avanzado (Fase 8, opcional):**
   - Instalar Prometheus + Grafana para métricas servidor
   - Dashboard: CPU, RAM, disco, uptime, logs errores
   - Alertas Telegram si CPU > 80% o disco < 50 GB

2. **Alta Disponibilidad (Futuro):**
   - Segundo Mini PC como failover (cold standby)
   - Rsync diario `C:\ClaudeWork` → Mini PC 2
   - Keepalived / manual switchover si primario falla

3. **Cloud Hybrid (Futuro):**
   - Migrar n8n a VPS cloud (sin OneDrive)
   - APIs locales (OneDrive dependency)
   - Workflows cloud, datos local

---

## 📚 Referencias

- [Intel NUC 12 Pro Specs](https://www.intel.com/content/www/us/en/products/sku/217393/)
- [Lenovo ThinkCentre M75q Gen 2](https://www.lenovo.com/us/en/p/desktops/thinkcentre/m-series-tiny/thinkcentre-m75q-gen-2/11tc1mt75q2)
- [Task Scheduler PowerShell cmdlets](https://learn.microsoft.com/en-us/powershell/module/scheduledtasks/)
- [OneDrive sync limits](https://support.microsoft.com/en-us/office/restrictions-and-limitations-in-onedrive-and-sharepoint-64883a5d-228e-48f5-b3d2-eb39e07630fa)
- [n8n Docker deployment](https://docs.n8n.io/hosting/installation/docker/)

---

**Última actualización:** 2026-04-29  
**Estado:** Planificación  
**Owner:** Sócrates Cabral (scabral20@yahoo.com.ar)
