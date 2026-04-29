---
title: Agente Apuestas — Fixes Críticos Sesgo Under
type: proyecto
sources: [agente_apuestas/DIAGNOSTICO_SESGO_UNDER.md, agente_apuestas/FIXES_APLICADOS_2026-04-29.md]
related: [wiki/proyectos/agente-apuestas.md]
updated: 2026-04-29
confidence: high
---

# Fixes Críticos — Sesgo Under + Sobreconfianza

## Contexto

**Performance pre-fix (n=6):**
- ❌ ROI: -68.3%
- ❌ Accuracy: 16.7% (1/6)
- ❌ Sesgo Under: 83% (5/6 apuestas)
- ❌ Sobreconfianza: prob 78-92% con accuracy real 0-50%

**Commit:** `9992338` (2026-04-29)

---

## Bug Principal: Lambda Floor

**Archivo:** `value_detector.py:504`

**Problema:**
```python
# Código buggy:
if lam_calculado < lam_min:
    return LAMBDA_DEFAULT.get(deporte, lam_min)  # ← BUG
```

Si `deporte` no coincide exactamente (ej: "football" vs "futbol"), devolvía `lam_min=1.0` en lugar de `LAMBDA_DEFAULT=2.5`.

Con lambda=1.0 y línea 2.5:
- P(Under 2.5) ≈ 92%
- Sin fundamento estadístico real

**Fix:**
```python
if lam_calculado < lam_min:
    default = LAMBDA_DEFAULT.get(deporte, 2.5)
    return default  # SIEMPRE prior neutro
```

---

## 5 Fixes Aplicados

### 1. Lambda Floor Bug
- **Dónde:** value_detector.py:504
- **Cambio:** Siempre devolver LAMBDA_DEFAULT, nunca lam_min
- **Impacto:** Elimina Under con prob inflada 92%

### 2. Lambda Sospechoso Endurecido
- **Dónde:** value_detector.py:620
- **Cambio:** lam < 1.5 → lam < 2.0 (fútbol)
- **Impacto:** Rechaza más apuestas con datos API insuficientes

### 3. MIN_CONFIDENCE Subido
- **Dónde:** config.py:87
- **Cambio:** 55 → 65 puntos
- **Impacto:** Solo apuestas con señal fuerte (score ≥65/100)

### 4. Umbrales por Liga
- **Dónde:** modelos/ligas_activas.json
- **Cambio:** Todos los umbrales → 0.75
- **Impacto:** Más conservador, menos volumen

### 5. Penalización Diversidad
- **Dónde:** confidence_scorer.py:50
- **Cambio:** Umbrales 80%→70%, 60%→50%; penalizaciones -20→-30, -10→-15
- **Impacto:** Fuerza balance 1X2 vs Over/Under (target <60% de un tipo)

---

## Protecciones Ya Existentes

✅ **Cap 75% probabilidades** (commit b95c368, 24 abril)
- value_detector.py:614: `prob_modelo = min(0.75, prob_fn())`

✅ **Platt Scaling** (Sprint 18)
- entrenador.py:325: `CalibratedClassifierCV(method="sigmoid")`

✅ **Under knockout bloqueado** (24 abril)
- value_detector.py:623: Rechaza Under en rondas eliminatorias

---

## Próximos Pasos

### 1. Re-entrenar Modelo
```bash
py agente_apuestas/entrenamiento/run_entrenamiento.py
```
**Por qué:** Features calculadas con lambda floor bug necesitan recálculo.

### 2. Backtesting
```bash
py agente_apuestas/backtesting/run_backtesting.py --n-partidos=100
```
**Validar:**
- Distribución <60% de un tipo
- Accuracy real ~50-55% si prob_modelo ~70%
- ROI >0% en n≥50

### 3. Paper Trading
- Continuar hasta n≥50 con ROI>0
- Monitorear cada 10 apuestas
- NO capital real hasta validación

---

## Métricas Esperadas Post-Fix

| Métrica | Pre-Fix | Target Post-Fix |
|---------|---------|-----------------|
| ROI | -68.3% | >0% (n≥50) |
| Accuracy | 16.7% | 50-60% |
| Sesgo Under | 83% | <60% |
| Prob >75% | 4/6 (66%) | 0% (bloqueado) |
| n apuestas/semana | ~1-2 | ~3-5 (umbrales más altos) |

---

## Alertas de Monitoreo

1. **Prob >75% en producción** → investigar (debería estar capped)
2. **>60% mismo tipo** en ventana 20 → revisar diversidad
3. **Accuracy <40%** en n≥20 → re-calibrar modelo
4. **Lambda <2.0** en apuesta generada → verificar datos API

---

## Archivos Modificados

1. value_detector.py — lambda floor + lambda sospechoso
2. config.py — MIN_CONFIDENCE 55→65
3. ligas_activas.json — umbrales todos 0.75
4. confidence_scorer.py — penalizaciones diversidad
5. DIAGNOSTICO_SESGO_UNDER.md — análisis completo
6. FIXES_APLICADOS_2026-04-29.md — resumen técnico

---

## Lecciones Aprendidas

1. **JSON round-trip puede causar bugs sutiles** (typo "football" vs "futbol")
2. **Caps de probabilidad deben aplicarse EN TODAS LAS RUTAS** de código
3. **Backtesting histórico ≠ performance real** con datos API en vivo
4. **n=6 es muestra insuficiente** — necesita n≥50 para conclusiones
5. **Platt Scaling existe pero modelo necesita re-entrenamiento** tras fix de features

---

## Referencias

- Diagnóstico: agente_apuestas/DIAGNOSTICO_SESGO_UNDER.md
- Fixes técnicos: agente_apuestas/FIXES_APLICADOS_2026-04-29.md
- Commit: 9992338
- Wiki proyecto: [[proyectos/agente-apuestas]]
- Memory: project_agente_apuestas.md (actualizar)
