---
title: WMS Despacho Automático por Contenedor
type: proyecto
sources: []
related: [proyectos/agente-apuestas-orquestador.md, conceptos/wms-egakat.md]
updated: 2026-04-22
confidence: high
---

## Descripción

Script Playwright (`wms_despacho/despacho.py`) que automatiza el Módulo 11 RF del WMS Egakat: Despacho por Contenedor. Procesa todos los viajes pendientes de una empresa despachando cada PLT hasta vaciar la lista diaria.

## Arquitectura

```
Task Scheduler (08:00 / 13:00 / 17:00 Lun–Vie)
    → ejecutar_despacho_silencioso.vbs (sin ventana)
        → despacho.py --headless (default)
            → Login WMS (SCABRAL / fallback SCABRAL2)
            → menurf.aspx: seleccionar depósito + empresa + flecha → Módulo 11
            → Despacho.aspx: iterar viajes
                → validar empresa (span#span_vEMPDSC_0001)
                → despachar PLTs uno a uno
                → BALANCEAR DESPACHO tras vaciar viaje
            → Email resumen vía Graph API
```

## Decisiones técnicas

**Por qué filtrar empresa por viaje y no en menurf:** El Módulo 11 muestra viajes de TODOS los clientes del depósito independiente de la empresa seleccionada en menurf. La selección solo da acceso al módulo.

**Por qué BALANCEAR DESPACHO:** Sin este clic los viajes completados permanecen en la lista. Selector: `input[name="BTNBALANCEARDESPACHO"]`.

**Por qué Graph API y no SMTP:** El tenant de Office 365 de Egakat tiene SmtpClientAuthentication deshabilitado. Todos los proyectos usan Graph API con credenciales del `.env` raíz (`Directory_(tenant)_ID`, `Application_(client)_ID`, `Client_Secret_Value`).

**Por qué headless por defecto:** Modo producción. Usar `--show` para debug visual, `--show --debug` para pausar entre pasos.

## Selectores HTML confirmados (DevTools 2026-04-22)

| Elemento | Selector |
|---|---|
| Usuario login | `input#vUSR` |
| Password login | `input#vPASSWORD` |
| Botón ACEPTAR | `input[name="CMDACEPTAR"]` |
| Select Depósito | `select#vSUCCOD` |
| Select Empresa | `select#vSELECCEMPRESA` |
| Flecha → | `input#vIMAGENFLECHA` |
| Botón 11 DESPACHO | `input[name="BUTTON3_0009"]` |
| Select Viaje | `select#vVIAJEOPCONCAT` |
| Input contenedor | `input#vUBCCPL` |
| Botón DESPACHAR | `input[name="BTNDESPACHAR1"]` |
| PLTs pendientes | `span[id^="span_vEVENTOS_EVPLTASO_"]` |
| Empresa valor | `span#span_vEMPDSC_0001` |
| Balancear despacho | `input[name="BTNBALANCEARDESPACHO"]` |

## Códigos de resultado CSV

| Código | Significado |
|---|---|
| OK | PLT despachado correctamente |
| VIAJE_COMPLETO | Último PLT del viaje |
| SIN_REMITO | OP sin remito asignado |
| YA_DESPACHADO | PLT ya procesado por otro usuario |
| NO_SE_PUEDE | WMS rechazó el despacho |
| EMPRESA_INCORRECTA | Viaje de otra empresa, saltado |
| DOBLE_SESION | Sesión expulsada por otro login |
| TIMEOUT | Página tardó demasiado |
| ERROR | Error inesperado |

## Configuración

**`.env` raíz:** credenciales WMS, Graph API
**`wms_despacho/.env`:** destinatarios email (`EMAIL_DESTINO`, `EMAIL_CC`)

**Variables CLI:**
```bash
py despacho.py                          # DERCO + QUILICURA, headless
py despacho.py --empresa "CERVECERIA ABI" --deposito PUDAHUEL
py despacho.py --show                   # con ventana
py despacho.py --dry-run                # solo valida navegación
```

## Task Scheduler

| Tarea | Hora |
|---|---|
| WMS Despacho - Manana 08:00 | Lun–Vie 08:00 |
| WMS Despacho - Mediodia 13:00 | Lun–Vie 13:00 |
| WMS Despacho - Tarde 17:00 | Lun–Vie 17:00 |

## Estado

- **2026-04-22:** Creado, validado en producción, 166+ PLTs despachados en primera corrida. Email Graph API activo. VoB aprobado. Destinatarios: socrates.cabral + mariana.varela (resto pendiente de activar).
