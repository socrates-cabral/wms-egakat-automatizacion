# Memory — Softnet_Ventas

Proyecto activo. Contexto completo en `MEMORY.md` en la raíz del proyecto.
Ver también: `PROJECT_SPEC.md` para spec técnico detallado.

## Estado actual
- Implementado completo (Fases 1-7) — 2026-04-24
- Pendiente: agregar credenciales al .env root + ejecutar `registrar_tarea.ps1` como admin

## Archivos clave
- `src/run_ventas.py` — entrypoint
- `config/parametros.json` — parámetros ajustables (ventana, SP, notificación)
- `logs/log_cambios_pagos.xlsx` — auditoría de cambios de estado pago

## Env vars requeridas (en C:\ClaudeWork\.env)
- `EMPRESA_SOFTNET_RUT` — RUT empresa en Softnet
- `USUARIO_SOFTNET` — usuario Softnet
- `CLAVE_SOFTNET` — clave Softnet
- Ya existentes: `Application_(client)_ID`, `Directory_(tenant)_ID`, `Client_Secret_Value`, `SHAREPOINT_USER`, `SHAREPOINT_PASSWORD`
