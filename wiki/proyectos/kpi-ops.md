---
title: KPI Operativo — Resumen JSON para Bot Telegram
type: proyecto
sources: [WMS_Automatizacion/generar_resumen_kpi_ops.py, WMS_Automatizacion/api_operaciones.py]
related: [bot-ops-egakat, graph-api-microsoft, n8n-workflows]
updated: 2026-05-02
confidence: high
---

# KPI Operativo — generar_resumen_kpi_ops.py

**Script:** `WMS_Automatizacion/generar_resumen_kpi_ops.py`  
**Tamaño:** ~5500 líneas (actualizado con historico mensual/YTD)  
**Estado:** ✅ Funcional — genera JSON con historico completo

---

## Propósito

Genera un resumen JSON consolidado con KPIs operativos de múltiples fuentes Excel en OneDrive:

- **NNSS** — OTIF, Fill Rate, staging, ocupación
- **Productividad** — líneas/unidades/pedidos por cliente, DERCO AP detallado
- **Inventario** — Stock WMS, posiciones, conteos cíclicos
- **Historico** — datos mensuales y YTD enero-N mes del año

**Consumidor principal:** Bot Telegram `@EgakatOpsBot` vía API Flask (puerto 8086) → workflow n8n.

---

## Estructura del JSON generado

```json
{
  "disponible": true,
  "fecha_generacion": "2026-05-02 08:33:36",
  "nnss": { "otif": {...}, "fillrate": {...}, "staging": {...} },
  "productividad": { "por_cliente": [...], "derco_ap": {...} },
  "inventario": { "stock": {...}, "posiciones": {...} },
  "historico": {
    "disponible": true,
    "periodo_cobertura": { "anio": 2026, "desde_mes": 1, "hasta_mes": 4 },
    "criterio_historico": "cierre_recalculado",
    "origen_historico": "recalculado_desde_fuente_viva",
    "nnss": {
      "otif_mensual": [...],     // 48 filas (12 clientes × 4 meses)
      "otif_ytd": [...],         // 12 filas (1 por cliente)
      "fillrate_mensual": [...], // 48 filas — metodología ratio de sumas
      "fillrate_ytd": [...]      // 12 filas
    },
    "productividad": {
      "mensual_cliente": [...],
      "ytd_cliente": [...],
      "derco_ap_mensual": [...], // 12 filas
      "derco_ap_ytd": [...]      // 3 filas (AP Total, AP Rack, AP Estantería)
    }
  },
  "alertas": [...],
  "recomendaciones": [...]
}
```

---

## Ejecución

```powershell
# Generar resumen mes actual
py C:\ClaudeWork\WMS_Automatizacion\generar_resumen_kpi_ops.py --year 2026 --month 4

# Output: C:\ClaudeWork\logs\resumen_kpi_ops_YYYYMMDD.json
# Tiempo: ~15-20 minutos (procesa Excel de 4 meses)
```

**Argumentos:**
- `--year`: año del periodo (default: año actual)
- `--month`: mes hasta el cual calcular historico (default: mes actual)
- `--output`: ruta alternativa de salida
- `--inspect-only`: solo muestra fuentes detectadas, no genera JSON
- `--verbose`: output detallado

---

## API Flask — api_operaciones.py

**Puerto:** 8086  
**Autenticación:** Header `X-API-Key: API_OPS_SECRET` (desde .env)

### Endpoint principal:
```
GET /ops/contexto/resumen
```
Devuelve JSON consolidado incluyendo `kpi_ops` con el resumen más reciente.

**Selección de archivo:** `_ruta_resumen_kpi_ops_reciente()` — toma el JSON con fecha más alta en nombre (`resumen_kpi_ops_YYYYMMDD.json`), con fallback por mtime.

### Estructura respuesta:
```json
{
  "kpi_ops": {
    "disponible": true,
    "fuente": "C:\\ClaudeWork\\logs\\resumen_kpi_ops_20260502.json",
    "fecha_archivo": "2026-05-02 08:33:36",
    "nnss": {...},
    "productividad": {...},
    "inventario": {...},
    "historico": {...},   // ← clave para consultas históricas del bot
    "alertas": [...],
    "recomendaciones": [...]
  }
}
```

---

## Fill Rate — Metodología Dual

| Fuente | Cálculo |
|--------|---------|
| `kpi_ops.nnss.fillrate` (actual) | Promedio simple de `fr_calculado` por fila |
| `historico.nnss.fillrate_mensual/ytd` | Razón de sumas: `Σnumerador / Σdenominador` |

Si el usuario compara Fill Rate actual vs histórico y nota diferencias, explicar diferencia metodológica (no es error).

---

## Reglas de Historico (para el bot)

1. Mes anterior → usar `historico.nnss.otif_mensual` filtrado por mes
2. YTD → usar `historico.nnss.otif_ytd` (NO calcular desde mensuales)
3. `criterio_historico = cierre_recalculado` → valores pueden diferir levemente del cierre operativo
4. Si `historico == null` → responder "no disponible en contexto actual"
5. DERCO AP → AP Total ≠ AP Rack + AP Estantería (universos distintos)
6. `pedidos_unicos_acum` en ytd_cliente ≠ suma de mensuales

---

## Fix JS — `_FINAL_preparar_contexto_ai.js` (2026-05-02)

**Problema:** La condición `periodoSolicitadoNoDisponible` activaba `control_periodo` para cualquier período pasado aunque `kpi_ops.historico` tuviera datos para ese período. El bloque hacía early return eliminando historico del contexto.

**Fix:** Función `historicoTienePeriodo(kpiTipo, mes, anio, esYtd)` que verifica presencia de filas en:
- `historico.nnss.otif_mensual` / `otif_ytd`
- `historico.nnss.fillrate_mensual` / `fillrate_ytd`
- `historico.productividad.mensual_cliente` / `ytd_cliente`
- `historico.productividad.derco_ap_mensual` / `derco_ap_ytd`

**Dos ramas de decisión:**
1. `(periodoSolicitadoNoDisponible || ytdSinHistorico || comparativoSinHistorico) && !historicoResponde` → `control_periodo`
2. `(periodoSolicitadoNoDisponible || es_ytd || es_comparativo) && historicoResponde` → early return con `kpi_ops.historico` + `consulta_historico` hint

**Casos validados OK:**
- "OTIF de DERCO en marzo" → devuelve `historico.nnss.otif_mensual`
- "Fill Rate de febrero" → devuelve `historico.nnss.fillrate_mensual`
- "productividad DERCO AP YTD" → devuelve `historico.productividad.derco_ap_ytd`
- "OTIF DERCO" (mes actual) → flujo normal `esOTIF` sin toca historico
