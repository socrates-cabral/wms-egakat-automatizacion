# AGENTS.md — wms_despacho

## Propósito
Automatización de despacho por contenedor en WMS Egakat RF (Módulo 11).
Procesa todos los viajes pendientes despachando cada PLT hasta vaciar la lista diaria.

## Archivos clave
| Archivo | Rol |
|---|---|
| `despacho.py` | Script principal Playwright |
| `run_despacho.bat` | Lanzador para Task Scheduler |
| `logs/despacho_YYYY-MM-DD.log` | Log completo diario |
| `logs/despacho_YYYY-MM-DD.csv` | Resumen por PLT (Excel) |

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

## Task Scheduler (automatización diaria)
```
Programa  : C:\Windows\System32\cmd.exe
Argumentos: /c C:\ClaudeWork\wms_despacho\run_despacho.bat
Directorio: C:\ClaudeWork\wms_despacho
Horario   : Lunes a Viernes, hora definida por operaciones
```
