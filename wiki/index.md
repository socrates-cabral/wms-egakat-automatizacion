# Wiki Index — ClaudeWork
Última compilación: 2026-05-25

## Proyectos

- [[proyectos/yield-sentinel]] — YieldSentinel Fase 1 activa (2026-05-31): paper trading automático Hyperliquid cripto perpetuos. BTC Breakout candidata líder (+29.7% ROI). Task Scheduler 15min + n8n webhooks + Telegram.

- [[proyecto-wms-egakat]] — Automatización descargas WMS Egakat SPA. 9 módulos activos (Módulo 9 = Validación Post-Ejecución). Graph API migrado 2026-03-24.
- [[proyectos/wms-automatizacion]] — Suite completa WMS: módulos 1-3-7-8-9, azure_graph.py compartido, Playwright headless, SCABRAL detection, tiempos hasta 360s.
- [[proyectos/nps-encuesta]] — Módulo 5: CSAT (386641) + NPS (418429) desde LimeSurvey RCAPI → Excel PowerBI → SharePoint Graph API. 3 tareas programadas.
- [[proyectos/vdr-comparador]] — Módulo 4: SAP vs Físico Derco Parts, horario, diff Excel amarillo, Power Automate trigger. Sin Graph API (OneDrive sync).
- [[proyectos/wms-run-todos]] — run_todos.py v2.2: lock+checkpoint+bridge pointer, retry 60s, estados OK/PARCIAL/ADVERTENCIA/FALLO, Graph API→Outlook fallback, 8 destinatarios.
- [[proyectos/productividad]] — 15 clientes, checkpoint diario+rows, timing fix AJAX 2000ms, email TO+CC desde .env local, separador miles latinoamericano. Fix Task Scheduler Password 2026-04-13.

## Decisiones técnicas
- [[decisiones/checkpoint_idempotencia]] — Patrón checkpoint JSON diario en Productividad y FillRate: skip clientes ya OK, row count guardado, --force override.
- [[decisiones/fillrate-checkpoint-serialization]] — Manejo robusto tipos datetime en checkpoint JSON. Bug latente 14 días (cdfff18→bac0c76). Round-trip JSON convierte date→string, fix detecta tipo antes de .strftime().
- [[decisiones/decision-context-on-request-playwright]] — context.on vs page.on en Playwright: WMS abre Excel en nueva pestaña, page.on no la captura. Siempre usar context.on para descargas WMS.
- [[decisiones/code-review-bots-telegram]] — Code review Codex 2026-05-01: 18 archivos, 4500 LOC. Multi-LLM fallback, SQLite historial, aislamiento RUT. 2 críticos, 5 altos. Seguro prod con optimizaciones.
- [[decisiones/security-remediation-agente-apuestas-2026-05-01]] — Remediación 2026-05-01: .footystats_profile eliminado del tracking e historial, GOOGLE_API_KEY validada desde .env raíz y repo limpio publicado en idx/main.
- [[proyecto-agente-apuestas]] — Agente ML XGBoost para value bets deportivos. Sprint 17 completo (Tavily enricher activo, umbrales adaptativos). Serie A activa.
- [[proyectos/agente-apuestas-modelos-ml]] — Inventario modelos multi-deporte 2026-05-25: Tenis v1/v2, NBA, NFL, Clubes v2, MLB. AUCs 0.67-0.70. Leakage detectado/corregido en tenis y clubes.
- [[proyectos/agente-apuestas-fixes-2026-04-29]] — Fixes críticos sesgo Under (83%→target <60%), lambda floor bug, re-entrenamiento XGBoost. Grid ROI: umbral 0.60 = +9.82%. Parámetros: MIN_CONFIDENCE=60, umbrales=0.65.
- [[proyectos/fillrate-automatizacion]] — Módulo independiente Fill Rate: 13 clientes, Graph API SharePoint, lock file, 3 reintentos Graph API. Corrió OK 10/04 en 47 min.
- [[proyectos/agente-apuestas-orquestador]] — run_agent.py: flujo 7 pasos, control riesgo stop-loss 15%/25%, MAX_FIXTURES=6, módulos opcionales graceful import.
- [[proyectos/finanzas-personales]] — App Streamlit finanzas chilenas. **Sprint 5 completo 2026-05-14**: migración Supabase + RLS multi-usuario + login Supabase Auth + deploy Streamlit Cloud (finanzas-socrates.streamlit.app). Repo dedicado, coexistencia Excel↔Supabase con toggle DATA_SOURCE.
- [[proyecto-chiquito-financiero]] — App diagnóstico financiero negocio muebles. Puerto 8502. Streamlit Community Cloud.
- [[proyecto-hackea-metabolismo]] — App pérdida de peso bilingual. Puerto 8504/8505. 14 sprints completos.
- [[proyectos/nutrimetab-bi]] — Herramienta clínica nutricional/metabólica. SQLite, RandomForest 92%, 18/18 tests. S1–S8b completos, sin roadmap pendiente.
- [[proyectos/inversiones-ia]] — App análisis inversiones institucional (BlackRock/GS/MS/Citadel). Claude + yfinance + Plotly. Puerto 8506. Sprint 1.
- [[proyectos/productividad-automatizacion]] — OPERATIVO 2026-04-21. productividad_diario.py: append incremental diario, 17 clientes (incl. NATIVO DRINKS + OMNITECH), checkpoint JSON, dedup, token Graph API por cliente.
- [[proyectos/wms-despacho-automatico]] — OPERATIVO 2026-04-22. Pipeline RF+WEB: despacho PLTs + confirmación salida viajes. SCABRAL2 principal. Email combinado Graph API. Task Scheduler 08:00/13:00/17:00.
- [[proyectos/softnet-ventas]] — OPERATIVO 2026-04-24. Libro de Ventas Softnet → SharePoint vía Graph API. Correo diario con CxC, vencidas, alto monto, pagos del día. L-V 16:00.
- [[proyectos/kpi-ops]] — DESARROLLO 2026-04-29. generar_resumen_kpi_ops.py (4524 líneas, Codex): JSON KPIs operativos (NNSS, Productividad, Inventario). 9 carpetas OneDrive compartidas. Alimenta @EgakatOpsBot vía n8n. Pendiente integración workflow.
- [[proyectos/canal-derco-auto]] — OPERATIVO 2026-05-14. canal_derco_auto.py: recalcula columna Canal de data Derco.xlsx desde MovDerco (cruce por OP). AP_R/AP_E por predominio líneas, separa CES (concesionarios) de MY. Cableado en run_fillrate.bat. Fase 2: bot WMS alineado vía canal_derco_utils.py compartido.
- [[proyectos/servidor_egakat_24x7]] — PLANIFICACIÓN 2026-04-29. Migración todas las automatizaciones Egakat a servidor dedicado 24/7. Mini PC Lenovo M75q Gen 2 recomendado. 9 fases, 6 días estimado, USD 720 inversión + $30.50/mes (M365 + Power BI Pro + electricidad).

## Mantenimiento & Infraestructura

- [[proyectos/cleanup-automation]] — OPERATIVO 2026-04-30. Sistema limpieza automatizada C:\ClaudeWork. Task Scheduler mensual (1er día 02:00). Elimina cache, logs >30d, outputs >15d, chunks, temporales. 2.7GB liberados inicial. Safe: nunca toca código/config/datos críticos.

## Criptomonedas

- [[proyectos/crypto-bot]] — Grid Trading BTC_USDT + EMA 200 filter. Paper trading activo. Exchange abstraction (Crypto.com + Kraken). 20 niveles $80K-$100K.

## Documentos & Presentaciones
- Presentacion_GrupoPlanet_Automatizacion.pptx — 8 slides, 2.440 hrs/año ahorradas, 6 procesos automatizados. Generador: Documentos/generar_presentacion_grupo_planet.py (gitignored)

## Conceptos ML / Estadística

- [[value-betting]] — Core del agente: detectar cuando prob_modelo > prob_implícita en cuota. Umbral mínimo value > 5%.
- [[conceptos/pi-rating]] — Sistema rating dinámico (Constantinou ~2012): ELO adaptado a goles, decay 0.98, K=0.5. Feature pi_diff en XGBoost. Limitación: no captura contexto ni lesiones.
- [[xg-expected-goals]] — Fuente: Understat. 10,707 partidos 5 ligas × 6 temporadas (2019-2024).
- [[kelly-criterion]] — Fórmula de apuesta óptima. Usar Quarter Kelly (×0.25). Cap 10% bankroll.
- [[xgboost-modelo]] — CV=0.4888, Test=0.5226. Sin data leakage (TimeSeriesSplit). 35 features.
- [[data-leakage]] — Bug corregido Sprint 8. Accuracy falsa 0.66 → real 0.50 al separar train/test cronológicamente.

## Conceptos WMS / Logística

- [[playwright-wms]] — Automatización headless Chromium. URL: egakatwms.cl. Selectores documentados por módulo.
- [[staging-in-out]] — 16 clientes, 3 sesiones CD. Selector SCABRAL detection para fallos silenciosos WMS.
- [[scabral-detection]] — WMS falla silenciosamente devolviendo SCABRAL{timestamp}.csv 0 bytes. Regex: `^SCABRAL\d+\.csv$`
- [[graph-api-migration]] — AADSTS53003 resuelto 2026-03-24. M1/M3/M6/M7/M8 migrados. Sites.ReadWrite.All aprobado.
- [[vdr-comparador]] — SAP vs Físico Derco Parts. 91,579 registros. Corre cada hora L-V 8-19.

## Entidades / APIs

- [[api-sports]] — 100 req/día gratuito. Fútbol + Basketball. Lesiones en /injuries?fixture={id}.
- [[understat]] — xG datos históricos. Python lib understatapi. 5 ligas disponibles (no UCL).
- [[transfermarkt]] — Valores de plantilla. Cache 30 días. IDs en config.py TRANSFERMARKT_IDS.
- [[the-odds-api]] — 500 créditos/mes. 40+ bookmakers. Cuotas pre-partido y en vivo.
- [[betano-chile]] — Casa de apuestas referencia. lat.betano.com. Moneda CLP.
- [[egakat-spa]] — Cliente 3PL Santiago Chile. WMS: QUILICURA + PUDAHUEL + PUDAHUEL UNITARIO.
- [[graph-api-microsoft]] — Reemplazó SMTP y OneDrive sync. Sites.ReadWrite.All + Mail.Send.

## Decisiones de arquitectura

- [[decision-flat-structure]] — Scripts en carpeta raíz del proyecto, no subcarpetas. Simplifica imports y .env loading.
- [[decision-haiku-modelo]] — claude-haiku-4-5-20251001 para uso diario. Sonnet/Opus solo cuando sea necesario.
- [[decision-paper-trading]] — MODO_PAPER_TRADING=True hasta ROI ≥ 20% sostenido n ≥ 20. Nunca hardcodear monto real.
- [[decision-graph-api]] — Migrado desde OneDrive sync + SMTP. Motivo: AADSTS53003 Conditional Access.
- [[decision-py-command]] — Siempre `py` y `py -m pip`. Nunca `python` ni `pip` directo.
- [[decisiones/decision-crypto-bot-grid]] — Bot cripto: Grid Trading + EMA 200 filtro tendencia. BTC/USDT. 4 fases. Paper 30 días mínimo antes de capital real. Pendiente de implementar.
- [[decisiones/decision-ml-roadmap-sprints20-22]] — S20 forma reciente (esta semana) → S21 separar modelos 1X2/Over-Under (n≥50, ~30 abril) → S22 Platt scaling (~mayo). api-sports Pro: no todavía.

## Estado ligas Agente Apuestas (actualizado 2026-04-09)

- [[liga-serie-a]] — ACTIVA. ROI +31.65%, n=23, accuracy 82.6%. Umbral 0.70, value 0.10.
- [[liga-la-liga]] — Suspendida. ROI +25.44% pero n=9 (necesita ≥20).
- [[liga-bundesliga]] — Suspendida. ROI +9.69%, n=16 (necesita ≥20).
- [[liga-premier-league]] — Suspendida. ROI -4.27%.
- [[liga-ligue-1]] — Suspendida. ROI -44.82%.
- [[liga-ucl]] — No activar aún. CV=0.4901, Test=0.5244. Pocas temporadas, qualifying diluye señal.
