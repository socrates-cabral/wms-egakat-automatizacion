# MEMORY — Softnet_Ventas

Automatización diaria de descarga del Libro de Ventas desde ERP Softnet y sincronización a SharePoint vía Graph API. Insumo para Power BI ya existente (no se diseña BI aquí, solo el pipeline de datos).

## Estado
- **Fase**: Diseño cerrado, listo para implementación por Claude Code
- **Owner**: Sócrates Cabral
- **Creado**: 2026-04-24
- **Ubicación**: `C:\ClaudeWork\Softnet_Ventas\`

## Objetivo de negocio
Eliminar la descarga manual diaria del Libro de Ventas que hoy realiza una persona. El archivo alimenta un Power BI ya construido que calcula DSO, cumplimiento de plazo, aging, etc. El dato crítico que cambia diariamente es el **estado de pago** de facturas emitidas en meses anteriores (clientes tienen hasta 60 días de crédito).

## Arquitectura
```
Softnet ERP (Playwright headless)
    ↓
Descarga libro_ventas.xlsx mensual
    ↓
Comparación con versión anterior (Graph API descarga)
    ↓
Detección de cambios → log_cambios_pagos.xlsx local
    ↓
Upload a SharePoint (Graph API) SOLO si hubo cambios
    ↓
Power BI consume desde SharePoint (ya existente)
```

## Decisiones clave (inmutables, ya discutidas y acordadas)

| # | Decisión | Justificación |
|---|---|---|
| D1 | Ventana de actualización = **60 días exactos** | Plazo máximo de crédito al cliente |
| D2 | **Playwright headless** (no requests) | Robustez ante futuros cambios del portal |
| D3 | Frecuencia: **diaria**, vía Task Scheduler | Requerimiento del usuario |
| D4 | **Graph API directo** (no OneDrive sync) | La carpeta de SharePoint destino no está sincronizada localmente |
| D5 | **Script independiente**, no integrado a `run_todos.py` | Aislar criticidad (ventas vs WMS) |
| D6 | Reutilizar `.env` root y patrón `azure_graph.py` de `C:\ClaudeWork\` | Consistencia con arquitectura Egakat |
| D7 | Log de cambios **local** (no SP) | Power BI ya tiene su modelo; log es solo auditoría operacional |
| D8 | Comparación previa a upload | Evita sobreescribir SP con versiones idénticas |
| D9 | Snapshot `_cierre` cuando mes sale de ventana | Respaldo inmutable contable |

## Lógica de negocio: ventana de 60 días

Un mes M está **abierto** (elegible para re-descarga) si:
```
(último_día_del_mes_M + 60 días) >= fecha_actual
```

Cuando deja de cumplirse → mes **cerrado** → se genera snapshot y no se re-descarga más.

**Ejemplo ejecutando el 24/04/2026:**

| Mes | Último día | Fecha congelamiento | Estado hoy |
|---|---|---|---|
| Enero 2026 | 31/01/2026 | 01/04/2026 | **Cerrado** (snapshot ya existe) |
| Febrero 2026 | 28/02/2026 | 29/04/2026 | **Abierto** (5 días más) |
| Marzo 2026 | 31/03/2026 | 30/05/2026 | **Abierto** |
| Abril 2026 | 30/04/2026 | 29/06/2026 | **Abierto** (mes en curso) |

Máximo 3-4 meses abiertos simultáneamente (mes en curso + 2 anteriores).

## Formato archivo Softnet (ya analizado)

- **Filas 1-9**: encabezado del ERP (empresa, RUT, mes, período)
- **Fila 10**: headers de 30 columnas
- **Fila 11 en adelante**: datos transaccionales
- **Clave única** documento: `(Tipo Doc + N° Cto)` ej `33-8495`
- **Tipos de documento**: 33 = Factura, 61 = Nota de Crédito

### Columnas críticas para comparación
| Col | Nombre | Uso |
|---|---|---|
| A | Fecha | Fecha emisión (clave + filtro) |
| B | Cto | N° correlativo |
| C | Tipo Doc | 33 / 61 |
| D | Rut | Cliente |
| E | Razón Social | Cliente |
| J | Total | Monto |
| M | Forma de Pago | CONTADO / CREDITO 30/60 DIAS |
| **Q** | **Estado** | **Pagado / NO Pagado** ← dinámico |
| **R** | **Fecha Último pago** | Fecha efectiva pago ← dinámico |
| S | Comprobantes Tesorería | N° comprobante ← dinámico |
| T | Saldo | Pendiente ← dinámico |
| AA | NC Referencias | NC que aplica a esta factura |

## Convención de nombres

**SharePoint**: `{mes_num}.0 Ventas {Mes_español} {año}.xlsx`
- `1.0 Ventas Enero 2026.xlsx`
- `2.0 Ventas Febrero 2026.xlsx`
- `12.0 Ventas Diciembre 2026.xlsx`

**Ruta SharePoint destino**: sitio `Finanzas y Mejora Continua` → `Documentos compartidos` → `Informe Ventas Mensual` → `{año}`

**Snapshots locales de cierre**: `C:\ClaudeWork\Softnet_Ventas\snapshots_cierre\{año}\{mes_num}.0 Ventas {Mes} {año}_cierre.xlsx`

## Tipos de eventos en log_cambios_pagos.xlsx

| tipo_cambio | Condición |
|---|---|
| `NUEVA_FACTURA` | Documento existe en nuevo snapshot, no en anterior |
| `PAGO_APLICADO` | Estado pasó de "NO Pagado" → "Pagado" |
| `NC_APLICADA` | Nuevo documento tipo 61 con referencia a factura existente |
| `CAMBIO_SALDO` | Saldo cambió sin cambio de estado (pago parcial) |
| `CAMBIO_OTRO` | Cualquier otro cambio relevante detectado |

**Campos del log (9 columnas, minimalista)**:
`fecha_deteccion | mes_archivo | tipo_doc | n_cto | rut | razon_social | tipo_cambio | estado_anterior_→_actual | fecha_pago | monto_total`

## Variables de entorno requeridas

En `C:\ClaudeWork\.env` agregar:
```
EMPRESA_SOFTNET_RUT=<el RUT de Egakat Logística>
USUARIO_SOFTNET=<usuario Softnet>
CLAVE_SOFTNET=<clave Softnet>
```

**Ya existentes** (se reusan sin modificación):
- `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`, `AZURE_TENANT_ID` (app `WMS_Egakat_SharePoint`)
- `SHAREPOINT_USER`, `SHAREPOINT_PASSWORD` (para notificación SMTP fallback)

## Flujo de Task Scheduler

- **Tarea**: `Softnet Ventas - Descarga Diaria`
- **Horario**: Lunes a Viernes 08:30 (después del WMS 08:00 para no saturar red)
- **Comando**: `py C:\ClaudeWork\Softnet_Ventas\src\run_ventas.py`
- **Log**: `C:\ClaudeWork\logs\softnet_ventas_YYYY-MM-DD_HHMMSS.log`

## Dependencias

```
playwright>=1.40
openpyxl>=3.1
pandas>=2.0
python-dotenv>=1.0
msal>=1.25          # OAuth2 Graph API (client_credentials)
requests>=2.31
```

## Restricciones / Reglas sagradas (heredadas de CLAUDE.md)

- 🔐 **NUNCA leer, mostrar ni verificar `.env`** — solo usar variables con `os.getenv()`
- 🔐 Credenciales siempre desde `.env`, jamás hardcoded
- Python: `py` y `py -m pip`
- Header obligatorio en todo script: `sys.stdout.reconfigure(encoding="utf-8")`
- Playwright: `headless=True`, timeouts 60s default / 180s descargas
- Logs en `C:\ClaudeWork\logs\` con prefijo `[FALLO]` para errores críticos
- Retry con backoff (3 intentos, 60s/120s/180s)
- `pandas.to_*` con `errors="coerce"` (no `"ignore"`)

## Pendientes post-producción (no bloquean v1)

- [ ] Mover `sp_graph.py` a `C:\ClaudeWork\lib\` si se reusa en otros proyectos
- [ ] Agregar métricas al correo diario (facturas nuevas, pagos aplicados)
- [ ] Wiki entry en `C:\ClaudeWork\wiki\proyectos\softnet_ventas.md` tras primera ejecución exitosa
