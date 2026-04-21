---
title: Productividad Automatización — Descarga Diaria Incremental
type: proyecto
sources: [Productividad_Automatizacion/productividad_config.py, Productividad_Automatizacion/productividad_diario.py]
related: [fillrate-automatizacion, wms-automatizacion, graph-api-microsoft]
updated: 2026-04-21
confidence: high
---

# Productividad Automatización

## Estado actual
**OPERATIVO** — `productividad_diario.py` corriendo desde 2026-04-21. Task Scheduler: Lun-Vie 10:30 AM.
TESTING_MODE=True (correo solo a socrates.cabral@egakat.cl). Cambiar a False tras 2-3 días exitosos.

## Script principal: productividad_diario.py

Reemplaza al viejo `productividad_descarga.py`. Descarga **incremental diaria** con append+dedup a SharePoint.

### Flujo por cliente
1. Leer checkpoint → ventana `from_dt` (08:00) / `to_dt` (06:00)
2. Descargar XLS del WMS vía Playwright (movxdocbase.aspx)
3. Parsear HTML→DataFrame (`dayfirst=True` — WMS usa DD-MM-YYYY con guiones)
4. Descargar archivo existente de SharePoint
5. Concat + dedup por clave compuesta
6. Subir resultado a SharePoint (con backup automático)
7. Actualizar checkpoint

### Ventana de descarga
- `from_dt` = checkpoint_date a las **08:00** (inicio turno)
- `to_dt` = hoy a las **06:00** (fin turno nocturno)
- Lunes: cubre fin de semana automáticamente
- Feriados: skip si hoy es feriado (lee `Tabla Feriados.xlsx`)
- Gaps: checkpoint no avanza si cliente falla → se cubre en próximo run

### Dedup key
`["Comprobante", "Comprobante externo", "Artículo", "Fecha", "Hora", "Número"]`

### Formato de fechas WMS
WMS genera HTML con fechas **DD-MM-YYYY** (ej. `02-04-2026`).
Script lee con `dayfirst=True` → correcto.
Escribe a xlsx como string `DD/MM/YYYY` (ej. `02/04/2026`).

## Clientes activos — 17 total (actualizado 2026-04-21)

| CD | Key config | Alias archivo | Empresa WMS |
|----|-----------|--------------|-------------|
| QUILICURA | abinbev | MovABInbev | CERVECERIA ABI |
| QUILICURA | bha | MovBha | BHA |
| QUILICURA | daikin | MovDaikin | DAIKIN |
| QUILICURA | pochteca | MovPochteca | POCHTECA |
| QUILICURA | mascota_quilicura | MovMascota | MASCOTAS LATINAS |
| QUILICURA | derco | MovDerco | DERCO (heavy) |
| PUDAHUEL | barentz | MovBarentz | BARENTZ |
| PUDAHUEL | buraschi | MovBuraschi | BURASCHI |
| PUDAHUEL | cepas_chile | MovCepas Chile | CEPAS CHILE |
| PUDAHUEL | collico | MovCollico | COLLICO |
| PUDAHUEL | delibest | MovDelibest | DELIBEST |
| PUDAHUEL | intime | Movintime | INTIME |
| PUDAHUEL | tresmontes | Movtresmontes | TRES MONTES |
| PUDAHUEL | unilever | MovUnilever | UNILEVER |
| PUDAHUEL UNITARIO | runo | MovRuno | RUNO SPA |
| PUDAHUEL | nativo_drinks | MovNativoDrinks | NATIVO DRINKS SPA ← nuevo |
| PUDAHUEL | omnitech | MovOmnitech | OMNITECH ← nuevo |

**DERCO** = cliente heavy: chunking 7/3/1 días, timeout 6 min, 72k+ filas/mes.
**MovRuno**: deposito=PUDAHUEL UNITARIO, carpeta destino=CD PUDAHUEL.

## Archivos clave

| Archivo | Rol |
|---------|-----|
| `productividad_diario.py` | Script principal (949 líneas) |
| `productividad_config.py` | Catálogo clientes, EXPECTED_HEADERS, constantes |
| `productividad_utils.py` | Graph API, email, logging, SharePoint helpers |
| `logs/productividad_diario_checkpoint.json` | Checkpoint por cliente |
| `verificar_fechas.py` | Script de diagnóstico de fechas en archivos OneDrive |

## Task Scheduler
- **Tarea activa:** `Productividad Diario - EGA KAT` — Lun-Vie 10:30 AM
- Python: `C:\Users\Socrates Cabral\AppData\Local\Python\pythoncore-3.14-64\python.exe`
- Script: `C:\ClaudeWork\Productividad_Automatizacion\productividad_diario.py`
- Iniciar en: `C:\ClaudeWork`

## Estructura destino SharePoint
```
Productividad/
  CD QUILICURA/2026/04. Abril/MovMascota.xlsx
  CD PUDAHUEL/2026/04. Abril/MovUnilever.xlsx
  _backups/CD PUDAHUEL/2026/04. Abril/MovUnilever/YYYYMMDD_HHMMSS_MovUnilever.xlsx
```
Sync local: `OneDrive - EGA KAT LOGISTICA SPA\Datos para Dashboard - Productividad\`

## Columnas WMS (archivo real — más que EXPECTED_HEADERS)
El WMS genera columnas extra según cliente: Destino, Observaciones, Artículo.1, Descripción,
Litros, Kilos, M3, Cód.Externo ERP1/2/3, Trabajo, Pedido Fecha Preparado/Remitido/Despachado/Salida,
Viaje Nro. SGL, Viaje Cliente, Status, Transportista, Chofer, Dominio Vehículo/Remolque,
Valor asegurado, Dirección, Nro. Doc. Externo, Inf. Adicional 1.
Nombres con espacios sobrantes: `"Ubicación "`, `"Naturaleza "`.

## Historial de incidentes
- **2026-04-21**: Archivos de abril con fechas en formato MM/DD (script viejo). Corregidos manualmente.
  Diagnóstico: `verificar_fechas.py`. Causa: old script guardaba strings MM/DD, new script leía con dayfirst=True → NaT para días >12.
- **2026-04-21**: 2 clientes nuevos agregados: NATIVO DRINKS SPA + OMNITECH (PUDAHUEL).
