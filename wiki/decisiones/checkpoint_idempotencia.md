---
title: Patrón Checkpoint Idempotencia — Módulos WMS
type: decision
sources: []
related: [proyectos/productividad.md]
updated: 2026-04-13
confidence: high
---

# Checkpoint Idempotencia en Módulos WMS

## Decisión
Implementar checkpoint JSON diario en Productividad y FillRate para que re-ejecuciones no descarguen datos ya procesados.

## Por qué
- Los módulos pueden fallar a mitad de corrida (ej: sesión WMS caída, Page crashed)
- Sin checkpoint: re-ejecutar reprocesa todos los clientes innecesariamente
- Con checkpoint: solo re-procesa los pendientes, respetando la restricción de una sesión WMS activa

## Implementación
```
logs/productividad_checkpoint_YYYYMMDD.json
logs/fillrate_checkpoint_YYYYMMDD.json
```
Estructura:
```json
{"completados": ["daikin", "pochteca", ...], "rows": {"daikin": 38, "pochteca": 52}}
```

- Se guarda por cliente al finalizar con `publish_code == 0` (Productividad) o `estado=OK` (FillRate)
- Se carga al inicio: clientes en checkpoint → skip + estado "Ya descargado" en correo
- `--force` ignora checkpoint para re-descarga completa

## Referencia
Patrón inspirado en `run_todos.py` que usa `wms_checkpoint_YYYYMMDD.json` para los módulos WMS principales.
