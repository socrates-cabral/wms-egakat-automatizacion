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

## MÓDULO 5 — NPS Encuesta LimeSurvey (nps_descarga.py v2.1) ✅ ACTUALIZADO 2026-03-20

**Carpeta:** `NPS_Encuesta\`
**URL LimeSurvey:** desde `.env` → `LIMESURVEY_URL`, `LIMESURVEY_USER`, `LIMESURVEY_PASSWORD`
**Salida fija Power BI:** `OneDrive\Reportes NPS\NPS_PBI_datos.xlsx` (4 hojas: fClientes/fÁreas/fClientes_mes/dClientes)
**Archivos mapeo:** `tokens_csat.csv` + `Contactos_Clientes.xlsx` en NPS_Encuesta\ — actualizar cada ronda

**Tareas programadas:**
- `NPS Egakat - CSAT Mensual` → día 11 cada mes 10:00
- `NPS Egakat - NPS Trimestral` → día 16 mar/jun/sep/dic 10:00

**Power Automate:**
- `NPS Egakat - Alerta Sin Respuestas` — trigger /Alertas/ → correo urgente
- `NPS Egakat - Nuevo Reporte Disponible` — trigger /Reportes NPS/ → correo con link

**Pendientes NPS:**
- Conectar Power BI al nuevo Excel (antes era Google Sheets)
- 25/03: descargar tokens NPS 418429 → guardar como `tokens_nps.csv`
- Agregar contacto NATIVO DRINKS SPA en LimeSurvey (próxima ronda)
- Rediseño Power BI: mejores visuales + M code documentado (carta blanca del usuario)

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

**Columnas hojas mensuales (fila 8 en adelante):**
- Col B: GRUPO | Col C: CONCEPTO | Col D: Fecha | Col E: DETALLE | Col F: IMPORTE

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

## Mejoras de diseño PENDIENTES (Sprint 2 — 2026-03-17)
Aplicar en orden de impacto visual:

### P1 — CRÍTICO (rompen la coherencia del tema oscuro)
**1. Tablas al tema oscuro** — todas las `st.dataframe()` y `st.table()` tienen fondo blanco por defecto. Solución: inyectar CSS global en `main.py`:
```python
st.markdown("""<style>
.stDataFrame { background: transparent !important; }
.stDataFrame table { background: #111d2e !important; color: #e2e8f0 !important; }
.stDataFrame thead tr th { background: #0c1422 !important; color: #4a6278 !important;
    font-size: 11px !important; font-weight: 500 !important; text-transform: uppercase !important;
    letter-spacing: 0.06em !important; border-bottom: 0.5px solid #1e2d45 !important; }
.stDataFrame tbody tr td { border-bottom: 0.5px solid #0f1a2a !important; }
.stDataFrame tbody tr:hover td { background: rgba(20,184,166,0.04) !important; }
.stDataFrame tbody tr:nth-child(even) td { background: rgba(255,255,255,0.015) !important; }
[data-testid="stTable"] { background: transparent !important; }
</style>""", unsafe_allow_html=True)
```

**2. Paleta Plotly unificada** — definir `COLOR_MAP` (ver arriba) en `charts.py` como constante global y referenciarla en TODOS los gráficos de barras apiladas, horizontales y donas. El gráfico Anual actualmente usa la paleta arcoíris de Plotly (12 colores sin semántica) — reemplazar con `color_discrete_map=COLOR_MAP`.

**3. KPI cards con delta** — en Dashboard y Mes Detalle, calcular variación vs mes anterior y mostrar con `st.metric()` nativo de Streamlit (soporta delta con flecha ▲▼ y color automático verde/rojo):
```python
st.metric(label="Gastos Marzo", value="$1.392.078",
          delta="+$276K vs feb", delta_color="inverse")
```

### P2 — IMPORTANTE (mejoran legibilidad y presentación)
**4. Badges de categoría en tabla transacciones** — reemplazar texto plano en columna Grupo por HTML con pill de color:
```python
def badge_grupo(grupo):
    color = COLOR_MAP.get(grupo, '#94a3b8')
    return f'<span style="background:{color}22;color:{color};padding:2px 8px;border-radius:4px;font-size:11px;font-weight:500;">{grupo}</span>'
```
Usar `st.write(df.to_html(escape=False), unsafe_allow_html=True)` para renderizar.

**5. Tooltip Plotly en formato CLP** — agregar en todos los gráficos:
```python
fig.update_traces(hovertemplate='<b>%{y}</b><br>$%{x:,.0f}<extra></extra>')
# Para barras verticales:
fig.update_traces(hovertemplate='<b>%{x}</b><br>$%{y:,.0f}<extra></extra>')
```

### P3 — POLISH (detalles finales)
**6. Línea Dashboard → área rellena** — cambiar tipo de línea en el gráfico de tendencia de gastos:
```python
fig.update_traces(fill='tozeroy',
                  fillcolor='rgba(20,184,166,0.10)',
                  line=dict(color='#14b8a6', width=2))
```

**7. Plotly layout global oscuro** — aplicar en `charts.py` como función helper:
```python
def apply_dark_theme(fig):
    fig.update_layout(
        paper_bgcolor='#111d2e',
        plot_bgcolor='#0c1422',
        font=dict(color='#94a3b8', size=12),
        xaxis=dict(gridcolor='#1e2d45', zerolinecolor='#1e2d45'),
        yaxis=dict(gridcolor='#1e2d45', zerolinecolor='#1e2d45'),
        margin=dict(l=10, r=10, t=30, b=10),
        legend=dict(bgcolor='#111d2e', bordercolor='#1e2d45', borderwidth=0.5)
    )
    return fig
```

## MÓDULO 9 — EAN Descarga Derco (ean_descarga.py v1.1)
- **Validado:** ✅ 2026-03-20 — 36,7 MB en ~19 segundos
- **URL:** `https://egakatwms.cl/sglwms_EGA_prod/hcodbarra.aspx`
- **Depósito sesión:** QUILICURA | **Empresa:** DERCO
- **Selector empresa:** `select[name='vEMPRESA']` label="DERCO" (NO `W0061EMPRESA`)
- **Buscar:** `input[name='SEARCHBUTTON']`
- **Excel:** `img#W0061SALIDAEXCEL` (fallback JS click en `<a>` padre)
- **Descarga:** rápida (~6s) — no requiere espera larga como maestro_articulos
- **Destino:** `C:\Users\Socrates Cabral\Grupo Planet SpA\José Caceres - Maestro EAN\`
- **Nombre archivo WMS:** `Codigo+de+Barras{TIMESTAMP}.XLS`
- **Integrado en:** `maestro_articulos_derco.py` — corre después del Maestro Artículos
- **Requerido:** click en "Procesos WMS" tras login antes de goto hcodbarra.aspx

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

---

# PROYECTO 3 — Agente de Apuestas Deportivas
Última actualización: 2026-03-23

## Contexto
Agente Python de análisis estadístico deportivo para identificar value bets.
Construido en sprints. Diseño en Claude.ai → implementación en Claude Code.
**Carpeta del proyecto:** `C:\ClaudeWork\agente_apuestas\` ✅ (migrado desde `files/` el 2026-03-22)
**Archivos originales en `files/`:** mantener como backup, NO usar para ejecutar

## APIs configuradas (.env)
| Variable          | Servicio             | Límite gratuito          |
|-------------------|----------------------|--------------------------|
| `API_SPORTS_KEY`  | api-sports.io        | 100 req/día por API      |
| `ODDS_API_KEY`    | the-odds-api.com     | 500 créditos/mes         |
| `BALLDONTLIE_KEY` | balldontlie.io       | Tier gratuito disponible |
| `SPORTMONKS_KEY`  | sportmonks.com       | Free forever (ligas limitadas) |

TheSportsDB V1 no requiere key (`/api/v1/json/123/`). V2 usa header `X-API-KEY`.

## Estructura de carpetas (flat — igual que otros proyectos)
```
C:\ClaudeWork\agente_apuestas\          ← Carpeta raíz del proyecto ✅
├── config.py                           ← Keys, URLs, IDs de ligas, thresholds
├── run_agent.py                        ← Orquestador principal ✅ Sprint 4
├── fixtures_collector.py               ← Partidos del día fútbol + basketball ✅ Sprint 1
├── lineup_collector.py                 ← Equipos probables + lesiones ✅ Sprint 1
├── stats_collector.py                  ← H2H + forma + stats temporada ✅ Sprint 2
├── predictions_collector.py            ← Predicciones + Poisson api-sports ✅ Sprint 2
├── odds_collector.py                   ← Cuotas tiempo real The Odds API ✅ Sprint 2
├── value_detector.py                   ← Detecta value bets por mercado ✅ Sprint 3
├── bet_recommender.py                  ← Clasifica tipo de apuesta óptima ✅ Sprint 3
├── confidence_scorer.py                ← Score final 0-100 por partido ✅ Sprint 3
├── claude_agent.py                     ← Narrativa Claude + reporte HTML ✅ Sprint 4
├── telegram_bot.py                     ← 6 funciones Telegram ✅ Sprint 4
├── nombre_normalizer.py                ← Aliases football-data ↔ Understat ✅ Sprint 9
├── backtesting\
│   ├── simulador.py                    ← Apuestas virtuales con bankroll ✅ Sprint 5
│   ├── resultado_checker.py            ← Verifica resultado real vs predicción ✅ Sprint 5
│   ├── reporte_performance.py          ← Dashboard precisión + ROI ✅ Sprint 5
│   ├── run_backtesting.py              ← Orquestador nocturno (Task Scheduler 23:00) ✅ Sprint 5
│   └── historico_apuestas.json         ← Se crea automáticamente al primer registro
├── entrenamiento\                      ← Pipeline ML XGBoost ✅ Sprint 7-9
│   ├── descargador_historico.py        ← football-data.co.uk → CSV por liga/temporada
│   ├── xg_collector.py                 ← Understat xG por liga/temporada (con cache)
│   ├── transfermarkt_collector.py      ← Valor plantilla Transfermarkt (cache 30d)
│   ├── nombre_normalizer.py            ← Normaliza nombres equipos entre fuentes
│   ├── feature_builder.py              ← Pi-Rating + forma + xG + Transfermarkt
│   ├── entrenador.py                   ← XGBoost + TimeSeriesSplit + joblib
│   ├── evaluador.py                    ← Grid ROI por umbral/value + reporte por liga
│   └── run_entrenamiento.py            ← Orquestador pipeline completo
├── aprendizaje\                        ← Autolearning del historial ⏳ Sprint 6
│   └── run_aprendizaje.py              ← Analiza historico_apuestas.json, ajusta thresholds
├── datos_historicos\
│   ├── raw\                            ← fd_*.csv (football-data) + understat_xg_*.csv
│   └── procesados\                     ← features_dataset.csv
├── modelos\
│   ├── xgb_model.joblib                ← Modelo entrenado ✅
│   └── metricas_entrenamiento.json     ← CV accuracy, log_loss, top features
└── output\                             ← Reportes HTML diarios
```

## Estado de sprints
| Sprint | Módulos | Estado |
|--------|---------|--------|
| 1 | `fixtures_collector.py` + `lineup_collector.py` + `config.py` | ✅ Validado (2026-03-22) |
| 2 | `stats_collector.py` v2.0 + basketball NBA + `predictions_collector.py` + `odds_collector.py` | ✅ v2.0 (2026-03-22) |
| 3 | `value_detector.py` + ensemble + steam move + `bet_recommender.py` + `confidence_scorer.py` | ✅ v2 (2026-03-22) |
| 4 | `claude_agent.py` + bloque riesgo HTML + `run_agent.py` + stop-loss + Telegram | ✅ v2 (2026-03-22) |
| 5 | `simulador.py` + `resultado_checker.py` + `reporte_performance.py` + `run_backtesting.py` | ✅ Código generado (2026-03-22) — en `backtesting\` |
| 6 | `aprendizaje\run_aprendizaje.py` — autolearning historial → ajusta thresholds | ⏳ Pendiente (prerequisito: 30+ partidos con resultado) |
| 7 | `entrenamiento\` — XGBoost + Pi-Rating + xG Understat + Transfermarkt + TimeSeriesSplit | ✅ Pipeline completo (2026-03-23) |
| 8 | Fixes: leakage B365 separado de features, Understat (FBref bloqueado), nombre_normalizer | ✅ CV=0.4734, Test=0.5020 |
| 9 | Grid ROI por umbral/value, evaluador reescrito con reglas selectivas, ROI por liga | ✅ ROI +10.79% Serie A activa (umbral=0.70, value=0.10) |
| 10 | predictor_tiempo_real.py + test + run_agent ML branch + Telegram fuente_prediccion | ✅ COMPLETO (2026-03-24) |

## Arquitectura Sprint 5 — Backtesting
```
HOY (antes del partido)          DESPUÉS DEL PARTIDO (estado FT/AET/PEN)
────────────────────────         ───────────────────────────────────────
simulador.py                     resultado_checker.py
  registrar_apuesta(rec, flat)   → consulta api-sports /fixtures?id=
  → historico_apuestas.json      → evaluar_apuesta(tipo, seleccion, goles)
    {resultado_real: null}       → actualiza ganado/retorno en JSON
                                 ↓
                                 reporte_performance.py
                                 → precision/ROI/yield por tipo
                                 → bankroll chart + calibración Plotly
                                 → HTML dark theme #0c1422 / teal #14b8a6
```
**Bankroll:** $100.000 CLP inicial | Flat: $5.000/apuesta | Kelly: Quarter Kelly, cap 10%
**Tipos de apuesta soportados:** 1X2, BTTS, OVER_UNDER, DOUBLE_CHANCE
**Task Scheduler sugerido:** 23:00 diario → `py agente_apuestas\backtesting\run_backtesting.py`
**Lanzadores escritorio:** `Agente Apuestas.lnk` + `Ver Performance.lnk` → `agente_apuestas\`

## Ligas configuradas (IDs estables api-sports.io)
**Fútbol:** Premier League=39, La Liga=140, Champions League=2,
Ligue 1=61, Serie A=135, Bundesliga=78, Primera División CL=265, Copa Libertadores=13
**Basketball:** NBA=12, Euroliga=120

## Tipos de apuesta por deporte
**Fútbol:** 1X2, DOUBLE_CHANCE, BTTS, OVER_UNDER, ASIAN_HC, HALF_TIME
**Basketball:** MONEYLINE, SPREAD, TOTAL, HALF_LINE

## Lógica core: Value Betting
```python
value = (prob_modelo * cuota_bookmaker) - 1
es_value_bet = value > 0.05   # umbral mínimo: +5%
```
El agente NO predice ganadores — detecta partidos donde la probabilidad
del modelo supera la probabilidad implícita en la cuota del bookmaker.

## Sprint 5 — Backtesting: diseño detallado

### simulador.py
- Recibe recomendaciones del agente (output Sprint 3)
- Simula apuesta con bankroll virtual configurable (default $100.000 CLP)
- Dos estrategias paralelas: flat betting (monto fijo) Y Kelly Criterion
- Guarda cada apuesta en `historico_apuestas.json`:
```json
{
  "fixture_id": 123456,
  "fecha": "2026-03-22",
  "deporte": "futbol",
  "liga": "Premier League",
  "home": "Arsenal",
  "away": "Chelsea",
  "tipo_apuesta": "BTTS",
  "seleccion": "Si",
  "cuota": 1.75,
  "prob_modelo": 0.64,
  "value": 0.12,
  "monto_flat": 5000,
  "monto_kelly": 3200,
  "resultado_predicho": "Si",
  "resultado_real": null,
  "ganado": null,
  "retorno_flat": null,
  "retorno_kelly": null,
  "score_final": null,
  "ts_registro": "2026-03-22T18:30:00"
}
```

### resultado_checker.py
- Corre una vez al día (23:00 via Task Scheduler, Task: "Agente Apuestas - Backtesting")
- Lee `historico_apuestas.json`, filtra entradas con `resultado_real: null`
- Para cada apuesta pendiente: consulta `api-sports /fixtures?id=fixture_id`
- Si estado == "FT": extrae score, evalúa si la apuesta ganó, llena todos los campos null
- Lógica de evaluación por tipo:
  - 1X2/MONEYLINE: compara ganador predicho vs ganador real
  - BTTS: verifica si ambos equipos anotaron (score_home > 0 AND score_away > 0)
  - OVER_UNDER: compara total goles vs línea (ej: total > 2.5)
  - SPREAD: compara diferencia de puntos vs handicap
- Guarda JSON actualizado
- Log con prefijo [OK]/[FALLO] compatible con run_todos.py

### reporte_performance.py
- Lee `historico_apuestas.json` (solo entradas con resultado_real != null)
- Calcula métricas:
  - Precisión global y por tipo de apuesta
  - ROI por tipo: `(ganado - apostado) / apostado * 100`
  - Yield: `% ganancia promedio por apuesta`
  - Evolución bankroll flat vs Kelly en el tiempo
  - Calibración del modelo: cuando predice 60%, ¿ocurre ~60% de las veces?
  - Mejor y peor racha de aciertos/fallos consecutivos
  - Value hit rate: % de value_bets que efectivamente ganaron
- Genera reporte HTML con Plotly
- Estética heredada de finanzas_personales: fondo #0c1422, teal #14b8a6, COLOR_MAP

### run_backtesting.py
- Orquestador: resultado_checker → reporte_performance → guarda HTML en output/
- Compatible con Task Scheduler (23:00 L-V)
- Log centralizado en `C:\ClaudeWork\logs\backtesting_YYYY-MM-DD.log`

### Métricas clave del modelo
```python
METRICAS = {
    "precision_1X2":        "% aciertos resultado final",
    "precision_btts":       "% aciertos ambos anotan",
    "precision_over_under": "% aciertos total goles",
    "roi_por_tipo":         "(ganado - apostado) / apostado * 100",
    "yield":                "% ganancia promedio por apuesta (benchmark: >5% = muy bueno)",
    "calibracion":          "cuando digo 70%, ocurre el 70% de las veces?",
    "value_hit_rate":       "% value_bets que ganaron",
    "bankroll_ev":          "evolucion bankroll flat vs Kelly en el tiempo",
}
```

## Resultados ML y parámetros de producción

### Modelo activo (Sprint 9)
| Métrica | Valor |
|---------|-------|
| CV accuracy (5-fold TimeSeriesSplit) | 0.4729 ± 0.0248 |
| Test accuracy (20% cronológico) | 0.5036 |
| Features totales | 16 |
| Top features | pi_exp_home, pi_exp_away, pi_diff, pi_diff_abs, pi_rating_home |

### Parámetros producción
| Parámetro | Valor |
|-----------|-------|
| `UMBRAL_CONFIANZA` | 0.70 |
| `VALUE_MIN` | 0.10 |
| Archivo modelo | `modelos/xgb_model.joblib` |

### ROI por liga (umbral=0.70) — DESPUÉS de fixes (reentrenado 2026-03-23)
| Liga | N apuestas | Accuracy | ROI | Estado |
|------|------------|----------|-----|--------|
| Serie A | 23 | 82.6% | **+31.65%** | **ACTIVA** ✓ |
| La Liga | 9 | 88.9% | +25.44% | suspendida (n < 20) |
| Bundesliga | 16 | 75.0% | +9.69% | suspendida (n < 20) |
| Premier League | 15 | 66.7% | -4.27% | suspendida |
| Ligue 1 | 11 | 36.4% | -44.82% | suspendida |

Mejor combinación global: umbral=0.75, value=0.08 → ROI flat +7.50%, 74 apuestas

### Tabla comparativa Sprint 9 → fixes
| Métrica | Sprint 9 | Post-fixes |
|---------|----------|------------|
| CV accuracy | 0.4729 | **0.4888** |
| Test accuracy | 0.5036 | **0.5226** |
| ROI Serie A | +10.79% | **+31.65%** |
| Partidos xG | 1,752 | **10,707** |

Top features post-fix: `pi_exp_home`, `pi_diff`, `pi_exp_away`, `xg_temporada_home`, `xg_temporada_away`

### xG Status
- 2019-2024: ✅ 10,707 partidos (5 ligas × 6 temporadas) en `raw/understat_xg_*.csv`

### Transfermarkt Status
- Cache 30 días en `datos_historicos/transfermarkt_cache.json`
- Fix B integrado: `get_valor_plantilla()` llamado directamente en `build_features_partido()`
- Features agregadas: `valor_home_mill`, `valor_away_mill`, `ratio_valor`, `log_ratio_valor`, `diff_valor_mill`
- Si equipo no está en `TRANSFERMARKT_IDS` → features=None, pipeline continúa ([WARN])

### Criterio de expansión de ligas
- Activar liga cuando n_apuestas (umbral=0.70) ≥ 20 Y ROI > 0
- La Liga está a 6 apuestas del umbral mínimo

## Sprint 10 COMPLETO ✅ (2026-03-24)
Archivos creados/modificados:
- `predictor_tiempo_real.py` — función `predecir_partidos_hoy()` (408 líneas)
- `run_agent.py` — rama ML integrada (Paso 3b, líneas 794-853)
- `telegram_bot.py` — campo `fuente_prediccion` con header/footer diferenciado
- `modelos/feature_columns.json` — 35 columnas del modelo
- `modelos/pi_ratings_actuales.json` — 29 equipos Serie A, 1900 partidos base
- `test_sprint10.py` — validación end-to-end (6/6 ✅)
- `Iniciar_Sprint10.bat` — lanzador con reporte automático

Validación `py test_sprint10.py` — 2026-03-24:
- Modelo ✅ | Features ✅ (35) | Pi-Ratings ✅ (29 equipos)
- Predictor ✅ | Formato ✅ | Telegram ✅
- Pi-Ratings top 5: Inter 1.43, Milan 1.10, Atalanta 0.92, Napoli 0.75, Juve 0.62

Flujo producción (Task Scheduler 08:00 L-V):
  `py run_agent.py` → Paso 3b: `predecir_partidos_hoy()` → Telegram ML card → registra en historico_apuestas.json

Task Scheduler (documentado, NO creado):
  Nombre: "Agente Apuestas - Prediccion Diaria"
  Script: C:\ClaudeWork\agente_apuestas\run_agent.py
  Hora: 08:00 L-V | Ejecutable: ruta completa python.exe

## Reglas del agente (heredadas de ClaudeWork)
1. `py` y `py -m pip` siempre
2. `.env` con `parent.parent` desde subcarpetas
3. `sys.stdout.reconfigure(encoding="utf-8")` en cada script
4. Nunca eliminar código — comentar con `#`
5. `if __name__ == "__main__"` en cada módulo para test individual
6. Logs con prefijo `[OK]`, `[FALLO]`, `[INFO]` — compatible con `run_todos.py`
7. `check_quota()` antes de secuencias de llamadas — límite 100 req/día api-sports
8. `historico_apuestas.json` es la fuente de verdad del backtesting — nunca eliminar entradas, solo actualizar campos null


## Casa de apuestas: Betano Chile
URL: https://lat.betano.com/
Moneda: CLP (pesos chilenos)
Contexto: Todas las apuestas reales se ejecutan manualmente en Betano Chile.
El agente recomienda — el usuario decide y apuesta en Betano.

### Mapeo de mercados internos → nombre en Betano Chile
| Nombre interno agente | Nombre en Betano Chile         |
|-----------------------|-------------------------------|
| 1X2                   | 1X2                            |
| DOUBLE_CHANCE         | Doble Oportunidad              |
| BTTS                  | Ambos Equipos Marcan           |
| OVER_UNDER            | Más/Menos [línea] Goles        |
| ASIAN_HC              | Hándicap Asiático              |
| HALF_TIME             | Resultado al Descanso          |
| MONEYLINE             | Ganador del Partido            |
| SPREAD                | Hándicap                       |
| TOTAL                 | Total Puntos Más/Menos         |

### Sección "Simulación de Retorno" en reporte HTML (Sprint 4)
Agregada a cada apuesta recomendada en el reporte HTML generado por claude_agent.py.
Funciona con JavaScript inline (sin dependencias externas — archivo HTML autocontenido).
Campos interactivos:
- Input monto a apostar (CLP)
- Slider bankroll (default $200.000, min $50.000, max $2.000.000, paso $50.000)
- Cálculo en tiempo real: ganancia neta, retorno total, pérdida, monto Kelly
- Semáforo value: verde >10%, amarillo 5-10%, rojo <5%
Estética: fondo #0c1422, teal #14b8a6, borde #1e2d45
