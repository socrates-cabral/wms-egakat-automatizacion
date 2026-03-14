# MEMORY.md — Proyecto Chiquito Finanzas
**Responsable:** Sócrates Cabral (hermano)
**Empresa analizada:** Negocio de Muebles "Chiquito" — Santiago, Región Metropolitana, Chile
**Última actualización:** 14-Mar-2026
**Directorio del proyecto:** `C:\ClaudeWork\chiquito_financiero\` *(mover aquí cuando ejecute Claude Code)*

---

## 1. ORIGEN DEL PROYECTO

El negocio de la hermana fabrica y vende muebles (estanterías, closets, muebles de cocina, proyectos a medida) en Santiago RM. Lleva operando con pérdidas recurrentes. Sócrates identificó la necesidad de un diagnóstico financiero profesional y herramientas de gestión que la hermana pueda usar sin ser financiera.

---

## 2. ARCHIVO FUENTE

**Nombre:** `1773448670534_Chiquito_Act_10_02.xlsx`
**Hojas totales:** 21 (5 visibles, 16 ocultas)

### Hojas analizadas:
| Hoja | Contenido | Estado |
|------|-----------|--------|
| `MP` | Materiales fabricación + costo estantería estándar | Visible |
| `Gastos_03_25` | Extracto bancario + gastos marzo 2025 | Oculta |
| `Crédito` | Detalle crédito Santander + Banco Estado + pagos recibidos | Oculta |
| `Deuda` | Resumen todas las deudas + calendario pagos | Oculta |
| `Estatería_Estándar` | Costos por variante de producto | Visible |
| `Analisis_Compra` | Cotización por volumen (100 muebles) | Oculta |
| `Ventas` | Registro ventas diarias Mar-2025 y Jul-2025 | Oculta |
| `Mueble_Lavaplato` | Costeo mueble cocina + variantes | Visible |
| `Hoja3` | Planificación proyectos (Odontología, Departamento) | Oculta |
| `Proyecto_Lyanne` | Presupuesto proyecto grande (repisas, mesón, cocina, tabique) | Oculta |
| `Hoja5` | Tracker ventas enero 2025 (vacío) | Oculta |
| `Hoja2` | Análisis compra por pallets Imperial | Oculta |
| `Gastos_02_25` | Gastos febrero 2025 — Total $1,317,439 | Oculta |
| `Alquiler_taller` | Acuerdo alquiler nuevo taller Macul (may-2025) | Oculta |
| `2do_pallet` | Planificación corte 2° pallet de melamina | Oculta |
| `Hoja4` | Costeo estantería alternativa | Oculta |
| `Hoja6` | Cotización proyecto herrería (Cargioli + carpintería) | Oculta |
| `Deuda_2026` | Deuda consolidada inicial 2026 | Oculta |
| `Cajas` | Libro de caja Nov-Dic 2025 (detalle diario) | Visible |
| `Cajas_2026` | Libro de caja Ene-Mar 2026 (detalle diario, hasta 11-Mar) | Visible |
| `Deuda_2026 actual` | Deuda actualizada 2026 con nuevas deudas | Visible |

---

## 3. DATOS FINANCIEROS EXTRAÍDOS

### Flujo mensual real (del libro de caja):
| Mes | Ingresos | Gastos Op. | Resultado Op. |
|-----|----------|------------|---------------|
| Nov-2025 | $1,721,170 | $2,025,470 | -$304,300 |
| Dic-2025 | $3,024,913 | $2,715,420 | +$309,493 |
| Ene-2026 | $1,625,820 | $1,601,683 | +$24,137 |
| Feb-2026 | $1,964,928 | $1,617,387 | +$347,541 |
| Mar-2026* | $2,400,000 | $2,200,000 | +$200,000 |
| **Promedio** | **$1,859,000** | **$1,832,000** | **+$27,000** |
*Mar-2026 estimado con datos parciales al 11-Mar

### Estructura de deuda (hoja `Deuda_2026 actual`):
| Instrumento | Tipo | Saldo | Cuota/mes | Tasa est. |
|-------------|------|-------|-----------|-----------|
| Banco Itau | Crédito + TC | $5,749,547 | $154,028 | 2.8%/mes |
| Banco Estado | Crédito + TC | $5,600,000 | $174,437 | 3.1%/mes |
| Banco Santander | TC | $3,760,935 | $109,000 | 2.8%/mes |
| CMR Falabella | TC retail | $1,607,443 | $80,000 | 3.3%/mes |
| Líneas crédito | 3 bancos | $2,360,000 | $71,660 | 3.1%/mes |
| Crédito Foton | Automotriz | $9,517,195 | $264,366 | 1.2%/mes |
| Seguro Foton | Fijo | $0 | $65,412 | — |
| Hermana | Familiar | $1,050,000 | $0 | 0% |
| **TOTAL** | | **$29,644,120** | **$918,903** | |

> ⚠️ La hoja registra deuda total ~$18.6M en instrumentos financieros + $9.5M en crédito automotriz. El Foton es un activo real que respalda parcialmente esa deuda.

### Métricas clave:
- **Punto de equilibrio (escenario realista 50% margen):** ~$3,950,000/mes
- **Ventas promedio actual:** $1,859,000/mes → **47% del PE**
- **Margen bruto producto estrella (Estantería 5E):** 55.2%
- **Margen bruto estimado mix real:** 42–50%
- **Déficit mensual neto estimado:** ~$458,000–$616,000/mes (incluye cuotas bancarias)

---

## 4. DIAGNÓSTICO — 5 CAUSAS DEL DÉFICIT

1. **Deuda aplastante ($18.6M)** — cuotas de $929K/mes = 50% del ingreso promedio
2. **Alquiler del taller ($700K/mes)** — 38% del ingreso bruto (lo normal: 10-15%)
3. **Ventas insuficientes** — se vende $1.86M pero se necesita $3.95M para cubrir todo
4. **Mezcla gastos personales** — ~$80K/mes de gastos de "Chiquito" salen de la caja del negocio
5. **TCs en mora** — registro dic-2025 de cuota morosa Banco Estado; genera tasa TMC (~2.75%/mes)

---

## 5. ENTREGABLES GENERADOS

### Sesión 1 — Diagnóstico base:
| Archivo | Descripción |
|---------|-------------|
| `Diagnostico_Financiero_Chiquito.xlsx` | Excel con 6 hojas: Dashboard, P&G (5 meses), Deuda, Punto Equilibrio, Plan de Acción, Seguir o Cerrar |
| App interactiva (artefacto Claude.ai) | React embebido con 4 tabs: Dashboard, Simulador, Deuda, Plan |

### Sesión 2 — App standalone + análisis inyección:
| Archivo | Descripción |
|---------|-------------|
| `ChiquitoFinanzas.html` | Aplicación HTML/JS completa, offline, con sidebar + 6 módulos |
| `MEMORY.md` | Este archivo — documentación del proyecto |
| `analisis_inyeccion.md` | Análisis crédito BCI + aporte familiar (ver sección 6) |

### Pendiente (Claude Code — próximo sprint):
- [ ] App Python Streamlit con conexión a carpeta OneDrive del Excel
- [ ] Actualización automática mensual leyendo `Cajas_2026`
- [ ] Exportador de reporte PDF mensual
- [ ] Alertas cuando saldo < umbral configurado

---

## 6. ANÁLISIS DE INYECCIÓN DE CAPITAL

### Propuesta:
- **Aporte familiar (hermanos):** $2,200,000 — sin interés, sin cuota
- **Crédito consumo BCI (Sócrates):** $10,000,000 — 18 cuotas a 1.43%/mes
- **Total inyección:** $12,200,000

### Datos crédito BCI (simulación real, mar-2026):
| Parámetro | Valor |
|-----------|-------|
| Monto | $10,000,000 |
| Cuotas | 18 |
| Tasa mensual (c/seguro desgravamen) | 1.43% |
| Cuota mensual | $648,805 |
| CAE | 20.24% |
| CTC (costo total del crédito) | $11,678,482 |
| Costo real en intereses | $1,678,482 (18 meses) |
| Primera cuota | 15-Abr-2026 |

### Estrategia de aplicación (prioridad por tasa mayor):
1. ✅ Pagar CMR Falabella completo — $1,607,443 (3.3%/mes) → libera $80,000/mes
2. ✅ Pagar Líneas de crédito — $2,360,000 (3.1%/mes) → libera $71,660/mes
3. ✅ Pagar Banco Estado — $5,600,000 (3.1%/mes) → libera $174,437/mes
4. ⚡ Pago parcial Banco Santander — $2,632,557 de $3,760,935 (2.8%/mes)

### Resultado:
| Métrica | Valor |
|---------|-------|
| Deudas completamente canceladas | 3 instrumentos |
| Cuotas liberadas por mes | +$326,097 |
| Nueva cuota BCI (18 meses) | -$648,805 |
| Impacto neto en cuotas | **-$322,708/mes más** (corto plazo) |
| Intereses eliminados por mes | +$373,517 |
| Interés mensual BCI | -$93,249 |
| **Ahorro neto en intereses** | **+$280,268/mes** |
| Arbitraje de tasa | 1.70% mensual a favor (3.13% → 1.43%) |
| Ahorro total en intereses (18 meses) | ~$3,363,213 |

### ✅ PROS:
1. Arbitraje de tasa brutal: se reemplaza deuda al 3.1-3.3%/mes por deuda al 1.43%/mes
2. En 18 meses la deuda BCI queda en cero — estructura limpia
3. Elimina 3 acreedores → reduce exposición bancaria de la hermana
4. Mejora historial crediticio al cerrar TCs en mora
5. Ahorra $3.36M en intereses a lo largo del período
6. El aporte de $2.2M es gratuito — costo cero

### ❌ CONTRAS:
1. **Riesgo de Sócrates:** La deuda BCI es personal de Sócrates — si el negocio no mejora, él paga igual
2. **Flujo neto peor al inicio:** -$322K/mes más en los primeros 18 meses sobre un negocio ya deficitario
3. **Dependencia:** Si las ventas no suben, se necesita que Sócrates cubra los $649K del BCI con su ingreso
4. **No resuelve el problema raíz:** El alquiler ($700K) y las ventas bajas ($1.86M vs PE $3.95M) siguen sin resolver
5. **El Santander queda parcialmente sin pagar** — $1,128,378 remanente al 2.8%/mes

### 🎯 RECOMENDACIÓN CONDICIONAL:
**Ejecutar SOLO si se cumplen simultáneamente:**
- [ ] Se negocia el alquiler del taller de $700K a máximo $450K **antes** de inyectar
- [ ] Se acuerda un plan de devolución claro entre Sócrates y su hermana (ej: $200K/mes al BCI)
- [ ] Las ventas alcanzan mínimo $2.5M/mes antes del 4° mes post-inyección
- [ ] Se formaliza la empresa (EIRL/SpA) para separar deuda personal/negocio

**Si no se cumplen estas condiciones → usar solo el aporte de $2.2M para pagar CMR + parte de líneas.**

---

## 7. PLAN DE ACCIÓN PRIORIZADO

### Horizonte 1: URGENTE (0-3 meses)
| # | Acción | Ahorro/mes |
|---|--------|-----------|
| 1 | Renegociar alquiler taller ($700K → $400K) | $300,000 |
| 2 | Separar gastos personales del negocio | $80,000 |
| 3 | Renegociar TCs antes de mora formal | $150,000 |
| 4 | Subir precios 10-15% | $186,000 |

### Horizonte 2: IMPORTANTE (3-12 meses)
| # | Acción | Impacto |
|---|--------|---------|
| 5 | Escalar ventas a $3.5M/mes | Meta supervivencia |
| 6 | Formalizar empresa (EIRL/SpA) | Acceso SERCOTEC/FOGAPE |
| 7 | Evaluar vender camión Foton | +$329K/mes libera |

### Horizonte 3: LARGO PLAZO (12-36 meses)
| # | Acción | Impacto |
|---|--------|---------|
| 8 | Liquidar TCs (CMR primero) | Libera flujo permanente |
| 9 | Colchón de liquidez (2 meses) | $3.8M intocable |
| 10 | Vendedor/a comisionista | Multiplica ventas sin costo fijo |

---

## 8. MODELO DEL NEGOCIO

**Tipo:** Taller de fabricación de muebles a medida + estándar
**Ubicación:** Taller en Macul, Santiago RM
**Operador principal:** "Chiquito" (nombre operativo)
**Transporte:** Camión pickup Foton Mid (crédito activo)
**Canal de ventas:** MercadoLibre, Instagram, redes de referidos

### Productos y márgenes:
| Producto | Precio venta | Costo | Margen |
|----------|-------------|-------|--------|
| Estantería estándar 5E (blanca) | $30,000 | $13,448 | 55.2% |
| Estantería estándar 5E (negra) | $34,990 | $18,937 | 45.9% |
| Mueble lavaplato | $140,000 | $81,048 | 42.1% |
| Mueble lavamanos | $85,000–$90,000 | ~$50,000 | ~42% |
| Proyectos a medida | Variable | Variable | 35–45% |
| Closet A/B | $154,990 | ~$90,000 | 42% |

---

## 9. CONTEXTO MERCADO CHILENO (referencia)

- **Tasa crédito consumo bancario:** 1.43-2.8%/mes (según banco y perfil)
- **Tasa TCs retail (CMR, Falabella):** 2.5-3.3%/mes
- **Tasa mora (TMC):** ~2.75%/mes (Tasa Máxima Convencional CMF)
- **SERCOTEC microcréditos:** ~0.5-1%/mes (requiere formalización)
- **FOGAPE:** Capital de trabajo subsidiado para PYMES formalizadas
- **IPC Chile (2025 prom.):** ~4.5% anual
- **Salario mínimo Chile (2026):** ~$500,000/mes (referencia costo mano de obra)

---

## 10. PRÓXIMOS PASOS (Claude Code — sprint pendiente)

### Sprint 1: App Streamlit
```
/chiquito_financiero/
├── app/
│   ├── main.py              # Streamlit app principal
│   ├── data_loader.py       # Lee Excel de OneDrive automáticamente
│   ├── charts.py            # Gráficos Plotly
│   ├── calculators.py       # PE, simulador, ROI deuda
│   └── requirements.txt
├── MEMORY.md                ← este archivo
├── ChiquitoFinanzas.html    ← app standalone
└── Diagnostico_Financiero_Chiquito.xlsx
```

### Funcionalidades Streamlit pendientes:
- [ ] Lector automático de `Cajas_2026` desde ruta OneDrive configurable
- [ ] Generador de reporte PDF mensual (fpdf2 o weasyprint)
- [ ] Alertas cuando saldo operativo < $200,000
- [ ] Simulador de amortización de deuda con pagos extras
- [ ] Calculadora de punto de equilibrio interactiva
- [ ] Escenario de inyección BCI integrado al flujo

---

*Documento generado por Claude (Kai) en sesión de análisis financiero — Mar 2026*
*Para actualizar: adjuntar nuevo Excel en Claude.ai y ejecutar script de análisis*
