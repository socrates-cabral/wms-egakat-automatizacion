---
title: KPI Operativo — Resumen JSON para Bot Telegram
updated: 2026-05-10
type: proyecto
sources: [WMS_Automatizacion/generar_resumen_kpi_ops.py, WMS_Automatizacion/api_operaciones.py]
related: [bot-ops-egakat, graph-api-microsoft, n8n-workflows]
updated: 2026-05-09
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

## Pipeline automatizado (2026-05-08)
`generar_resumen_kpi_ops.py` ahora corre automáticamente al final de:
- `run_fillrate.bat` (Task Scheduler 9:05)
- `run_productividad.bat` (Task Scheduler 10:05)

Garantiza que el bot tenga data fresca sin intervención manual.

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

---

## OTIF por CD — Fix completo (2026-05-09)

### Raíz del problema (diagnosticado vía Claude.ai)
`esOTIF` block en `_FINAL_preparar_contexto_ai.js` compactaba `otif` pero descartaba `otif.por_cd`. La data existía en la API pero nunca llegaba al LLM.

### 3 fixes aplicados en `_FINAL_preparar_contexto_ai.js`:
1. **`por_cd` en contexto:** `otifCompacto` ahora incluye `por_cd` (array completo), `por_cd_filtrado` (filtrado por CD del mensaje via `normText(x.cd) === cdSolicitado`) y `regla_otif_por_cd` (instrucción dinámica que nombra el CD solicitado).
2. **`esOTIF` ampliado:** Añadidos `msg.includes('in full')`, `msg.includes('infull')`, `msg.includes('on time')` — sin estos, preguntas de motivos IF/OT no entraban al bloque correcto.
3. **Regla anti-confusión:** `regla_otif_por_cd` prohíbe usar `pedidos_no_evaluables_detalle` (pedidos pendientes, concepto distinto) para responder motivos IF/OT.

### 3 fixes en `generar_resumen_kpi_ops.py` (`calcular_otif_por_pedido`):
Cada entrada de `otif.por_cd` ahora incluye:
```python
"motivos_no_in_full": [{"motivo": m, "lineas": c} for m, c in Counter(motivos_cd).most_common(10)]
"detalle_no_in_full": [{"nro_pedido", "cliente", "estado", "motivos": [...]}]  # por pedido
"detalle_no_on_time": [{"nro_pedido", "cliente", "estado", "es_arrastre"}]     # por pedido
```
Mismo patrón que `por_cliente`. Tracking via `detalle_no_ot_por_cd`, `detalle_no_if_por_cd`, `motivos_no_if_por_cd` (defaultdict).

### Valores validados (abril 2026):
| CD | Evaluados | OTIF % | No OT | No IF |
|----|-----------|--------|-------|-------|
| QUILICURA | 872 | 91,40 % | 54 (todos DERCO) | 31 (30 DERCO + 2 MASCOTAS) |
| PUDAHUEL | 15 | 86,67 % | 0 | 2 (ambos UNILEVER) |

### System prompt (`_FINAL_system_message.txt`) — Regla 6 ampliada:
- Para motivos no IF: usar `motivos_no_in_full` (agregado) + `detalle_no_in_full` (por pedido)
- Para pedidos no OT: usar `detalle_no_on_time`
- Prohibido usar `pedidos_no_evaluables_detalle` para estas preguntas

---

## Desglose canales DERCO — Fix (2026-05-10)

**Síntoma:** Consulta "separa AP, MY, SG, CAP, CES y GT" → bot sin respuesta. No incluía keywords "canal" ni "DERCO" explícitos.

### Canales DERCO y su origen

Canal derivado en `calcular_canal_derco()` combinando `Comprobante externo[:2]` + `Destino[:4]` del WMS MovDerco.xlsx:

| Clave | Canal | Ejemplo Destino |
|-------|-------|-----------------|
| `46AP00` | AP | AP0066-San Pablo Qui |
| `31SODI/WALM/EASY/REND/HIPE` | GT | SODIMAC, WALMART, EASY... |
| `46SG00` | SG | SG0001-... |
| `91SG00/AP00/CORO` | CAP | — |
| default | MY | — |

AP se subdivide en AP_R (Rack) y AP_E (Estantería) según `Tipo_Ubicacion_Dim`. **CES no existe** en datos DERCO.

### Cambios en `_FINAL_preparar_contexto_ai.js`

```javascript
// Detector — no requiere "canal" ni "DERCO" explícito
const _DERCO_CANAL_KEYS = ['my', 'sg', 'cap', 'gt', 'ces'];
const pideDercoCanales = _dercoCanalesCount >= 2 ||
    (msg.includes(' ap') && _dercoCanalesCount >= 1) ||
    msg.includes('ap rack') || msg.includes('ap estanteria') ||
    (msg.includes('rack') && msg.includes('estanteria'));

// Handler expone ambas versiones
prodCompacta.derco_canales = {
  canales: prod.derco.canales,           // AP agrupado (AP_R+AP_E → AP)
  canales_originales: prod.derco.canales_originales,  // AP_R y AP_E separados
  nota: 'CES no existe en datos DERCO — indicarlo si se pregunta.'
};
```

### Valores validados mayo 2026 (parcial, vs WMS directo)

| Canal | Bot | WMS | Match |
|-------|-----|-----|-------|
| AP | 26.445 | 26.445 | ✓ |
| MY | 1.580 | 1.580 | ✓ |
| SG | 67 | 67 | ✓ |
| CAP | 562 | 562 | ✓ |
| GT | 295 | 295 | ✓ |
| AP_R + AP_E | 15.642 + 10.803 | — | = 26.445 ✓ |

**Commits:** 953f264 → 547c2c6 → 574657a

### Gotcha: Canal_Agrupado vs Canal_Principal

```python
# Línea 1600 — Canal_Agrupado agrupa CAP+MY+SG intencionalmente
df["Canal_Agrupado"] = df["Canal_Principal"].map(
    lambda c: "CAP-MY-SG" if c in {"CAP", "MY", "SG"} else c
)
```

Para el historico usar siempre `Canal_Principal` (separado: MY, SG, CAP, GT, AP). `Canal_Agrupado` es solo para la vista consolidada del período actual.

**Validado abril 2026:** CAP 2.430 + MY 7.347 + SG 288 = 10.065 ✓ (idéntico al grupo anterior)
