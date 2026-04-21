---
title: Productividad Automatización — Descarga Diaria Incremental
type: proyecto
sources: [Productividad_Automatizacion/productividad_config.py, Productividad_Automatizacion/productividad_diario.py, Productividad_Automatizacion/productividad_descarga.py]
related: [fillrate-automatizacion, wms-automatizacion, graph-api-microsoft]
updated: 2026-04-21
confidence: high
---

# Productividad Automatización

## Estado — PRODUCCIÓN (2026-04-21)
Dos scripts coexisten con roles distintos:

| Script | Función | Schedule | Email |
|--------|---------|----------|-------|
| `productividad_diario.py` | Append incremental diario | Task Scheduler 10:30 AM | TESTING_MODE=True → solo Sócrates |
| `productividad_descarga.py` | Mes completo, reemplaza archivo | Manual (reprocesos) | Siempre a todos |

**TESTING_MODE = True** en diario — cambiar a False cuando validado 2-3 días automáticos.

## Clientes activos — 17 (actualizado 2026-04-21)

| CD | Key | Alias archivo | Empresa WMS | Nota |
|----|-----|--------------|-------------|------|
| QUILICURA | abinbev | MovABInbev | CERVECERIA ABI | |
| QUILICURA | bha | MovBha | BHA | |
| QUILICURA | daikin | MovDaikin | DAIKIN | |
| QUILICURA | pochteca | MovPochteca | POCHTECA | |
| QUILICURA | mascota_quilicura | MovMascota | MASCOTAS LATINAS | |
| QUILICURA | derco | MovDerco | DERCO | heavy: chunking 7/3/1d, timeout 6min |
| PUDAHUEL | barentz | MovBarentz | BARENTZ | |
| PUDAHUEL | buraschi | MovBuraschi | BURASCHI | |
| PUDAHUEL | cepas_chile | MovCepas Chile | CEPAS CHILE | |
| PUDAHUEL | collico | MovCollico | COLLICO | |
| PUDAHUEL | delibest | MovDelibest | DELIBEST | |
| PUDAHUEL | intime | Movintime | INTIME | |
| PUDAHUEL | tresmontes | Movtresmontes | TRES MONTES | |
| PUDAHUEL | unilever | MovUnilever | UNILEVER | |
| PUDAHUEL UNITARIO | runo | MovRuno | RUNO SPA | deposito≠carpeta |
| PUDAHUEL | nativo_drinks | MovNativoDrinks | NATIVO DRINKS SPA | nuevo 2026-04-21 |
| PUDAHUEL | omnitech | MovOmnitech | OMNITECH | nuevo 2026-04-21 |

## Formato de fechas WMS
WMS genera HTML con fechas **DD-MM-YYYY con guiones** (ej. `02-04-2026`).
Scripts leen con `dayfirst=True` → correcto.
productividad_diario.py escribe a xlsx como string `DD/MM/YYYY`.

## historical_reference
Requerido por `productividad_descarga.py` para validar estructura de cabeceras.
nativo_drinks y omnitech usan MovBarentz enero 2026 como plantilla (misma estructura PUDAHUEL 50 cols).

## Lógica diario (productividad_diario.py)

### Ventana de descarga
- `from_dt` = checkpoint 08:00 | `to_dt` = hoy 06:00
- Lunes: cubre fin de semana
- Feriados: skip (lee `Tabla Feriados.xlsx`)
- Gap: checkpoint no avanza si falla → se recupera solo

### Dedup key
`["Comprobante", "Comprobante externo", "Artículo", "Fecha", "Hora", "Número"]`

### Email — diferencia clave vs script viejo
- "Al día" = ventana vacía, nada nuevo que bajar (correcto, no es error)
- Movimientos = filas nuevas de esa ejecución, no total acumulado
- El script viejo siempre muestra el total porque descarga el mes entero

## Estructura destino SharePoint
```
Productividad/
  CD QUILICURA/2026/04. Abril/MovMascota.xlsx
  CD PUDAHUEL/2026/04. Abril/MovUnilever.xlsx
  (sin _backups — eliminada 2026-04-21, WMS es fuente de verdad)
```
Sync local: `OneDrive - EGA KAT LOGISTICA SPA\Datos para Dashboard - Productividad\`

## Archivos clave

| Archivo | Rol |
|---------|-----|
| `productividad_diario.py` | Script principal incremental |
| `productividad_descarga.py` | Script reproceso mes completo |
| `productividad_config.py` | Catálogo 17 clientes, constantes |
| `productividad_utils.py` | Graph API, email, SharePoint helpers |
| `logs/productividad_diario_checkpoint.json` | Checkpoint por cliente |
| `verificar_fechas.py` | Auditoría fechas archivos OneDrive local |

## Task Scheduler
- **ACTIVA**: `Productividad Diario - EGA KAT` — Lun-Vie 10:30 AM → productividad_diario.py
- **DESHABILITADA**: `Productividad Egakat - Descarga Diaria` (script viejo)

## Historial incidentes
- **2026-04-21**: Archivos históricos de abril en formato MM/DD (script viejo). Corregidos manualmente.
  Causa: old script almacenaba strings MM/DD, new script leía con dayfirst=True → NaT días >12.
  Herramienta: verificar_fechas.py
- **2026-04-21**: 2 clientes nuevos: NATIVO DRINKS SPA + OMNITECH.
  Bug: faltaba `historical_reference` → KeyError en productividad_descarga.py. Fix: apuntar a MovBarentz.
- **2026-04-21**: Backup remoto SharePoint eliminado de ambos scripts + carpeta _backups borrada.
