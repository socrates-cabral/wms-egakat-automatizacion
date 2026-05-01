---
title: KPI Operativo — Resumen JSON para Bot Telegram
type: proyecto
sources: [WMS_Automatizacion/generar_resumen_kpi_ops.py, WMS_Automatizacion/bots/_write_wf_ops.py]
related: [bot-ops-egakat, graph-api-microsoft, n8n-workflows]
updated: 2026-04-29
confidence: high
---

# KPI Operativo — generar_resumen_kpi_ops.py

**Script:** `WMS_Automatizacion/generar_resumen_kpi_ops.py`  
**Creado:** 2026-04-29 (Codex OpenAI)  
**Tamaño:** 4524 líneas, 184 KB  
**Estado:** ✅ Funcional, en testing

---

## Propósito

Genera un resumen JSON consolidado con KPIs operativos de múltiples fuentes Excel en OneDrive:

- **NNSS (Near Stock Status)** — Staging IN/OUT, ocupación, alertas operacionales
- **Productividad** — Movimientos diarios globales + por cliente + Derco detallado
- **Inventario** — Stock WMS, posiciones ocupadas/libres, conteos cíclicos

**Consumidor principal:** Bot Telegram `@EgakatOpsBot` vía workflow n8n.

---

## Arquitectura

```
┌─────────────────────────────────────────────┐
│  9 Carpetas OneDrive (compartidas externas) │
│  - NNSS Operacional                         │
│  - Productividad                            │
│  - Dimensiones (maestras)                   │
│  - Stock WMS Semanal                        │
│  - Staging IN/OUT                           │
│  - Posiciones                               │
│  - Inventario (Ubicaciones CDs)             │
│  - Registros conteos cíclicos               │
└─────────────────────────────────────────────┘
              ↓ (lectura OneDrive Desktop)
┌─────────────────────────────────────────────┐
│   generar_resumen_kpi_ops.py                │
│   - Lee Excel (pandas + openpyxl)          │
│   - Agrega por cliente, fecha, centro      │
│   - Calcula KPIs operativos                │
│   - Genera alertas + recomendaciones        │
└─────────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────────┐
│   tmp_resumen_kpi_ops_YYYYMMDD.json         │
│   Payload: { nnss, productividad,          │
│              inventario, alertas }          │
└─────────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────────┐
│   n8n workflow "Egakat Ops Bot WMS"         │
│   - Trigger: Mensaje Telegram              │
│   - Obtener Contexto: Lee JSON             │
│   - Consulta Claude: System msg + context  │
│   - Respuesta: Telegram                    │
└─────────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────────┐
│   @EgakatOpsBot (Telegram)                  │
│   Responde consultas operacionales 24/7     │
└─────────────────────────────────────────────┘
```

---

## Rutas OneDrive (9 carpetas)

**Por qué OneDrive Desktop, no Graph API:**

1. **Carpetas compartidas por externos** (Grupo Planet SpA) — permisos delegados complejos
2. **Solo lectura** — sin problemas de sincronización (no escribe)
3. **Graph API requeriría tokens del propietario externo** — no factible con application permissions

```python
NNSS_DIR = Path(
    r"C:\Users\Socrates Cabral\OneDrive - EGA KAT LOGISTICA SPA\Datos para Dashboard - NNSS Operacional"
)
PRODUCTIVIDAD_ROOT_OFICIAL = Path(
    r"...\Datos para Dashboard - Productividad"
)
DIMENSIONES_ROOT = Path(
    r"...\datos para Dashboard EK\Productividad"
)
STOCK_WMS_ROOT = Path(
    r"...\Datos para Dashboard - Stock WMS Semanal"
)
STAGING_ROOT = Path(
    r"...\Datos para Dashboard - Stagin IN- OUT"
)
POSICIONES_ROOT = Path(
    r"...\Datos para Dashboard - Consulta de Posiciones"
)
INVENTARIO_DIM_ROOT = Path(
    r"...\datos para Dashboard EK\Inventario"
)
CONTEOS_OFICIAL_ROOT = Path(
    r"...\Datos para Dashboard - Registros de conteos"
)
```

**En servidor 24/7:**  
Rutas resuelven vía **Symbolic Link** (FASE 3.5 guía migración):
```powershell
New-Item -ItemType SymbolicLink `
  -Path "C:\Users\Socrates Cabral" `
  -Target "C:\Users\egakat_admin"
```

---

## Payload JSON (estructura)

```json
{
  "periodo": "2026-04",
  "fecha_generacion": "2026-04-29 18:43:00",
  
  "fuentes": {
    "nnss": {
      "archivo": "NNSS Operacional 2026-04.xlsx",
      "fecha_modificacion": "2026-04-29 06:30:00"
    },
    "productividad": { ... },
    "dimensiones": { ... },
    "metas": { ... }
  },
  
  "nnss": {
    "total_ubicaciones_staging": 150,
    "ocupadas": 45,
    "disponibles": 105,
    "tasa_ocupacion": 0.30,
    "por_estado": {
      "STAGING IN": 28,
      "STAGING OUT": 17
    },
    "alertas": [
      "Alta ocupación CD QUILICURA: 82%"
    ]
  },
  
  "productividad": {
    "global": {
      "total_movimientos_mes": 12500,
      "movimientos_diarios_promedio": 450,
      "lineas_por_movimiento_promedio": 8.5
    },
    "diario": {
      "2026-04-28": { "movimientos": 520, "lineas": 4400 },
      "2026-04-29": { "movimientos": 480, "lineas": 4100 }
    },
    "por_fecha_cliente": {
      "2026-04-29": {
        "DERCO": { "movimientos": 180, "lineas": 1500 },
        "DAIKIN": { "movimientos": 45, "lineas": 380 }
      }
    },
    "derco": {
      "por_fecha": { ... },
      "ap_por_fecha": { ... },
      "canal_por_fecha": { ... }
    },
    "metas": {
      "mensual": 15000,
      "cumplimiento": 0.83
    }
  },
  
  "inventario": {
    "total_skus": 8500,
    "disponible": 7200,
    "posiciones": {
      "ocupadas": 12500,
      "libres": 3200,
      "tasa_ocupacion": 0.80
    },
    "conteo_ciclico": {
      "objetivo_mensual": 25288,
      "registrados": 18500,
      "cumplimiento": 0.73,
      "pendiente": 6788
    }
  },
  
  "alertas": [
    "Staging ocupación alta (82%) — considerar liberar PLTs",
    "Meta mensual productividad: 83% cumplimiento (17% pendiente)",
    "Conteo cíclico retrasado: 27% pendiente (6.788 items)"
  ],
  
  "recomendaciones": [
    "Priorizar despacho Staging OUT para liberar ubicaciones",
    "Acelerar conteos cíclicos para cumplir meta abril",
    "Revisar bottleneck preparación DERCO (180 mov/día vs histórico 220)"
  ]
}
```

---

## Integración n8n + Telegram

**Workflow:** `wf_bot_ops.json` (generado por `bots/_write_wf_ops.py`)

### Flujo de ejecución

1. **Trigger:** Usuario envía mensaje → `@EgakatOpsBot` (Telegram)
2. **Whitelist:** Verifica ID usuario autorizado (personal + grupo ops)
3. **Obtener Contexto:** Nodo HTTP lee `tmp_resumen_kpi_ops_YYYYMMDD.json`
4. **Consulta Claude:**
   - System message: "Eres el analista de operaciones WMS de Egakat SPA..."
   - Context: JSON completo inyectado (hasta 60KB, truncado inteligentemente si excede)
   - User message: Pregunta original de Telegram
5. **Respuesta:** Envía respuesta a Telegram (mismo chat)

### System Message (extracto)

> "Eres el analista de operaciones WMS de Egakat SPA, empresa chilena de logística 3PL.
> 
> Tu función es responder consultas internas sobre el estado del pipeline WMS, módulos de descarga,
> alertas operacionales, staging, posiciones, recepciones y productividad diaria.
> 
> Tienes el contexto operacional actual inyectado al final de este mensaje.
> Úsalo cuando pregunten sobre: estado del WMS, módulos ejecutados, fallos o advertencias,
> duración de la descarga, validación de archivos, staging, alertas operacionales,
> productividad diaria y productividad por cliente.
> 
> DEFINICIONES OPERACIONALES:
> - OK: módulo ejecutado sin errores ni fallos internos.
> - PARCIAL: módulo ejecutó pero tuvo fallos en algunos clientes o centros.
> - ADVERTENCIA: módulo OK pero con warnings conocidos (ej: cliente sin movimiento).
> - FALLO: módulo no ejecutó o falló completamente.
> - STAGING IN: pallets recién recibidos, pendientes de ubicación.
> - STAGING OUT: pallets preparados, pendientes de despacho.
> - MOVIMIENTO: traslado de mercancía (entrada, salida, ubicación, preparación).
> - LÍNEA: ítem individual dentro de un movimiento (1 mov puede tener N líneas).
> - DERCO: cliente principal (automotriz), tracking detallado AP + canal."

---

## Casos de Uso

| Consulta Telegram | Datos JSON usados | Respuesta esperada |
|-------------------|-------------------|--------------------|
| "¿Cómo está el staging hoy?" | `nnss.total_ubicaciones_staging`, `ocupadas`, `tasa_ocupacion` | "Staging 30% ocupado (45/150). 28 STAGING IN, 17 STAGING OUT." |
| "Productividad Derco últimos 3 días" | `productividad.derco.por_fecha` | Tabla: fecha, movimientos, líneas, promedio líneas/mov |
| "¿Cuánto falta para la meta mensual?" | `productividad.metas.mensual`, `global.total_movimientos_mes` | "Meta: 15.000 mov. Actual: 12.500 (83%). Faltan 2.500 (17%)." |
| "Alertas operacionales" | `alertas[]` | Lista de 3 alertas actuales (staging, meta, conteos) |
| "Estado conteo cíclico" | `inventario.conteo_ciclico.*` | "Conteo cíclico: 73% completado (18.500/25.288). Pendiente: 6.788 items." |
| "¿Hay bottlenecks hoy?" | `recomendaciones[]` | "Posible bottleneck preparación DERCO: 180 mov/día vs histórico 220." |

---

## Ejecución

### Manual
```bash
cd C:\ClaudeWork\WMS_Automatizacion
py generar_resumen_kpi_ops.py --year 2026 --month 4

# Output: tmp_resumen_kpi_ops_20260429.json
```

### Automatizada (pendiente implementar)

**Opción A:** Task Scheduler diario
```powershell
# Task Scheduler → "KPI Ops - Resumen Diario"
# Trigger: Diario 06:00 AM (antes de que inicie día operativo)
# Action: py C:\ClaudeWork\WMS_Automatizacion\generar_resumen_kpi_ops.py
```

**Opción B:** Trigger n8n bajo demanda
```
Mensaje Telegram → Workflow n8n
  ├─ Nodo Bash: Ejecutar generar_resumen_kpi_ops.py
  ├─ Esperar 30-60 seg (generación)
  └─ Leer JSON → Consulta Claude → Respuesta
```

**Recomendación:** Opción A (diario 06:00 AM) — datos pre-calculados, respuesta instantánea bot.

---

## Dependencias

### OneDrive Desktop
- ✅ **Necesario** para acceso carpetas compartidas externas
- Carpetas deben sincronizarse (OneDrive → Configuración → Elegir carpetas)
- Validar sincronización activa antes de ejecutar script

### Symbolic Link (servidor 24/7)
```powershell
# Crear enlace (PowerShell Admin)
New-Item -ItemType SymbolicLink `
  -Path "C:\Users\Socrates Cabral" `
  -Target "C:\Users\egakat_admin"

# Verificar
Test-Path "C:\Users\Socrates Cabral"  # → True
ls "C:\Users\Socrates Cabral"         # → carpetas egakat_admin
```

### Librerías Python
```bash
py -m pip install pandas openpyxl
# No requiere azure_graph.py (solo lectura local)
```

---

## Relación con otros proyectos

- **[[bot-ops-egakat]]** — Proyecto padre, @EgakatOpsBot
- **[[graph-api-microsoft]]** — NO usado aquí (solo OneDrive Desktop)
- **[[n8n-workflows]]** — Consumidor del JSON
- **[[proyectos/wms-automatizacion]]** — Scripts WMS que generan datos fuente

---

## Estado actual (2026-04-29)

| Componente | Estado | Pendiente |
|------------|--------|-----------|
| `generar_resumen_kpi_ops.py` | ✅ Completo (4524 líneas) | Test con datos reales mes completo |
| `bots/_write_wf_ops.py` | ✅ Completo (genera wf_bot_ops.json) | - |
| `wf_bot_ops.json` | ✅ Generado | Importar a n8n |
| @EgakatOpsBot | ⏳ Creado, webhook pendiente | Probar end-to-end |
| Task Scheduler | ❌ No configurado | Crear tarea diaria 06:00 AM |
| OneDrive sync servidor | ❌ No configurado | Seleccionar carpetas a sincronizar |

**Próximo milestone:** Bot respondiendo consultas operacionales (mayo 2026).

---

## Decisiones técnicas

### ¿Por qué no usar Graph API?

**Razón:** Carpetas compartidas por personas externas (Grupo Planet SpA).

**Problema con Graph API:**
- Application permissions (`Sites.ReadWrite.All`) → acceso como aplicación, no como usuario
- Carpetas compartidas requieren **delegated permissions** (actuar en nombre del usuario)
- Egakat no tiene tokens del usuario externo (Grupo Planet)

**Solución:** OneDrive Desktop con permisos compartidos → lectura local archivos sincronizados.

**Alternativa futura:** Si carpetas migran a SharePoint Egakat (no externo), entonces sí usar Graph API.

### ¿Por qué JSON liviano, no Excel directo?

**Razón:** Bot n8n consume JSON, no Excel.

**Ventajas JSON:**
- Parsing rápido (n8n + Claude)
- Tamaño compacto (~50-100 KB vs Excel ~5-10 MB)
- Fácil inyección en prompt Claude (context expression)
- Versionable (Git, si se commitea histórico)

**Desventaja:** Requiere script intermedio (este).

---

## Próximos pasos

1. ✅ **Completado:** Scripts `generar_resumen_kpi_ops.py` + `_write_wf_ops.py`
2. ⏳ **Importar workflow a n8n** — `wf_bot_ops.json` → n8n UI
3. ⏳ **Probar bot end-to-end** — Mensaje Telegram → Respuesta con KPIs
4. ❌ **Configurar Task Scheduler** — Diario 06:00 AM
5. ❌ **Monitorear logs** — Verificar errores lectura OneDrive, archivos faltantes
6. ❌ **Documentar casos de uso internos** — Equipo ops debe conocer capacidades bot

**Meta:** Bot ops 100% funcional para mayo 2026.
