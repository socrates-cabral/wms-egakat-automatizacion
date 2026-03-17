# Memoria del proyecto — WMS Egakat Automatización
Última actualización: 2026-03-17

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
| `asistente_omni.py` | Asistente conversacional QWEN3-OMNI (texto + audio) con historial, tokens y exportación WAV | v1.0 | ✅ Creado 2026-03-13 |
| `qwen_omni.py` | Script demo QWEN3-Omni-Flash con streaming audio + texto, exporta WAV `respuesta_omni.wav` | v1.0 | ✅ Creado 2026-03-13 |

**Notas:**
- Carpeta `audio/` creada para los archivos WAV generados por `asistente_omni.py`.

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

---

---

# PROYECTO 2 — Finanzas Personales (finanzas_personales)
Última actualización: 2026-03-17

## Contexto
App de gestión de finanzas personales de Sócrates Cabral. Construida en Sprint 1 (2026-03-17) con Claude Code. Basada en el mismo patrón arquitectónico de `chiquito_financiero`.

## Rutas críticas
- **Carpeta proyecto:** `C:\ClaudeWork\finanzas_personales\`
- **Script principal:** `app\main.py`
- **Excel fuente:** `Plantilla-para-controlar-gastos.xlsm` (en carpeta del proyecto)
- **Puerto Streamlit:** `8503` (8502 reservado para chiquito_financiero)
- **Lanzador:** `Iniciar_FinanzasPersonales.bat`
- **Variable entorno:** `EXCEL_FP_PATH` en `C:\ClaudeWork\.env`

## Estructura de carpetas
```
C:\ClaudeWork\finanzas_personales\
├── app\
│   ├── main.py              ← Streamlit app principal (ARCHIVO CENTRAL)
│   ├── data_loader.py       ← Lee el .xlsm con openpyxl data_only=True
│   ├── calculators.py       ← Lógica: presupuesto, patrimonio, tasa ahorro, 50/30/20
│   ├── charts.py            ← Gráficos Plotly reutilizables
│   └── requirements.txt
├── Plantilla-para-controlar-gastos.xlsm   ← Excel fuente
├── MEMORY.md                ← Documentación del proyecto
└── Iniciar_FinanzasPersonales.bat
```

## Excel fuente — estructura validada
**Formato:** `.xlsm` (con macros) → siempre abrir con `keep_vba=True, data_only=True`
**Hojas relevantes:**
| Hoja | Uso |
|------|-----|
| `01 Enero` … `12 Diciembre` | Transacciones — fuente principal |
| `Resumen` | SUMIF cruzado — referencia, NO leer directo |
| `Categorias` | Tabla maestra grupos/conceptos/tipo |
| `Gastos Compartidos` | Desglose vivienda compartida |
| `Trámites` | ❌ NO LEER — datos trámites Venezuela |

**Filas especiales (hojas mensuales):**
- Fila 4: Saldo Actual (fórmula F4 — calculado) → leer con `data_only=True`
- Fila 5: Saldo Inicial (F5 = cuentas + USDT × precio fijo hardcodeado en Excel) → **ignorar F5 para patrimonio; recalcular USDT con precio configurable en Ajustes**
- Fila 7: Headers | Fila 8+: Transacciones

**Columnas hojas mensuales (fila 8 en adelante):**
- Col B: GRUPO | Col C: CONCEPTO | Col D: Fecha | Col E: DETALLE | Col F: IMPORTE
- ⚠️ Algunos meses tienen cols B y C **intercambiadas** → si row[1] es None y row[2] no lo es, hacer swap (ya implementado en data_loader.py)

## Páginas implementadas (estado al 2026-03-17)
| Página | Ícono | Estado | Descripción |
|--------|-------|--------|-------------|
| Dashboard | 📊 | ✅ Activo | Indicadores económicos (UF/USD/IPC/USDT), KPIs mes, Top 10 gastos, dona Fijo/Variable, línea de tendencia, alertas automáticas |
| Mis Ingresos | 💵 | ✅ Activo | Historial completo de liquidaciones, evolución remuneraciones (barras apiladas), evolución descuentos legales, breakdown mes activo (haberes + descuentos) |
| Mes Detalle | 📅 | ✅ Activo | Saldo inicial/actual/variación, regla 50/30/20 (barras real vs ideal), tabla transacciones filtrable por grupo, sección Gastos Compartidos desglosada |
| Anual | 📆 | ✅ Activo | Ingresos vs gastos por mes (barras agrupadas), barras apiladas por grupo/mes, resumen anual por grupo (tabla), Top 5 gastos del año |
| Patrimonio Neto | 💎 | ✅ Activo | Total activos/pasivos/patrimonio neto, ratio endeudamiento con semáforo, waterfall chart activos+AFP vs pasivos vs resultado, tablas activos y pasivos |
| AFP y Previsión | 🏛️ | ✅ Activo | Carga de Excel AFP (drag & drop), KPIs saldo/aporte mensual/isapre, proyección 3 escenarios (pesimista 4%/base 6%/optimista 8%) a N años con slider, comparativa comisiones AFP Chile |
| Simulador | 🎛️ | ✅ Activo | 4 tabs: Meta de Ahorro (proyección hasta alcanzar meta), FIRE (independencia financiera), Proyección AFP, Deuda |
| Liquidaciones | 📋 | ✅ Activo | Historial completo de liquidaciones de sueldo |
| Ajustes | ⚙️ | ✅ Activo | Ruta Excel, ingresos mensuales, precio USDT, botón recargar |

## Indicadores económicos en Dashboard
- Fuente: `mindicador.cl` (CMF) — API REST gratuita
- Valores mostrados: UF, Dólar USD, IPC mensual, USDT estimado
- Se actualiza en tiempo real al cargar la página

## Saldo inicial Enero 2026 (referencia hardcodeada en Excel)
- Cuenta 1 (vista): $1.679.673
- Cuenta 2 (ahorro): $10.349.996
- USDT: 909.09 unidades (precio variable — configurar en Ajustes)
- Total referencia: ~$32.000.000

## Diseño visual — tema implementado
**Sidebar:** Híbrido Opción 3 + Opción 1
- Fondo: `#080E1A`
- Borde derecho: `1.5px solid #14b8a6`
- Ítem activo: color `#14b8a6`, bg `rgba(20,184,166,0.09)`, barra izquierda `2.5px`
- Secciones en CAPS: ANÁLISIS / PATRIMONIO / HERRAMIENTAS
- Botón Recargar: bg `#14b8a6`, texto `#021b18`
- Main bg: `#0c1422`

**Estructura menú sidebar:**
```
ANÁLISIS     → Dashboard, Mis Ingresos, Mes Detalle, Anual
PATRIMONIO   → Patrimonio Neto, Deudas, AFP y Previsión
HERRAMIENTAS → Liquidaciones, Simulador, Ajustes
```

## COLOR_MAP Plotly (paleta semántica — USAR EN TODOS LOS GRÁFICOS)
```python
COLOR_MAP = {
    'Hogar y Vivienda':          '#14b8a6',   # teal
    'Familia e Hijos':           '#60a5fa',   # azul
    'Financiero - Deudas':       '#f59e0b',   # amber
    'Alimentación':              '#818cf8',   # indigo
    'Salud y Cuidado Personal':  '#f472b6',   # pink
    'Transporte':                '#34d399',   # verde claro
    'Servicios Básicos':         '#fb923c',   # naranja
    'Educación y Formación':     '#a78bfa',   # violeta
    'Ahorro e Inversión':        '#4ade80',   # verde
    'Suscripciones Digitales':   '#38bdf8',   # sky
    'Ocio y Vida Social':        '#e879f9',   # fuchsia
    'Mascotas':                  '#fbbf24',   # yellow
    'Regalos y Donaciones':      '#f87171',   # red claro
    'Varios y Otros':            '#94a3b8',   # slate
    'Seguros':                   '#6ee7b7',   # emerald
}
```

## Mejoras de diseño — Estado (2026-03-17)

### ✅ Aplicadas (Sprint 2)
1. **Tablas oscuras** — CSS `.stDataFrame table` dark + header uppercase + zebra + hover teal
2. **COLOR_MAP unificado** — 15 categorías en `charts.py`, usado en barras apiladas y top gastos
3. **KPI cards con delta** — Gastos muestra `±$X vs [mes anterior]` con `delta_color="inverse"`
4. **Badges de categoría** — tabla Mes Detalle usa HTML + pills de color via `badge_grupo()` + `.badge-table` CSS
5. **% en barras Top Gastos** — etiqueta `$521K  37%` + colores semánticos por grupo (sin gradiente)
6. **Tooltips CLP** — `hovertemplate` en `chart_barras_gastos_mes` y `chart_ingresos_vs_gastos`
7. **Área rellena Dashboard** — `fill='tozeroy'` con `rgba(20,184,166,0.08)` ya activo
8. **Semáforo Financiero** — cards oscuras `#111d2e` en lugar de `#f8f9fa`

### 🔜 Pendientes Sprint 3
- Badges en otras tablas (Anual, Patrimonio)
- BCI scraper parser Excel
- ITAÚ scraper
- Recargar saldo API Anthropic (AI Insights)

## Dependencias del proyecto
```
py -m pip install streamlit pandas openpyxl plotly python-dotenv requests --break-system-packages
```

## Reglas específicas del proyecto
1. `data_only=True` y `keep_vba=True` SIEMPRE al abrir el `.xlsm`
2. NO leer hoja `Trámites`
3. Puerto `8503` — no cambiar (8502 es chiquito_financiero)
4. `EXCEL_FP_PATH` desde `.env` — no hardcodear ruta
5. `COLOR_MAP` definido en `charts.py` — importar desde ahí, nunca redefinir local
6. Tipo de cambio USDT configurable en Ajustes — nunca hardcodeado
7. Indicadores económicos desde `mindicador.cl` — manejar timeout con try/except y mostrar valor N/D si falla
8. Cols B/C pueden estar intercambiadas en algunos meses → si `row[1]` (grupo) es None y `row[2]` no lo es, hacer swap; implementado en `data_loader.py`
9. F5 (Saldo Inicial) tiene USDT × precio fijo hardcodeado → **nunca usar F5 para calcular patrimonio**; recalcular siempre con precio actual de Ajustes
