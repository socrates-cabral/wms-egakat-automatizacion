# Wiki Log — ClaudeWork
Registro cronológico append-only. Formato: `## [YYYY-MM-DD] tipo | Título`

---

## [2026-05-15] update | FillRate — rename histórico columna y reconciliación Quilicura

**Tipo:** Hallazgo + reconciliación manual

**Páginas actualizadas:**
- wiki/proyectos/fillrate-automatizacion.md (sección "Hallazgo: rename histórico columna fecha" + "Filas vacías masivas")

**Hallazgos:**
- `Fecha y hora de Generación` (WMS bruto) = `Fecha y hora de Ingreso` (procesado). Mismo dato, nombre cambiado en algún momento — canónico debería ser "Generación".
- Filas vacías intercaladas masivas en `data Runo Tradicional.xlsx` (1042 huérfanas + 729 vacías de 1855) y `data Derco.xlsx` (~35.226 de 69.975). Trim de fillrate solo borra trailing, no intermedias.
- Reconciliación Quilicura vs WMS: Pochteca -16, Cervecería ABI -7, Daikin -4, Mascotas Latinas -1, Derco +2 (Aplica 196099 y 196119 del 12-may, anulados después de corrida previa).

**Memoria guardada:** `project_fillrate_columna_generacion.md`

---

## [2026-05-01] ingest | Code Review Bots Telegram Codex

**Tipo:** Revisión código (calidad, seguridad, optimización)  
**Fuente:** REVISION_CODIGO_CODEX_2026-05-01.md (37 KB)  
**Páginas creadas:**
- wiki/decisiones/code-review-bots-telegram.md

**Páginas actualizadas:**
- wiki/index.md (+1 entrada decisiones técnicas)

**Archivos revisados (18):**
- Softnet_Ventas/bots: db_manager, alertas_engine, claude_agent, telegram_utils, sp_reader, run_alertas, run_reporte_semanal, webhook_handler, admin_clientes, diagnostico_telegram, api_cobranza
- Softnet_Ventas/bots/agents: orquestador, agente_general, agente_cliente, agente_cobranza
- WMS_Automatizacion/bots: _write_wf_ops
- Productividad_Automatizacion: productividad_diario
- WMS_Automatizacion: run_todos

**Veredicto:** ✅ Seguro en producción con optimizaciones recomendadas

**Hallazgos críticos (2):**
1. Validación checkpoint obsoleto productividad_diario — si >30 días sin ejecutar → descarga ventana gigante → timeout WMS
2. Rate limiting incompleto telegram_utils — solo reactivo 429, no preventivo (límite 20 msg/min/chat)

**Hallazgos altos (5):**
3. Connection pool SQLite — 150+ conexiones innecesarias por ejecución → +750ms overhead
4. Sin cache SharePoint — 2-5s latencia evitables, respuesta bot 6s → objetivo <2s
5. Claude agent lazy init no thread-safe — race condition con n8n webhooks paralelos
6. Historial sin límite agente_cobranza — prompts 8K+ tokens → 4x costo LLM
7. Playwright headless hardcoded — debugging difícil en servidor

**Positivos:**
- ✅ XSS prevention (html.escape en plantilla_correo)
- ✅ SQL injection safe (queries parametrizadas)
- ✅ Secrets en .env, no hardcodeados
- ✅ Separación bot interno/cliente clara
- ✅ Error handling exhaustivo
- ✅ OneDrive portable (ONEDRIVE_ROOT)

**Decisiones arquitectónicas documentadas:**
- Multi-LLM fallback (Claude → OpenAI → Gemini): redundancia ante rate limits
- SQLite historial: <10K msg/mes, simplicidad operacional vs Redis/PostgreSQL
- SharePoint como fuente verdad: evita source of truth conflict vs DB intermedia
- Aislamiento cliente por RUT: filtro DF aceptable <100 clientes, revisar si >500

**Memory actualizada:**
- feedback_code_review_codex.md (nuevo)
- MEMORY.md (índice actualizado)

**Git commit:** eb75296

---

## [2026-04-30] proyecto | Sistema Limpieza Automatizada + Fixes WMS/Softnet

**Tipo:** Nuevo sistema mantenimiento + fixes producción  
**Archivos creados:**
- scripts/cleanup_automatico.bat — Script principal limpieza (4.3 KB)
- scripts/crear_tarea_cleanup.bat — Task Scheduler mensual (1.3 KB)
- scripts/verificar_tarea_cleanup.bat — Verificación estado tarea (590 bytes)
- scripts/eliminar_tarea_cleanup.bat — Eliminación tarea con confirmación (1.1 KB)
- scripts/README_cleanup.md — Documentación completa (3.0 KB)
- limpiar_cache.bat — Quick cleanup solo cache Python (raíz repo)

**Archivos modificados:**
- wms_despacho/despacho.py — Eliminado filtro DERCO-only, procesa TODOS los viajes
- Softnet_Ventas/src/plantilla_correo.py — Fix columna "Monto" → "Saldo" en facturas alto monto
- .gitignore — Agregados patrones cleanup (chunks, paths corruptos, logs/cleanup/)

**Propósito:** Mantener repo limpio sin riesgo de borrar código/datos críticos. Fixes operacionales en producción.

### 1. Sistema de limpieza automatizada

**Eliminación inicial (2.7 GB):**
- _instaladores/ (1.7 GB): Claude Setup, Codex Installer, Ollama — ya instalados
- Productividad_Automatizacion/logs/downloads/ (1.0 GB): 262 chunks MovDerco
- C:ClaudeWorktemp_movderco.xlsx (22 MB): Path corrupto Windows
- __pycache__/ y *.pyc (3.3 MB): 36 carpetas, 176 archivos bytecode
- agente_apuestas/output/: 23 reportes HTML antiguos (marzo-abril)

**Qué elimina (safe):**
- Cache Python regenerable (__pycache__, *.pyc)
- Logs >30 días (logs/*.log)
- Outputs temporales >15 días (agente_apuestas, crypto_bot)
- Chunks procesamiento (*_chunk_*.xlsx)
- Archivos corruptos (C:ClaudeWork*)
- Temporales Office (.tmp, .bak, ~$*)

**Qué NO elimina (garantizado):**
- ✅ Código fuente (.py, .ps1, .bat, .json, .md)
- ✅ Configuraciones (.env)
- ✅ Checkpoints (fillrate_checkpoint.json, productividad_checkpoint.json)
- ✅ Bases de datos SQLite
- ✅ Scripts Task Scheduler
- ✅ Logs recientes (<30 días)
- ✅ Outputs recientes (<15 días)

**Task Scheduler:**
- Nombre: "ClaudeWork - Limpieza Automatica Mensual"
- Frecuencia: 1er día del mes 02:00 AM
- Usuario: SYSTEM, privilegios HIGHEST
- Logs: logs/cleanup/cleanup_YYYYMMDD_HHMMSS.log

**Estado:** ✅ Creada y ejecutada 2026-04-30 22:15. Próxima ejecución 2026-05-01 02:00.

### 2. WMS Despacho — Procesar TODOS los viajes (no solo DERCO)

**ANTES:** Filtro manual `span#span_vEMPDSC_0001` → solo procesaba viajes de DERCO  
**AHORA:** Eliminado filtro empresa (líneas 267-271) → procesa TODOS los viajes disponibles

**Razón:** Módulo 11 RF muestra viajes de todas las empresas en la misma ventana (no tiene filtro nativo). El parámetro `--empresa` solo se usa para navegación inicial en menú RF.

**Impacto:** De 2-5 viajes/día (solo DERCO) → potencialmente 10-30 viajes/día (todas las empresas).

**Commit:** a722a9b

### 3. Softnet Ventas — Fix columna "Saldo" en email

**ANTES:** Sección "Facturas de alto monto sin pagar" mostraba columna "Monto" (monto_total completo)  
**AHORA:** Columna "Saldo" (deuda pendiente real)

**Razón:** Evitar confusión — usuarios leían monto total factura y asumían deuda completa cuando ya se habían hecho pagos parciales.

**Cambio:** `plantilla_correo.py` líneas 343 (valor) y 355 (header tabla).

**Commit:** a722a9b

---

**Memory actualizada:**
- project_cleanup_automation.md (nuevo)
- project_wms_despacho.md (actualizado — cambio 2026-04-30)
- project_softnet_ventas.md (actualizado — fix email template)
- MEMORY.md (índice actualizado)

**Wiki actualizada:**
- log.md (esta entrada)
- index.md (pendiente agregar cleanup automation)

**Git commit:** a722a9b — "feat+fix: cleanup automation + WMS despacho all-trips + Softnet Ventas saldo fix"

---

## [2026-04-29] ingest | KPI Operativo + Bot Ops — Scripts completados con Codex

**Tipo:** Nuevos scripts (Codex OpenAI)  
**Archivos creados:**
- WMS_Automatizacion/generar_resumen_kpi_ops.py — Resumen JSON KPIs operativos (184 KB, 4524 líneas)
- WMS_Automatizacion/bots/_write_wf_ops.py — Generador config workflow n8n bot ops (15 KB)

**Propósito:** Alimentar @EgakatOpsBot (Telegram) con contexto operacional actualizado.

**Arquitectura:**
```
generar_resumen_kpi_ops.py
  └─ Lee 9 carpetas OneDrive (NNSS, Productividad, Inventario, Stock WMS, Staging, Posiciones, Conteos)
  └─ Genera tmp_resumen_kpi_ops_YYYYMMDD.json
       └─ n8n workflow → @EgakatOpsBot (Telegram)
```

**Decisión técnica:** Mantener OneDrive Desktop para lectura carpetas compartidas externas (Grupo Planet SpA). Graph API no factible (permisos delegados, no application permissions). Solo lectura, sin problema sincronización.

**Estado proyecto bot ops:** Actualizado de ❌ BLOQUEADO → ⏳ EN PROGRESO. Scripts completados, pendiente integración n8n.

**Memory actualizada:**
- project_kpi_ops.md (nuevo)
- project_bot_ops_bloqueado.md (actualizado)

**Wiki pendiente:** Crear proyectos/bot-ops-egakat.md

---

## [2026-04-29] proyecto | Servidor Egakat 24/7 — Plan de Migración

**Tipo:** Nuevo proyecto (planificación infraestructura)  
**Archivos creados:**
- wiki/proyectos/servidor_egakat_24x7.md — Plan completo migración (40 KB)
- Documentos/Guia_Migracion_Servidor_Egakat.md — Guía paso a paso lenguaje sencillo (37 KB)
- Documentos/Checklist_Migracion_Servidor.md — Checklist imprimible migración (8 KB)

**Páginas actualizadas:**
- wiki/index.md (+1 entrada proyectos)

**Decisión técnica:** Mini PC (Lenovo ThinkCentre M75q Gen 2) sobre VPS Cloud. Razones: OneDrive sync nativo, ROI 6 meses vs VPS, latencia debugging, control total hardware.

**Inventario automatizaciones:**
- ✅ Al servidor: WMS, Softnet, VDR, NPS, Productividad, FillRate, agente_apuestas, crypto_bot, n8n, APIs Flask (10+ Task Scheduler tasks)
- ❌ En laptop: HackeaMetabolismo, Finanzas_Personales, InversionesIA, NutriMetab_BI (proyectos personales)

**Presupuesto:** USD 720 (Mini PC USD 600 + UPS USD 100 + accesorios USD 20)

**Timeline:** 7 fases, 6 días de trabajo (1-2h diarias), validación 48h antes de producción

**Entregables:**
1. Arquitectura servidor (requisitos HW/SW, dependencias críticas)
2. Comparativa hardware (Mini PC vs PC Torre vs VPS, TCO 3 años)
3. Guía instalación 7 fases (Windows, software base, migración código, OneDrive, n8n, Task Scheduler, pruebas)
4. Checklist validación post-migración (50+ items)
5. Troubleshooting común (8 problemas típicos)

**Estado:** Planificación — pendiente compra hardware

---

## [2026-04-29] ingest | Agente Apuestas — re-entrenamiento post-fixes + ajuste parámetros

Re-entrenamiento XGBoost tras fixes lambda floor bug. Dataset 9,629 partidos, accuracy 52.02%. Grid ROI validó umbral 0.60 = +9.82% ROI (n=11). Ajustes: MIN_CONFIDENCE 65→60, umbrales liga 0.75→0.65. Modelo listo para paper trading fin de semana. Wiki: [[proyectos/agente-apuestas-fixes-2026-04-29]]. Commit 124a572.

---

## [2026-04-29] ingest | FillRate — bug latente checkpoint datetime→string resuelto

Bug introducido cdfff18 (15 abril), manifestado hoy tras VS Code reinicio. Checkpoint JSON serializa `datetime.date` como string via `default=str`, pero `build_summary_html` esperaba objeto date. Fix bac0c76: detección tipo runtime antes de `.strftime()`. Sistema ahora robusto ante interrupciones + reintentos mismo día. Página wiki: [[decisiones/fillrate-checkpoint-serialization]].

---

## [2026-04-25] ingest | Agente Apuestas — Bundesliga + Ligue 1 activadas, Sprint 20 confirmado

Bundesliga (1530 pts) y Ligue 1 (1725 pts) activadas para acelerar n=50.
Sprint 20 features L5 ya estaban en el modelo. n=50 estimado junio 2026.

---

## [2026-04-24] ingest | Agente Apuestas — fixes calibración + API key

Poisson cap 0.95→0.75, bloqueo Under en knockout, resultado_real corregido.
API Anthropic renovada. Crypto bot: +$30.33 USDT (+3.03%) BTC+ETH combinado.

---

## [2026-04-24] ingest | Softnet Ventas — nuevo proyecto en producción

Pipeline completo Softnet ERP → SharePoint. Playwright headless, Graph API, correo HTML con CxC/vencidas/alto monto/pagos. Task Scheduler L-V 16:00. MODO_TEST=false activado.

---

## [2026-04-21] ingest | Productividad — 17 clientes, backup eliminado, diario en producción

productividad_diario.py operativo (TESTING_MODE=True). 17 clientes (+ NATIVO DRINKS SPA + OMNITECH).
Fechas históricas en MM/DD corregidas manualmente. WMS usa DD-MM-YYYY con guiones.
Backup SharePoint eliminado de ambos scripts + carpeta _backups borrada.
productividad_descarga.py sigue activo para reprocesos manuales.

## [2026-04-17] ingest | Crypto Bot operativo + fixes agente apuestas sesgo Under

Crypto Bot Grid Trading BTC_USDT implementado y corriendo en Task Scheduler.
Rango ajustado $65K-$85K, EMA filter desactivado en paper, Telegram activo.
Agente apuestas: 3 fixes sesgo Under (lambda_sospechoso, under_irreal, diversidad).
Resultado Inter 3-0 Cagliari → Under 2.25 perdida. Histórico: 1/6 (16.7%).

## [2026-04-09] ingest | Inicialización wiki desde MEMORY.md
Fuente: MEMORY.md (estado al 2026-03-28)
Páginas creadas: index.md con 25 entradas en 7 categorías
Proyectos indexados: WMS Egakat, Agente Apuestas, Finanzas Personales, Chiquito, Hackea Metabolismo
Conceptos indexados: value-betting, pi-rating, xG, Kelly, XGBoost, data-leakage
Entidades indexadas: api-sports, Understat, Transfermarkt, The Odds API, Betano, Graph API
Decisiones indexadas: flat-structure, haiku-modelo, paper-trading, graph-api, py-command
Notas: Primera compilación. Wiki vacía → base inicial. Próximo paso: crear páginas individuales por concepto.

---

## [2026-04-09] pendiente | Modelo XGBoost — features Corners/BTTS desde odds-api.io
Origen: odds-api.io v3 entrega Corners Totals, Corners Spread y BTTS por partido en tiempo real.
Tarea: buscar fuente histórica de resultados corners/BTTS (candidato: football-data.co.uk CSVs ya integrados).
Cruzar cuota BTTS/Corners pre-partido con resultado real → nuevas features para XGBoost.
Bloqueante: football-data.co.uk tiene columnas HC/AC (home/away corners) y BTTS implícito en goles — verificar.
Sprint sugerido: S20+ (después de que La Liga/Bundesliga alcancen n≥20).

---

## [2026-04-09] ingest | run_todos.py — Orquestador WMS Egakat
Fuente: WMS_Automatizacion/run_todos.py (leído directo desde codebase)
Páginas creadas: wiki/proyectos/wms-run-todos.md
Páginas actualizadas: wiki/index.md (+1 entrada)
Notas: v2.2. 6 módulos operativos + Módulo 9 validación. Patrones: lock, checkpoint diario, bridge pointer (spec/09 crash recovery), retry 60s, Graph API + Outlook fallback. Módulo 9 no bloquea estado global.

---

## [2026-04-09] ingest | run_agent.py — Orquestador Agente Apuestas
Fuente: agente_apuestas/run_agent.py (leído directo desde codebase — aún no en raw/)
Páginas creadas: wiki/proyectos/agente-apuestas-orquestador.md
Páginas actualizadas: wiki/index.md (+1 entrada)
Notas: Sprint 19 en curso. Módulos opcionales NBA/MLB/FootyStats con graceful import. Stop-loss diario 15%, semanal 25%. MODO_PAPER_TRADING=True activo.

---

## [2026-04-11] ingest | FillRate_Automatizacion — Proyecto nuevo (OpenAI Codex)
Fuente: FillRate_Automatizacion/*.py (leído directo desde codebase)
Páginas creadas: wiki/proyectos/fillrate-automatizacion.md
Páginas actualizadas: wiki/index.md (+1 entrada)
Notas: Proyecto generado con OpenAI Codex. 13 clientes activos, Graph API SharePoint. Fixes aplicados: lock file, temp cleanup, retries 1→3, .codex/ eliminado. Independiente de run_todos.py.

---

## [2026-04-11] ingest | run_todos.py v2.2 — Verificación bugs resueltos
Fuente: WMS_Automatizacion/run_todos.py (leído directo desde codebase)
Páginas actualizadas: wiki/proyectos/wms-run-todos.md (fecha + tabla bugs v2.2)
Notas: Confirmado que los 4 bugs documentados en run_todos_issues.md están todos resueltos en v2.2. El archivo run_todos_issues.md en memory fue eliminado (info obsoleta). El wiki ya tenía la página correcta del orquestador desde 2026-04-09.

---

## [2026-04-12] decision | Roadmap ML Sprints 20-22 + Task Scheduler agente apuestas
Páginas creadas: wiki/decisiones/decision-ml-roadmap-sprints20-22.md
Páginas actualizadas: wiki/index.md (+1 entrada decisiones)
Memorias actualizadas: project_agente_apuestas.md (Task Scheduler 5 tareas + roadmap S20-22)
Notas: S20 forma reciente sin prerequisito. S21/S22 requieren n≥50. api-sports Pro: esperar validación modelo.

---

## [2026-04-12] ingest | 3 proyectos core Egakat al wiki
Fuente: código fuente directo (NPS_Encuesta/, VDR_Comparador/, WMS_Automatizacion/)
Páginas creadas:
  - wiki/proyectos/nps-encuesta.md
  - wiki/proyectos/vdr-comparador.md
  - wiki/proyectos/wms-automatizacion.md
Páginas actualizadas: wiki/index.md (+3 entradas)
Notas: VDR es el único módulo sin Graph API (OneDrive sync + PA). NPS importa azure_graph desde WMS_Automatizacion. WMS página de proyecto completo (wms-run-todos.md cubre solo el orquestador).

---

## [2026-04-12] ingest | 5 proyectos nuevos al wiki
Fuente: MEMORY.md + lecturas directas de codebase
Páginas creadas:
  - wiki/proyectos/nutrimetab-bi.md
  - wiki/proyectos/inversiones-ia.md
  - wiki/proyectos/productividad-automatizacion.md
  - wiki/decisiones/decision-crypto-bot-grid.md
Páginas actualizadas: wiki/index.md (+4 entradas proyectos, +1 entrada decisiones)
Notas: FillRate ya tenía página (fillrate-automatizacion.md) — no se duplicó. Productividad tiene selectores WMS pendientes de runtime. Crypto bot en fase de diseño únicamente.

---

<!-- INSTRUCCIONES PARA EL LLM:
Agregar entradas con este formato al final del archivo:

## [YYYY-MM-DD] ingest | [Título del documento ingestado]
Fuente: raw/[ruta del archivo]
Páginas creadas: [lista]
Páginas actualizadas: [lista]
Notas: [observaciones relevantes]

## [YYYY-MM-DD] query | [Pregunta realizada]
Páginas leídas: [lista]
Output: [descripción del resultado — si se archivó, indicar ruta]

## [YYYY-MM-DD] lint | [Descripción del health-check]
Contradicciones: [N]
Páginas huérfanas: [N]
Páginas faltantes sugeridas: [lista]
-->
---

## [2026-05-02] fix | Bot Ops — JS historico bloqueado por periodoSolicitadoNoDisponible

**Tipo:** Bug fix lógica contexto AI  
**Archivo:** `WMS_Automatizacion/bots/_FINAL_preparar_contexto_ai.js`  
**Páginas actualizadas:**
- wiki/proyectos/kpi-ops.md (reemplazado "Problema conocido" → documentación fix)
- memory/project_bot_ops_bloqueado.md (estado FUNCIONAL PARCIAL → FUNCIONAL COMPLETO)

**Síntoma:** Consultas históricas como "OTIF DERCO en marzo", "Fill Rate de febrero" y "productividad DERCO AP YTD" devolvían solo `control_periodo` aunque `kpi_ops.historico` tenía los datos. El bloque hacía early return antes de que el agente recibiera historico.

**Causa raíz:** `periodoSolicitadoNoDisponible = true` cuando mes solicitado ≠ mes disponible (e.g., marzo ≠ abril), sin revisar si historico tenía filas para ese mes. Para YTD, `esProductividad` sobreescribía el contexto con datos del mes actual eliminando historico.

**Fix:** Función `historicoTienePeriodo()` que verifica presencia de filas en los 8 arrays del historico (otif_mensual, otif_ytd, fillrate_mensual, fillrate_ytd, mensual_cliente, ytd_cliente, derco_ap_mensual, derco_ap_ytd). Condición de bloqueo dividida: solo activa `control_periodo` si historico NO cubre; early return con historico si SÍ cubre.

---

## [2026-05-10] fix | Bot Ops — Canal_Principal en historico DERCO (MY/SG/CAP separados)

**Tipo:** Bug fix Canal_Agrupado → Canal_Principal  
**Commit:** 574657a

`Canal_Agrupado` agrupa CAP+MY+SG → "CAP-MY-SG" (diseño intencional para vista actual). El historico debe usar `Canal_Principal` para mantenerlos separados. Validado: CAP 2.430 + MY 7.347 + SG 288 = 10.065 ✓

---

## [2026-05-10] fix | Bot Ops — Desglose canales DERCO AP/MY/SG/CAP/GT + AP Rack/Estantería

**Tipo:** Bug fix detección consulta + exposición datos  
**Archivo:** `WMS_Automatizacion/bots/_FINAL_preparar_contexto_ai.js`  
**Commit:** 953f264

**Síntoma:** "separa AP, MY, SG, CAP, CES y GT" → bot sin respuesta. No detectaba intención sin keywords "canal" o "DERCO".

**Fix:** `pideDercoCanales` detecta 2+ codes de {my, sg, cap, gt, ces}, o 'ap' + 1 code, o 'ap rack'/'ap estantería'. Expone `prod.derco.canales` (AP agrupado) y `prod.derco.canales_originales` (AP_R/AP_E separados). CES no existe → bot lo indica.

**Validado:** 5/5 canales coinciden exacto con WMS. AP_R+AP_E = AP total ✓.

**Páginas actualizadas:**
- wiki/proyectos/kpi-ops.md (sección "Desglose canales DERCO")
- memory/project_bot_ops_bloqueado.md (Fix 2026-05-10)
- memory/MEMORY.md (entrada EgakatOpsBot actualizada)

---

## [2026-05-09] fix | Bot Ops — OTIF por CD + terminología WMS + PUDAHUEL UNITARIO

**Tipo:** Fixes múltiples en bot  
**Archivos:** `_FINAL_preparar_contexto_ai.js`, `generar_resumen_kpi_ops.py`, `_FINAL_system_message.txt`  
**Commits:** ver project_bot_ops_bloqueado.md

**Fixes:**
1. OTIF por CD: JS ahora expone `por_cd`, `por_cd_filtrado`, `regla_otif_por_cd` + `generar_resumen_kpi_ops.py` agrega `detalle_no_on_time`, `detalle_no_in_full`, `motivos_no_in_full` a cada CD
2. Terminología: "días trabajados" → "Días activos WMS", regla metodológica obligatoria en system prompt
3. `cdFromMsg()`: prioridad QUILICURA → PUDAHUEL UNITARIO → PUDAHUEL → SANTA ROSA (fix bug detección)

**Páginas actualizadas:**
- wiki/proyectos/kpi-ops.md (sección OTIF por CD)

---

## [2026-05-01] ingest | Remediación seguridad agente_apuestas
Fuente: SECURITY_REMEDIATION_STEPS.md + `.gitignore` + `agente_apuestas/*.py`
Páginas creadas:
- wiki/decisiones/security-remediation-agente-apuestas-2026-05-01.md
Páginas actualizadas:
- wiki/proyectos/agente-apuestas-orquestador.md
- wiki/index.md (+1 entrada decisiones)
Notas: La key antigua de Google Cloud quedó revocada fuera de Git. Se validó `GOOGLE_API_KEY` desde `C:\ClaudeWork\.env`, se eliminó `agente_apuestas/.footystats_profile/` del tracking y de todo el historial, y la historia limpia quedó publicada en `idx/main` con `PATH_COUNT=0` y `MATCH_COUNT=0`.

## [2026-05-14] ingest | Finanzas Personales — Sprint 5 (Supabase + login + deploy)
Fuente: finanzas_personales/ (repo dedicado github.com/socrates-cabral/finanzas-personales)
Páginas creadas:
- wiki/proyectos/finanzas-personales.md
Páginas actualizadas:
- wiki/index.md (link corregido proyecto-finanzas-personales → proyectos/finanzas-personales, estado Sprint 5)
Notas: Sprint 5 completo — migración Excel→Supabase con coexistencia (toggle DATA_SOURCE), RLS multi-usuario, login Supabase Auth con sesión persistente por cookie, deploy en Streamlit Cloud (finanzas-socrates.streamlit.app). finanzas_personales/ extraído del monorepo a repo git propio (patrón HackeaMetabolismo); el monorepo lo ignora. Migración validada en paridad: 348 transacciones + 69 categorías + 22 config. Causa raíz F5: cookie SameSite=Strict se pierde en iframe cross-site de Streamlit Cloud → fix secure=True/same_site=none. Follow-up media-baja: portar persistencia de cookie a HackeaMetabolismo.

## [2026-05-14] ingest | Canal Derco Auto — automatización columna Canal de data Derco.xlsx
Fuente: WMS_Automatizacion/canal_derco_auto.py + canal_derco_utils.py
Páginas creadas:
- wiki/proyectos/canal-derco-auto.md
Páginas actualizadas:
- wiki/index.md (+1 entrada bajo proyectos)
Cambios en producción:
- canal_derco_auto.py cableado como paso 2 en FillRate_Automatizacion/run_fillrate.bat (entre fillrate_descarga y generar_resumen_kpi_ops)
- 1ra corrida real ejecutada 2026-05-14: 8.205 filas salieron de MY hacia su canal correcto, 553 "AP" sin clasificar bajaron a 1, 2.094 CES separados de MY
- Confirmación visual del usuario 2026-05-15: todos los canales identificados correctamente
Fase 2 (2026-05-15): clasificación Rack/Est unificada vía canal_derco_utils.py compartido entre canal_derco_auto.py y generar_resumen_kpi_ops.py. Antes: bot usaba tabla DimUbicaciones; ahora: regla de prefijos compartida. Delta verificado en abril 2026: solo 9 líneas (0,008%) cambian Rack→Est, total AP conservado.
Notas: llave de cruce es Nro Aplica (OP) ↔ MovDerco Comprobante (100% match), no Nro Pedido (corrupto en notación científica para 18% de filas). Recálculo completo cada corrida (auto-sanador, idempotente). Backup en _backups_data_derco/ (local, no SP). Logs + CSV de métricas en C:\ClaudeWork\logs\ para seguir tendencia de tiempos. Cuello de botella: lectura MovDerco (~80% del runtime).
