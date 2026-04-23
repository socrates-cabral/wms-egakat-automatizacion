---
title: WMS Despacho Automático — Pipeline RF + Confirmación Salida
type: proyecto
sources: []
related: [proyectos/agente-apuestas-orquestador.md, proyectos/wms-automatizacion.md]
updated: 2026-04-22
confidence: high
---

## Descripción

Pipeline completo de despacho diario WMS Egakat. Dos scripts Playwright en secuencia:
1. `despacho.py` — RF Módulo 11: despacha PLTs por contenedor
2. `confirmar_salida.py` — WEB hinicio.aspx: confirma salida de viajes

Un solo correo HTML combinado al finalizar, vía Graph API.

## Arquitectura

```
Task Scheduler (08:00 / 13:00 / 17:00 Lun–Vie)
    → ejecutar_pipeline_silencioso.vbs
        → run_pipeline.bat
            → despacho.py (headless)
                → Login RF (SCABRAL2)
                → menurf.aspx: depósito + empresa + Módulo 11
                → Despacho.aspx: iterar viajes
                    → validar empresa (span#span_vEMPDSC_0001)
                    → despachar PLTs uno a uno
                    → BALANCEAR DESPACHO tras vaciar viaje
                → Guarda pipeline_resumen_temp.json (NO envía email)
            ↓ 10s pausa
            → confirmar_salida.py (headless)
                → Login WEB (SCABRAL2) → hinicio.aspx
                → Procesos WMS → Viajes Pendientes de Salida
                → Seleccionar depósito → Aplicar
                → tildaTodo() → CONFIRMARSALIDA
                → Lee pipeline_resumen_temp.json
                → Envía correo combinado (RF + Salida)
                → Borra JSON temporal
```

## Decisiones técnicas

**Por qué pipeline separado y no un solo script:** Separación de concerns — cada script se puede correr y debuggear independientemente. El `.bat` los une en secuencia.

**Por qué un solo correo:** El usuario recibe un correo por corrida con toda la información: PLTs despachados por viaje + confirmación de salida. El JSON temporal (`pipeline_resumen_temp.json`) es el mecanismo de comunicación entre scripts.

**Por qué SCABRAL2 en despacho y confirmar_salida:** Evitar conflicto de sesión con `productividad_diario.py` que usa SCABRAL. Separación de usuarios por proceso.

**Por qué `input[name="BUTTON3"]` en login WEB:** La interfaz web (`hinicio.aspx`) usa un selector diferente al RF (`hdis.aspx`). Confirmado con DevTools.

**Por qué `page.evaluate("tildaTodo()")` para seleccionar viajes:** El botón "Tildar Todo" llama a función JS pura de la página. `page.evaluate` es la forma correcta — no hay selector de input.

## Selectores confirmados (DevTools 2026-04-22)

### RF (hdis.aspx / menurf.aspx / Despacho.aspx)
| Elemento | Selector |
|---|---|
| Login RF usuario | `input#vUSR` |
| Login RF password | `input#vPASSWORD` |
| Login RF aceptar | `input[name="CMDACEPTAR"]` |
| Select Depósito | `select#vSUCCOD` |
| Select Empresa | `select#vSELECCEMPRESA` |
| Flecha → | `input#vIMAGENFLECHA` |
| Módulo 11 DESPACHO | `input[name="BUTTON3_0009"]` |
| Select Viaje | `select#vVIAJEOPCONCAT` |
| Input PLT | `input#vUBCCPL` |
| Botón DESPACHAR | `input[name="BTNDESPACHAR1"]` |
| PLTs lista | `span[id^="span_vEVENTOS_EVPLTASO_"]` |
| Empresa valor | `span#span_vEMPDSC_0001` |
| Balancear despacho | `input[name="BTNBALANCEARDESPACHO"]` |

### WEB (hinicio.aspx / trabajarconwms.aspx / viajespendientesdesalida.aspx)
| Elemento | Selector |
|---|---|
| Login WEB usuario | `input#vUSR` |
| Login WEB password | `input#vPASSWORD` |
| Login WEB ingresar | `input[name="BUTTON3"]` |
| Procesos WMS | `a[href="./trabajarconwms.aspx"]` |
| Viajes pendientes | `a[href="viajespendientesdesalida.aspx"]` |
| Select Depósito | `select#vSUCURSAL` (value="1"=QUILICURA) |
| Aplicar | `input[name="BUTTON1"]` |
| Checkboxes viajes | `input[name*="vOP_"]` (ej: `vOP_0001`) |
| Tildar Todo | `page.evaluate("tildaTodo()")` |
| Confirmar Salida | `input[name="CONFIRMARSALIDA"]` |

## Usuarios por script

| Script | Principal | Fallback |
|---|---|---|
| `despacho.py` | SCABRAL2 | SCABRAL |
| `confirmar_salida.py` | SCABRAL2 | SCABRAL |
| `productividad_diario.py` | SCABRAL | SCABRAL2 |

## Configuración

**`.env` raíz:** credenciales WMS y Graph API
**`wms_despacho/.env`:** destinatarios email (`EMAIL_DESTINO`, `EMAIL_CC`) + credenciales WMS locales

## Manejo de errores — Target crashed (fix 2026-04-22)

El renderer Chromium puede crashear mid-viaje ("Target crashed"). `page.reload()` no funciona en ese estado — requiere nueva pestaña.

**Solución implementada en `despacho.py`:**
- Se almacena el context: `ctx = browser.new_context(...)`, `page = ctx.new_page()`
- `_reiniciar_pagina(ctx, old_page, ...)` → cierra la pestaña rota, abre nueva desde el mismo `ctx`, re-login y navega a Despacho
- Loop de viajes con `while not viaje_listo` + contador `crash_intentos`
- Hasta `MAX_CRASH_RETRIES=2` reintentos por viaje; si se agotan → salta el viaje (no aborta el pipeline)
- Los PLTs ya despachados no reaparecen en la lista WMS → retry del viaje es seguro

## Estado

- **2026-04-22:** Pipeline completo validado en producción. 16 viajes confirmados, 102 PLTs despachados en prueba final. Email combinado aprobado. Destinatarios: socrates.cabral + mariana.varela. Task Scheduler activo: 08:00 / 13:00 / 17:00.
- **2026-04-22:** Fix Target crashed — recovery con nueva pestaña + retry automático hasta 2 intentos por viaje.
