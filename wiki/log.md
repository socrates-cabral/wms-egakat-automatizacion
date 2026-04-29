# Wiki Log — ClaudeWork
Registro cronológico append-only. Formato: `## [YYYY-MM-DD] tipo | Título`

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
