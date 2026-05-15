---
title: Canal Derco Auto — Automatización columna Canal en data Derco.xlsx
type: proyecto
sources: [WMS_Automatizacion/canal_derco_auto.py, WMS_Automatizacion/canal_derco_utils.py, WMS_Automatizacion/generar_resumen_kpi_ops.py, FillRate_Automatizacion/run_fillrate.bat]
related: [fillrate-automatizacion, kpi-ops, bot-ops-egakat, wms-automatizacion]
updated: 2026-05-15
confidence: high
---

# Canal Derco Auto — `canal_derco_auto.py`

**Script:** `WMS_Automatizacion/canal_derco_auto.py`
**Utilidades compartidas:** `WMS_Automatizacion/canal_derco_utils.py`
**Estado:** ✅ Funcional, en producción dentro de `run_fillrate.bat` (Task Scheduler 9:05)
**Fecha de puesta en marcha:** 2026-05-14

---

## Propósito

Recalcula la columna **Canal** del archivo `data Derco.xlsx` (cliente DERCO/Grupo Planet) de forma automática, eliminando la dependencia de la hoja manual `Pedidos Rack-ET` que el usuario actualizaba a mano y que generaba canales errados.

**Canales producidos:** `AP_R`, `AP_E`, `CES`, `GT`, `SG`, `CAP`, `MY`, `LB`.

---

## Problema que resuelve

La fórmula original en Excel para la columna `Canal` dependía de:

1. La hoja `Pedidos Rack-ET` (manual, actualizada esporádicamente desde el reporte de Productividad).
2. La columna `Llave Canal` derivada de `Nro Pedido` + `Cliente`.

Dos defectos críticos:

- **Hoja manual desactualizada** → 553 filas quedaban como "AP" sin clasificar (no se sabía si Rack o Estantería) y los AP_R/AP_E existentes podían estar errados.
- **`Nro Pedido` corrupto en notación científica** ("9,1E+09") → 6.120 filas (18%) tenían su Llave Canal mal calculada y caían incorrectamente a "MY", camuflando AP, CAP, SG y CES dentro de MY.

**Impacto medido al implementar (1ra corrida real, 2026-05-14):** 8.205 filas salieron de MY hacia su canal correcto. AP sin clasificar bajó de 553 a 1 (esa única OP era válida: pedido en "En Preparación" sin picking aún en MovDerco).

---

## Arquitectura

### Flujo

```
data Derco.xlsx ──┐
                  │  (cruce por Nro Aplica = OP, 100% match verificado)
                  ▼
         canal_derco_auto.py ──► reescribe SOLO columna Canal
                  ▲
MovDerco *.xlsx ──┤  (todos los meses 2026: 6 archivos, ~512K líneas picking)
                  │
Base CES.xlsx ────┘  (concesionarios; ubicada en SP / Archivos Soporte)
```

### Llaves de cruce

| data Derco | ↔ | MovDerco |
|---|---|---|
| `Nro Aplica` (OP) | ↔ | `Comprobante` (limpio, único, 100% match) |
| `Nro Pedido` | ↔ | `Comprobante externo` (recuperado vía OP, sin corrupción) |
| `Cliente` | ↔ | `Destino` (truncado a 20 chars en ambos) |

**OP es la llave correcta**, no `Nro Pedido + Cliente`: el Nro Pedido en data Derco está corrupto en notación científica para 18% de las filas, mientras que OP es int64 limpio.

### Rutas físicas

```
data Derco.xlsx        C:\Users\Socrates Cabral\OneDrive - EGA KAT LOGISTICA SPA\
                       Datos para Dashboard - NNSS Operacional\Quilicura\

MovDerco *.xlsx        C:\Users\Socrates Cabral\OneDrive - EGA KAT LOGISTICA SPA\
                       Datos para Dashboard - Productividad\CD QUILICURA\2026\NN. Mes\

Base CES.xlsx          C:\Users\Socrates Cabral\OneDrive - EGA KAT LOGISTICA SPA\
                       Datos para Dashboard - NNSS Operacional\Archivos Soporte\
```

---

## Reglas de negocio (confirmadas 2026-05-14)

### Clasificación de ubicación (vive en `canal_derco_utils.py`)

| Patrón ubicación | Clasificación |
|---|---|
| `P-EST-*`, `I-BBR-*`, `QE\d*` | Estantería (`EST`) |
| `Q\d*` (no QE) | Rack (`RACK`) |
| `QP*`, `MAQ*`, `PISOD*`, `ANDEN-*`, `INV1-*` | Piso (`PISO`) — cuenta como Rack |
| Resto (default) | Rack — monitoreado por métrica |

Auditoría inicial sobre 511.938 líneas: 0 ubicaciones caen en el default catch-all.

### Resolución del canal por OP

1. **Canal principal** se calcula desde MovDerco (datos limpios) usando la clave `Comprobante_externo[:2] + Destino[:4]`:
   - `46AP00` → AP
   - `31SODI`, `31WALM`, `31EASY`, `31REND`, `31HIPE` → GT
   - `46SG00` → SG
   - `91SG00`, `91AP00`, `91CORO` → CAP
   - `55LO B` → LB
   - resto → MY

2. **Si AP**: desempate Rack vs Estantería **por predominio de líneas**. Empate → AP_R.

3. **Si MY y el Destino matchea Base CES**: → CES (separa concesionarios de mayoristas).

4. **OP sin picking en MovDerco**: se conserva el Canal previo (caso típico: pedido en Estado "En Preparación" sin líneas pickeadas aún).

### Cruce CES (Base CES)

- `Base CES.xlsx` tiene 2 hojas: `base 1` (157 concesionarios — fuente sólida) y `base 2` (35 concesionarios). Validación automática base 2 ⊆ base 1.
- El nombre de empresa en MovDerco `Destino` viene **truncado a 20 chars** y a veces con sufijo `/sucursal` ("AUTOMOTRIZ DENALI SP", "Anfruns Carmen 641/Sant").
- Match: separar antes del `/`, normalizar (mayúsculas, sin puntuación), aceptar prefix-match con n ≥ 10 chars.

### Estado del pedido como criterio de "definitivo"

Una fila es **definitiva** cuando su OP llega a Estado **"Con Salida"**. Antes de eso (estados "En Preparación", "Preparados") el picking puede seguir creciendo y el predominio Rack/Est podría cambiar. El recálculo completo en cada corrida garantiza auto-corrección de las filas provisionales sin intervención manual.

### Diferencia bot WMS Ops vs data Derco por estado

| Estado del pedido | Aparece en MovDerco | Aparece en data Derco |
|---|---|---|
| En Preparación | NO (sin picking todavía) | SÍ |
| Preparados | SÍ | SÍ |
| Con Salida | SÍ | SÍ |
| Despachado | SÍ | SÍ |
| Remitido | SÍ | SÍ |

**Implicacion:** el bot WMS Ops (que lee MovDerco) **nunca puede ver** los pedidos en "En Preparación". data Derco sí los lista y los marca como "AP" sin clasificar hasta que avancen de estado. Por eso el universo "AP del mes" del bot suele ser ligeramente menor que el de data Derco para el mismo mes — la diferencia son los pedidos del mes recién ingresados que aún no se pickean.

Tampoco se debe esperar coincidencia exacta entre "líneas AP_Rack" del bot y "filas AP_R" de data Derco: el bot cuenta cada línea individual de MovDerco; data Derco clasifica cada pedido completo por predominio. Un pedido con 1 línea Rack + 9 Estantería suma "1 Rack + 9 Est" al bot, pero queda como AP_E en data Derco.

---

## Operación

### Invocación

```powershell
# Recálculo completo (modifica data Derco.xlsx, hace backup primero):
py WMS_Automatizacion\canal_derco_auto.py

# Validación sin escribir nada:
py WMS_Automatizacion\canal_derco_auto.py --dry-run
```

### Cableado en producción

`FillRate_Automatizacion/run_fillrate.bat` (Task Scheduler diario 9:05):

```bat
1. fillrate_descarga.py        ← descarga WMS, refresca data Derco.xlsx
2. canal_derco_auto.py         ← recalcula columna Canal       [AGREGADO 2026-05-14]
3. generar_resumen_kpi_ops.py  ← JSONs para bot Telegram
```

### Salvaguardas

- **Backup automático** antes de escribir: `WMS_Automatizacion/_backups_data_derco/data Derco_BACKUP_<ts>.xlsx` — se conservan los últimos 5.
- **Solo reescribe la columna Canal** vía openpyxl (preserva fórmulas de otras hojas, pivots, formato).
- MovDerco y Base CES en modo solo-lectura.

### Logs y métricas

- **Log por corrida:** `C:\ClaudeWork\logs\canal_derco_<YYYY-MM-DD_HHMMSS>.log` — incluye comparación canal antes/después, diagnóstico CES (concesionarios detectados vs sin pedidos), advertencias.
- **CSV acumulativo de métricas:** `C:\ClaudeWork\logs\canal_derco_metricas.csv` — una fila por corrida con tiempos por fase + tamaños. Útil para graficar la evolución del runtime conforme crecen los datos.

Métricas registradas:
```
fecha; modo; movderco_lineas; ops_movderco; filas_data_derco;
filas_provisionales; ubicaciones_sin_regla;
t_base_ces_s; t_movderco_s; t_resumen_op_s; t_lectura_calculo_dd_s; t_backup_escritura_s; t_total_s
```

**Tiempo típico (mayo 2026):** ~150-180 s. El cuello de botella es la lectura completa de los 6 MovDerco (~80% del tiempo).

---

## Fase 2 — Alineación con el bot WMS Ops (2026-05-15)

`generar_resumen_kpi_ops.py` (que alimenta el bot de Telegram con líneas AP_Rack/AP_Estantería) lee MovDerco crudo línea por línea y antes clasificaba Rack/Est usando la **tabla dimensión** `Tabla Ubicaciones CDs.xlsx`. Eso podía generar splits distintos a los de `data Derco.xlsx`.

**Cambio quirúrgico:** ambos scripts ahora importan `clasificar_ubicacion_dim` desde el módulo compartido `canal_derco_utils.py`. Una sola fuente de verdad para Rack/Est.

**Delta verificado** (Abril 2026, pre vs post Fase 2):

| | Pre (DimUbicaciones) | Post (regla prefijos) | Δ |
|---|---|---|---|
| AP total líneas | 108.042 | 108.042 | 0 ✓ |
| AP Rack líneas | 62.621 | 62.612 | −9 |
| AP Estantería líneas | 45.421 | 45.430 | +9 |

Solo 9 líneas (0,008%) se reclasificaron de Rack→Est. Total AP conservado. Campo `ap_detalle_metodo` ahora reporta `"regla_prefijos"` en vez de `"dimubicaciones"`.

---

## Decisiones técnicas no obvias

- **Llave OP, no pedido+cliente** — `Nro Pedido` está corrupto en notación científica para 18% de las filas; `Nro Aplica` (OP) es int64 limpio, único, 100% match contra MovDerco.
- **Recálculo completo cada corrida**, no incremental — es auto-sanador (los pedidos en "En Preparación" se clasifican solos cuando llegan a "Con Salida"), idempotente, sin estado que mantener. ~150-180 s por corrida es aceptable para un batch diario.
- **Backup en local (no SP)** — `_backups_data_derco/` está bajo el repo, no en OneDrive, para no sincronizar basura a SharePoint y mantener la carpeta SP limpia.
- **CES por prefix-match con threshold 10 chars** — el `Destino` de MovDerco truncado a 20 chars no permite match exacto contra Base CES (solo 5 de 157 matchean exacto). Prefix-match con n ≥ 10 captura 75 concesionarios distintos / 2.094 OPs en el periodo.
- **Default de `clasificar_ubicacion` = RACK** + métrica de auditoría — el catch-all es necesario para no romper si aparece una ubicación nueva, pero la métrica `ubicaciones_sin_regla` permite detectar cuándo agregar regla explícita.
- **No se modifica la columna `Llave Canal`** — es un intermedio histórico; se reescribe solo `Canal` con valores ya correctos.

---

## Dependencias

- `WMS_Automatizacion/canal_derco_utils.py` — funciones compartidas con generar_resumen_kpi_ops.py
- pandas, openpyxl
- OneDrive sincronizado (rutas absolutas a Datos para Dashboard - *)
- `fillrate_descarga.py` debe correr antes (refresca filas de data Derco)

---

## Pendientes / mejoras futuras

- **Optimización runtime** (cuando se vuelva molesto): leer solo MovDerco del mes actual + anterior + reprocesar solo filas con Estado ≠ "Con Salida". Bajaría de ~150 s a ~30-40 s.
- **Bot Telegram** podría mostrar el campo `ap_detalle_metodo` para transparencia del método de clasificación.
- **CES sucursales sin match** — algunos concesionarios de Base CES quedan sin pedidos detectados por la combinación truncado/sufijo. Si Base CES se pudiera obtener con nombres también ≤20 chars (igual al Destino MovDerco), el match sería exacto.
