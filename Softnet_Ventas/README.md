# Softnet_Ventas

Automatización diaria de descarga del Libro de Ventas desde ERP Softnet y subida a SharePoint vía Graph API. Alimenta Power BI existente.

## Arquitectura rápida

```
Softnet ERP (Playwright)  →  Comparación con versión SP  →  Upload a SharePoint (Graph API)
                                        ↓
                          log_cambios_pagos.xlsx (local, auditoría)
```

## Lógica

- **Ventana de 60 días**: re-descarga solo meses que aún aceptan pagos retroactivos.
- **Upload inteligente**: sobreescribe SP solo si hay cambios reales en estado de pago, saldo o nuevas facturas.
- **Snapshot _cierre**: al salir un mes de la ventana, se guarda copia inmutable local.

## Uso

```bash
# Ejecución manual
py C:\ClaudeWork\Softnet_Ventas\src\run_ventas.py

# Tarea programada (Task Scheduler)
# Nombre: "Softnet Ventas - Descarga Diaria"
# Horario: L-V 08:30
```

## Variables .env requeridas

Agregar a `C:\ClaudeWork\.env`:
```
EMPRESA_SOFTNET_RUT=...
USUARIO_SOFTNET=...
CLAVE_SOFTNET=...
```

Reusa las ya existentes: `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`, `AZURE_TENANT_ID` (app `WMS_Egakat_SharePoint`), `SHAREPOINT_USER`, `SHAREPOINT_PASSWORD`.

## Permisos Graph API

La app de Azure AD debe tener el permiso **`Sites.ReadWrite.All`** (Application, con admin consent) para poder escribir en SharePoint.

## Logs

- **Técnico por ejecución**: `C:\ClaudeWork\logs\softnet_ventas_YYYY-MM-DD_HHMMSS.log`
- **Auditoría de cambios**: `C:\ClaudeWork\Softnet_Ventas\logs\log_cambios_pagos.xlsx`

## Documentación

- `MEMORY.md` — contexto de negocio y decisiones
- `PROJECT_SPEC.md` — spec técnico y pseudo-código
- `config/parametros.json` — parámetros operativos ajustables
