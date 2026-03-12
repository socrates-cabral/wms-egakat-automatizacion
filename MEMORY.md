# Memoria del proyecto — WMS Egakat Automatización
Última actualización: 2026-03-11

## Contexto del usuario
- **Nombre:** Sócrates Cabral
- **Rol:** Head of Control Management & Continuous Improvement — Egakat SPA (3PL)
- **Stack:** Python 3 + Playwright + python-dotenv
- **Carpeta trabajo:** `C:\ClaudeWork\`
- **Comando Python:** siempre `py` (nunca `python` ni `pip` directo — siempre `py -m pip`)

---

## Estructura de carpetas (reorganizada 2026-03-09)
```
C:\ClaudeWork\
├── run_todos.py           ← PUENTE → WMS_Automatizacion\run_todos.py (Task Scheduler apunta aquí)
├── vdr_comparador.py      ← PUENTE → VDR_Comparador\vdr_comparador.py (Task Scheduler apunta aquí)
├── .env + MEMORY.md       ← raíz (no mover)
├── WMS_Automatizacion\    ← wms_descarga, posiciones_descarga, staging_descarga, run_todos, sharepoint_upload
├── VDR_Comparador\        ← vdr_comparador, vdr_ultimo_procesado.txt, tarea_vdr.xml, crear_tarea_vdr.ps1
├── Documentos\            ← Informe.docx, PPT, generar_documentos.py
├── Solicitudes_IT\        ← Solicitud_Azure_AD_WMS_Egakat.docx
├── otros_proyectos\       ← proyectos independientes (horario, inventario)
├── logs\                  ← todos los logs centralizados
├── _debug_historico\      ← screenshots y scripts de debug históricos
└── _instaladores\         ← Claude Setup.exe
```
**Patrón puente:** Task Scheduler → script raíz (puente) → script real en subcarpeta. No requiere cambios en Task Scheduler.

## Scripts principales
| Archivo | Descripción | Versión | Estado |
|---|---|---|---|
| `WMS_Automatizacion\wms_descarga.py` | Stock WMS Semanal — 3 centros → OneDrive | v2.4 | ✅ Activo y en producción |
| `WMS_Automatizacion\posiciones_descarga.py` | Consulta de Posiciones — 8 reportes → OneDrive | v1.2 | ✅ Validado completo 2026-03-08 |
| `WMS_Automatizacion\staging_descarga.py` | Staging IN/OUT — 16 clientes, 3 sesiones → OneDrive | v2.3 | ✅ Validado 2026-03-08 |
| `WMS_Automatizacion\preparacion_descarga.py` | Pedidos Preparados — 5 clientes Quilicura → OneDrive Clientes EK | v1.4 | ✅ Produccion |
| `WMS_Automatizacion\recepciones_descarga.py` | Recepciones Recibidas — 5 clientes Quilicura → OneDrive Clientes EK | v1.1 | ✅ Produccion |
| `WMS_Automatizacion\run_todos.py` | Orquestador — ejecuta los 4 módulos + alerta email en fallo | v1.3 | ✅ En producción |
| `VDR_Comparador\vdr_comparador.py` | Comparador Base VDR Derco Parts — detecta cambios VDR SAP/FISICO → Excel OneDrive | v1.0 | ✅ Validado 2026-03-09 |

---

## MÓDULO 1 — Stock WMS Semanal (wms_descarga.py v2.4) ✅

**URL:** `https://egakatwms.cl/sglwms_EGA_prod/hinicio.aspx`
**Usuario:** `SCABRAL` | **Clave:** `.env` → `WMS_PASSWORD`
**v2.4 fix (2026-03-09):** UnicodeEncodeError CP1252 — la función `log()` ahora reemplaza todos los símbolos Unicode (`→`, `✓`, `✗`, `▶`, `✅`, `❌`) por equivalentes ASCII antes del `print`. También corregido el `print` final con `→` hardcodeado.

**Flujo validado:**
1. Login: `input[name='vUSR']`, `input[name='vPASSWORD']` → clic `input[name='BUTTON3']`
2. Seleccionar depósito en `<select>` → clic `input[value='Aceptar']`
3. Clic `text=Procesos WMS`
4. Clic `text=Buscar Contenedores en Warehouse`
5. Clic `input[value='Exportar Excel']`
6. `page.expect_download()` → `download.save_as(ruta_fija)`

**Notas críticas:**
- `context = browser.new_context(accept_downloads=True)` obligatorio
- Archivo descarga con nombre UUID sin extensión → siempre usar `expect_download`
- Timeout descarga: 180.000ms (QUILICURA ~75s, PUDAHUEL ~18s, PUDAHUEL UNITARIO ~13s)
- El menú NO usa hover — todo son clics directos

**Centros procesados:**
| CD WMS | Carpeta destino OneDrive |
|---|---|
| QUILICURA | `...\Stock WMS Semanal\Quilicura` |
| PUDAHUEL | `...\Stock WMS Semanal\Pudahuel` |
| PUDAHUEL UNITARIO | `...\Stock WMS Semanal\Pudahuel` |
| PUDAHUEL REFRIGERADO | ❌ No se descarga |

**Ruta base:** `C:\Users\Socrates Cabral\OneDrive - EGA KAT LOGISTICA SPA\Datos para Dashboard - Stock WMS Semanal`

---

## MÓDULO 2 — Consulta de Posiciones (posiciones_descarga.py v1.2) ✅

**URL directa:** `https://egakatwms.cl/sglwms_EGA_prod/consultaposiciones.aspx?SCABRAL`

**Clave validada 2026-03-08:** El WMS filtra por el dropdown del formulario, NO por el CD de sesión → un solo login con QUILICURA baja los 8 reportes.

**Selectores confirmados:**
- Select depósito: `select[name='vCOMBOSUCURSAL']` → `1`=QUILICURA, `2`=PUDAHUEL, `3`=PUDAHUEL UNITARIO, `4`=PUDAHUEL REFRIGERADO
- Checkboxes por ID: `#vINPUTPOSCOMPLETAS`, `#vINPUTPOSPARCIALOCUPADAS`, `#vINPUTPOSLIBRES`
  - `get_by_label` NO funciona — los labels están vacíos
- Botón: `input[value='Consulta Excel']` con fallback JS click
- Usar `wait_for_load_state("load")` + `wait_for_timeout()` — `networkidle` causa timeout
- `sys.stdout.reconfigure(encoding="utf-8")` necesario en Windows

**Configuración checkboxes:**
- **Ocupadas:** `#vINPUTPOSCOMPLETAS` ✅ + `#vINPUTPOSPARCIALOCUPADAS` ✅ + `#vINPUTPOSLIBRES` ☐
- **Libres:** `#vINPUTPOSCOMPLETAS` ☐ + `#vINPUTPOSPARCIALOCUPADAS` ☐ + `#vINPUTPOSLIBRES` ✅

**Archivo descarga como `.xls` → `save_as()` con `.xlsx` funciona correctamente**
**Nombres de archivo FIJOS — Power Query los busca por nombre exacto**

**8 reportes:**
| CD | Valor | Tipo | Archivo fijo | Carpeta |
|---|---|---|---|---|
| QUILICURA | 1 | ocupadas | `Posiciones Ocupadas.xlsx` | Quilicura |
| QUILICURA | 1 | libres | `Posiciones Libres.xlsx` | Quilicura |
| PUDAHUEL | 2 | ocupadas | `Posiciones Ocupadas Moderno.xlsx` | Pudahuel |
| PUDAHUEL | 2 | libres | `Posiciones Libres Moderno.xlsx` | Pudahuel |
| PUDAHUEL UNITARIO | 3 | ocupadas | `Posiciones Ocupadas Unitario.xlsx` | Pudahuel |
| PUDAHUEL UNITARIO | 3 | libres | `Posiciones Libres Unitario.xlsx` | Pudahuel |
| PUDAHUEL REFRIGERADO | 4 | ocupadas | `Posiciones Ocupadas Refrigerado.xlsx` | Pudahuel |
| PUDAHUEL REFRIGERADO | 4 | libres | `Posiciones Libres Refrigerado.xlsx` | Pudahuel |

**Ruta base:** `C:\Users\Socrates Cabral\OneDrive - EGA KAT LOGISTICA SPA\Datos para Dashboard - Consulta de Posiciones`

---

## MÓDULO 3 — Staging IN/OUT (staging_descarga.py v2.3) ✅ VALIDADO 2026-03-08

**URL:** `https://egakatwms.cl/sglwms_EGA_prod/ReportesPersonalizados.aspx`
**Navegar:** `page.goto(url)` directo — NO usar hover de menú (colapsa antes del clic)

**Diferencia crítica vs Módulo 2:** SÍ importa el CD de sesión → 3 sesiones con login propio.

**Selectores confirmados:**
- Depósito: `select[name='vSUCURSAL']` | Empresa: `select[name='vEMPRESA']` | Reporte: `select[name='vREPORTE']`
- Botón: `input[name='SEARCHBUTTON']` con `force=True`
- **Captura URL:** `context.on("request")` filtrando `.csv` — **NO usar `expect_page`** (popup queda en `about:blank`)
- Descarga: `page.request.get(url_csv)` con sesión autenticada

**Archivo descarga:**
- Formato `.csv`, nombre original `VISTA_CONSULTA_Pallets_[CLIENTE][USUARIO][DDMMYYYYHHMMSS].csv`
- **NO se renombra** — se guarda con nombre original

**Nota NATIVO DRINKS SPA:** genera archivo 0 bytes — problema de datos en WMS, reportado, comportamiento esperado.

**3 sesiones y clientes:**

| Sesión WMS | Empresa WMS | Carpeta OneDrive |
|---|---|---|
| QUILICURA | CERVECERIA ABI | `\Quilicura\ABINBEV` |
| QUILICURA | DAIKIN | `\Quilicura\DAIKIN` |
| QUILICURA | DAIKIN CLIENTES | `\Quilicura\DAIKIN CLIENTES` |
| QUILICURA | DERCO | `\Quilicura\DERCO` |
| QUILICURA | MASCOTAS LATINAS | `\Quilicura\MASCOTAS LATINAS` |
| QUILICURA | POCHTECA | `\Quilicura\POCHTECA` |
| PUDAHUEL | BARENTZ | `\Pudahuel\BARENTZ` |
| PUDAHUEL | BURASCHI | `\Pudahuel\BURASCHI` |
| PUDAHUEL | CEPAS CHILE | `\Pudahuel\CEPAS CHILE` |
| PUDAHUEL | COLLICO | `\Pudahuel\COLLICO` |
| PUDAHUEL | DELIBEST | `\Pudahuel\DELIBEST` |
| PUDAHUEL | INTIME | `\Pudahuel\INTIME` |
| PUDAHUEL | NATIVO DRINKS SPA | `\Pudahuel\NATIVOS DRINK` |
| PUDAHUEL | TRES MONTES | `\Pudahuel\TRES MONTE` |
| PUDAHUEL | UNILEVER | `\Pudahuel\UNILEVER` |
| PUDAHUEL UNITARIO | RUNO SPA | `\Pudahuel\RUNO` |

**Excluidos:** PUDAHUEL REFRIGERADO ❌, resto de clientes de PUDAHUEL UNITARIO ❌

**Ruta base:** `C:\Users\Socrates Cabral\OneDrive - EGA KAT LOGISTICA SPA\Datos para Dashboard - Stagin IN- OUT`

---

## MÓDULO 4 — VDR Comparador Derco Parts (vdr_comparador.py v1.0) ✅ VALIDADO 2026-03-09

**Origen:** `C:\Users\Socrates Cabral\Grupo Planet SpA\José Caceres - Base VDR\[MM. Mes]\`
**Salida:** `C:\Users\Socrates Cabral\OneDrive - EGA KAT LOGISTICA SPA\Reportes VDR\`
**Estado:** `C:\ClaudeWork\VDR_Comparador\vdr_ultimo_procesado.txt` — formato `[carpeta_mes]|[nombre_archivo]`

**Flujo:** Detecta carpeta mes actual (dinámica) → lista archivos `Base VDR DD-MM-YYYY.xlsx` → compara los 2 más recientes si hay novedad → genera `Reporte_VDR_DDMMYYYY_HHMMSS.xlsx` solo si hay diferencias

**4 hojas del reporte:** `Diferencias_VDR` | `Cambios_Equivalencia` | `SKUs_Nuevos` | `SKUs_Eliminados`

**Columnas clave:** `Material WMS` (clave join) | `VDR SAP` | `VDR FISICO` | `Material SAP` | `Desc_Material` | `Categoria`

**Notas críticas:**
- Ruta origen: `José` con tilde — NO `Jose`
- Siempre compara `archivos[-1]` vs `archivos[-2]` (los 2 más recientes) — el estado solo controla si hay novedad
- 91.579 registros por archivo — tiempo de procesamiento ~29 segundos
- Task Scheduler: `VDR Comparador - EGA KAT` — cada hora L-V 08:00–19:00 ✅ activa 2026-03-09
- Power Automate: `VDR Comparador - Notificacion Reportes` ✅ — trigger OneDrive /Reportes VDR → Delay 2min → Send email (V2) con File content adjunto
- Destinatarios activos: `socrates.cabral@egakat.cl`, `daniel.galindo@egakat.cl`, `mariana.varela@egakat.cl` ✅ validado 2026-03-09

---

## Estado del proyecto

| Fase | Descripción | Estado |
|---|---|---|
| 1 | Script Stock WMS 3 centros → OneDrive | ✅ Completo v2.4 |
| 2a | OneDrive → SharePoint automático | ✅ Completo |
| 2b | Correo notificación Gmail (App Password) | ❌ Eliminado 2026-03-08 |
| 3 | Programador de tareas Windows L-V 8AM | ✅ Actualizado → run_todos.py |
| 4 | Script Consulta de Posiciones (8 reportes) | ✅ Completo v1.2 validado |
| 5 | Graph API + OAuth2 (SharePoint directo + correo único) | 🔮 Pendiente VoBo IT |
| 6 | headless=True en los 3 scripts | ✅ Activado 2026-03-08 |
| 7 | Script Staging IN/OUT | ✅ Completo v2.3 validado |
| 8 | Power BI dashboards | 🔮 Futuro |
| 9 | VDR Comparador Derco Parts | ✅ Completo v1.0 — tarea + Power Automate activos 2026-03-09 |
| 10 | NPS+CSAT LimeSurvey → OneDrive | ✅ Completo v1.0 — tareas + Power Automate activos 2026-03-10 |

---

## MÓDULO 5 — NPS Encuesta LimeSurvey (nps_descarga.py v1.0) ✅ VALIDADO 2026-03-10

**Carpeta:** `NPS_Encuesta\`
**URL LimeSurvey:** desde `.env` → `LIMESURVEY_URL`, `LIMESURVEY_USER`, `LIMESURVEY_PASSWORD`
**Salida:** `C:\Users\Socrates Cabral\OneDrive - EGA KAT LOGISTICA SPA\Reportes NPS\`
**Alertas:** subcarpeta `/Alertas/` — archivo vacío si no hay respuestas nuevas

**Tareas programadas:**
- `NPS Egakat - Primera descarga` → 28/03/2026 10:00 única vez
- `NPS Egakat - CSAT Mensual` → día 11 cada mes 10:00
- `NPS Egakat - NPS Trimestral` → día 16 mar/jun/sep/dic 10:00

**Power Automate:**
- `NPS Egakat - Alerta Sin Respuestas` — trigger /Alertas/ → correo urgente
- `NPS Egakat - Nuevo Reporte Disponible` — trigger /Reportes NPS/ → correo con link

**Pendientes NPS:**
- Franco Pérez (franco.perez@egakat.cl): tokens individuales + skip logic CSAT en LimeSurvey
- Power BI dashboard NPS — cuando lleguen respuestas 28/03/2026

---

## MÓDULO 6 — SharePoint Copy Staging → Clientes EK (sharepoint_copy.py v2.1) ✅ VALIDADO 2026-03-11

**Script:** `WMS_Automatizacion\sharepoint_copy.py`
**Flujo:** OneDrive Stagin IN-OUT (origen) → OneDrive `Datos para Dashboard - Clientes EK` (destino local sync) → SharePoint automático
**Respaldo API:** `sharepoint_copy_API_v1.py` — versión Office365 REST API, pendiente App Registration IT (AADSTS53003)
**Integrado en:** `run_todos.py` como Módulo 6 (modo daily)
**Anti-duplicado:** verifica existencia del archivo antes de copiar (`Path.exists()`)
**Modo daily:** archivos del día actual | **Modo backfill:** todos del mes sin duplicar (ejecución manual)
**Destino dinámico:** `{CLIENTE}/Inventario/{AÑO}/{MM Mes}` — carpeta creada automáticamente
**Formato mes:** `03 Marzo` (número + nombre, igual que 2025) — estandarizado toda la carpeta Clientes EK
**Nombre destino:** prefijo `YYYY-MM-DD_` al copiar — permite ordenar descendente en SharePoint (más reciente arriba)
**Clientes Quilicura:** ABINBEV, DAIKIN, DERCO, MASCOTAS LATINAS, POCHTECA
**PUDAHUEL:** vacío por ahora — agregar en CLIENTES cuando se habilite
**Origen:** `Datos para Dashboard - Stagin IN- OUT\Quilicura\{CLIENTE}\`
**Destino:** `Datos para Dashboard - Clientes EK\{CLIENTE}\Inventario\{AÑO}\{MM Mes}\`
**Power BI:** prefijo YYYY-MM-DD_ NO afecta Query M — `Text.PositionOfAny(...Occurrence.Last)` sigue encontrando timestamp al final del nombre original

## MÓDULO 7 — Pedidos Preparados (preparacion_descarga.py v1.0) ⏳ Validacion pendiente 2026-03-11

**URL:** `https://egakatwms.cl/sglwms_EGA_prod/pedidospreparadoswp.aspx`
**Login:** sesión QUILICURA (un solo login para los 5 clientes)
**fecha_desde:** día 1 del mes de fecha_hasta | **fecha_hasta:** datetime.now() - 1 día

**Selectores confirmados (debug 2026-03-11):**
- Depósito: `select[name='vSUCCOD']` → label "QUILICURA"
- Empresa: `select[name='vCOD_EMP']` → label nombre empresa
- Fecha Desde: `input[name='vFDESDE']` | Fecha Hasta: `input[name='vFHASTA']` (DD/MM/YYYY)
- Estado: `select[name='vESTADO']` → label "Preparados"
- Combo Excel: `select[name='vCOMBOEXCEL']` → label "Excel General"
- Vista detalle: `select[name='vDETALLEOCABECERA']` → label "Mostrar Detalle de Picking" (CRÍTICO — sin esto faltan 7 columnas)
- Isla de Control: `select[name='vFILTROIC']` → dejar en "Todas" (no tocar)
- Botón Aplicar: `input[name='APLICAR2']` → NO hacer clic (exportar directo desde BUTTON7)
- Botón Excel: `input[name='BUTTON7']` (NO BUTTON7 de PDF — ese es `BTNIMPRIMITPDF`)
- Popup JS "2000+ registros": `page.on("dialog", lambda d: d.dismiss())` → descartar

**Flujo por cliente:** goto URL → select sucursal → select empresa → select estado → fill fechas + Tab → select vDETALLEOCABECERA → select combo excel → expect_download + click BUTTON7 (SIN clic APLICAR2)
**Timeout descarga:** 300.000ms (5 min) — DERCO puede ser muy pesado

**Clientes:** CERVECERIA ABI → ABINBEV | DAIKIN → DAIKIN | DERCO → DERCO | MASCOTAS LATINAS → MASCOTAS LATINAS | POCHTECA → POCHTECA
**Destino:** `Datos para Dashboard - Clientes EK\{CLIENTE}\Preparación\{AÑO}\{MM Mes}\Pedidos Preparados.xlsx`
**Sobrescribe el archivo** — siempre contiene el acumulado del mes
**Integrado:** `run_todos.py` v1.3 como Módulo 7 (último en ejecutarse)

## Infraestructura y bloqueos

**Bloqueos activos:**
- `AADSTS53003` — autenticación SharePoint directa bloqueada por Conditional Access
- SMTP `smtp.office365.com:587` — SmtpClientAuthentication deshabilitado

**Solución unificada:** Azure AD App Registration — pendiente VoBo IT
**Contacto IT:** José Contreras — jcontreras@tinetservices.cl
**Documento enviado:** `Solicitudes_IT\Solicitud_Azure_AD_WMS_Egakat.docx`

**Power Automate Cloud (activos):**
- Flow 1: `WMS Egakat - Notificación Reportes Subidos` — trigger SharePoint, llegan 3 correos separados (fix con OAuth2 pendiente)
- Flow 2: `VDR Comparador - Notificacion Reportes` — trigger OneDrive /Reportes VDR → Delay 2min → correo con Excel adjunto ✅
- Flow 3: `NPS Egakat - Alerta Sin Respuestas` — trigger /Alertas/ → correo urgente ✅
- Flow 4: `NPS Egakat - Nuevo Reporte Disponible` — trigger /Reportes NPS/ → correo con link ✅

**Programador de tareas Windows:**
- `WMS Egakat - Descarga diaria` → `python.exe C:\ClaudeWork\run_todos.py` (puente) a las 8AM L-V
- `VDR Comparador - EGA KAT` → `python.exe C:\ClaudeWork\vdr_comparador.py` (puente) cada hora L-V 08:00–19:00
- `NPS Egakat - Primera descarga` → `nps_descarga.py` — 28/03/2026 10:00 única vez
- `NPS Egakat - CSAT Mensual` → `nps_descarga.py` — día 11 cada mes 10:00
- `NPS Egakat - NPS Trimestral` → `nps_descarga.py` — día 16 mar/jun/sep/dic 10:00
- **Ejecutable:** ruta completa `C:\Users\Socrates Cabral\AppData\Local\Python\pythoncore-3.14-64\python.exe`
- **LogonType:** `Password` — corre sin sesión activa
- **WakeToRun:** `True` — reactiva laptop desde Sleep a las 8AM
- Logs en: `C:\ClaudeWork\logs\`

**Claude Desktop MCPs configurados:**
- Config real: `C:\Users\Socrates Cabral\AppData\Local\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Roaming\Claude\claude_desktop_config.json`
- Power BI MCP ✅ — solo modelo (medidas, tablas, relaciones — NO páginas de reportes)
- Playwright MCP ✅ — `@playwright/mcp@latest` via npx — control de navegador desde Claude.ai
- Filesystem MCP ✅ — `@modelcontextprotocol/server-filesystem` via npx — acceso a `C:\ClaudeWork` y OneDrive desde Claude.ai

---

## Reglas del agente
1. Siempre usar `py` y `py -m pip`
0. **Estructura de carpetas obligatoria:** Todo proyecto, script, presentacion o archivo nuevo debe respetar la organizacion de `C:\ClaudeWork\`. Cada proyecto va en su propia subcarpeta. Scripts puente en raiz solo si Task Scheduler los necesita ahi. Nada suelto en la raiz salvo `.env` y `MEMORY.md`.
0b. **Flujo Claude.ai + Claude Code:** En proyectos nuevos o problemas complejos, sugerir activamente cuando conviene usar Claude.ai primero (diseño, arquitectura, analisis de screenshots/logs visuales, redaccion) y luego Claude Code para implementar, ejecutar y depurar. Tabla de referencia: Editar scripts/debug → Code | Diseñar modulo nuevo → Claude.ai | Analizar log texto → Code | Debug visual WMS/screenshots → Claude.ai | Documentos/MEMORY → Code.
2. Nunca hardcodear credenciales — leer desde `.env`
3. `expect_download()` para descargas tipo attachment (Módulos 1 y 2)
4. `context.on("request")` para capturar URL CSV en Módulo 3 — NO `expect_page` (popup queda en about:blank)
5. Si error en un reporte → continuar con el siguiente
6. Scripts idempotentes
7. Destino siempre OneDrive → SharePoint, NUNCA `C:\ClaudeWork\Reportes\`
8. Nombres de archivo en Módulo 2: FIJOS (Power Query los busca por nombre exacto)
9. Nombres de archivo en Módulo 3: ORIGINALES del WMS (no renombrar)
10. Comentar líneas deprecadas — nunca eliminar (preservar historial de cambios)

## Dependencias
```
py -m pip install playwright python-dotenv openpyxl Office365-REST-Python-Client python-docx python-pptx anthropic requests pywin32
py -m playwright install chromium
```
