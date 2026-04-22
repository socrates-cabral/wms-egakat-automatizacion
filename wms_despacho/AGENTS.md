# AGENTS.md — wms_despacho

## Propósito
Pipeline de despacho diario WMS Egakat:
1. `despacho.py` — RF Módulo 11: despacha PLTs por contenedor
2. `confirmar_salida.py` — WEB: confirma salida de viajes después del RF

## Archivos clave
| Archivo | Rol |
|---|---|
| `despacho.py` | Script RF — despacha PLTs (Módulo 11) |
| `confirmar_salida.py` | Script WEB — confirma salida de viajes |
| `run_pipeline.bat` | Orquesta ambos scripts en secuencia |
| `ejecutar_pipeline_silencioso.vbs` | Lanzador silencioso para Task Scheduler |
| `crear_tareas_pipeline.ps1` | Crea las 3 tareas programadas del pipeline |
| `logs/despacho_YYYY-MM-DD.log` | Log RF diario |
| `logs/confirmar_salida_YYYY-MM-DD.log` | Log WEB diario |
| `logs/pipeline_YYYY-MM-DD.log` | Log combinado del pipeline |

## Selectores HTML confirmados (DevTools 2026-04-22)
| Elemento | Selector |
|---|---|
| Usuario (login) | `input#vUSR` |
| Password | `input#vPASSWORD` |
| Botón ACEPTAR | `input[name="CMDACEPTAR"]` |
| Select Depósito | `select#vSUCCOD` |
| Select Empresa | `select#vSELECCEMPRESA` |
| Flecha → | `input#vIMAGENFLECHA` |
| Botón 11 DESPACHO | `input[name="BUTTON3_0009"]` |
| Select Viaje | `select#vVIAJEOPCONCAT` |
| Input contenedor | `input#vUBCCPL` |
| Botón DESPACHAR | `input[name="BTNDESPACHAR1"]` |
| PLTs pendientes | `span[id^="span_vEVENTOS_EVPLTASO_"]` |
| Empresa valor (PALLETS PENDIENTES) | `span#span_vEMPDSC_0001` |

## Uso
```bash
py despacho.py                          # DERCO + QUILICURA (defaults)
py despacho.py --empresa "CERVECERIA ABI" --deposito PUDAHUEL
py despacho.py --headless               # producción
py despacho.py --debug                  # verificación paso a paso
```

## Constraint crítico
WMS no soporta dos sesiones simultáneas. Script usa SCABRAL como principal
y SCABRAL2 como fallback. NO abrir sesión manual mientras corre el script.

## Variables .env requeridas
```
WMS_USUARIO=SCABRAL
WMS_USUARIO_2=SCABRAL2
WMS_PASSWORD=...
WMS_PASSWORD2=...
WMS_DEPOSITO=QUILICURA   # opcional, default
WMS_EMPRESA=DERCO        # opcional, default
```

## Códigos de resultado CSV
| Código | Significado |
|---|---|
| OK | Despachado correctamente |
| VIAJE_COMPLETO | Último PLT — viaje terminado |
| SIN_REMITO | OP sin remito asignado |
| YA_DESPACHADO | Otro usuario ya lo procesó |
| NO_SE_PUEDE | WMS rechazó el despacho |
| TIMEOUT | Página tardó demasiado |
| ERROR | Error inesperado |

## Selectores WEB (hinicio / trabajarconwms)
| Elemento | Selector |
|---|---|
| Usuario login WEB | `input#vUSR` |
| Clave login WEB | `input#vPASSWORD` |
| Botón INGRESAR (hinicio) | `input[name="BUTTON3"]` |
| Procesos WMS | `a[href="./trabajarconwms.aspx"]` |
| Viajes pendientes de salida | `a[href="viajespendientesdesalida.aspx"]` |
| Select Depósito | `select#vSUCURSAL` (value="1"=QUILICURA, "2"=PUDAHUEL) |
| Botón Aplicar | `input[name="BUTTON1"]` |
| Checkboxes viajes | `input[name*="vOP_"]` |
| Tildar Todo | `page.evaluate("tildaTodo()")` |
| Confirmar Salida | `input[name="CONFIRMARSALIDA"]` |

**Nota:** selectores de depósito en hinicio.aspx pendientes de confirmar con DevTools.

## Usuarios por script
| Script | Principal | Fallback |
|---|---|---|
| `despacho.py` | SCABRAL2 | SCABRAL |
| `confirmar_salida.py` | SCABRAL2 | SCABRAL |
| `productividad_diario.py` | SCABRAL | SCABRAL2 |

## Pipeline — Task Scheduler
```
Programa : wscript.exe
Argumento: C:\ClaudeWork\wms_despacho\ejecutar_pipeline_silencioso.vbs
Horario  : Lunes a Viernes 08:00 / 13:00 / 17:00
Crear    : powershell -ExecutionPolicy Bypass -File crear_tareas_pipeline.ps1
```
Eliminar las tareas antiguas "WMS Despacho - *" tras validar el pipeline.
