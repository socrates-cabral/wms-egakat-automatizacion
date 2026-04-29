# Fixes Aplicados — Agente Apuestas
**Fecha:** 2026-04-29  
**Contexto:** ROI -68.3%, Accuracy 16.7%, sesgo Under 83%

---

## CAMBIOS REALIZADOS

### 1. ✅ Lambda Floor Bug — value_detector.py:500-506
**Problema:** Cuando lambda calculado < mínimo, devolvía lam_min (1.0) en lugar de LAMBDA_DEFAULT (2.5), causando P(Under 2.5) ≈ 92% sin fundamento.

**Fix:**
```python
# ANTES:
if lam_calculado < lam_min:
    return LAMBDA_DEFAULT.get(deporte, lam_min)  # ← bug: podía devolver 1.0

# DESPUÉS:
if lam_calculado < lam_min:
    default = LAMBDA_DEFAULT.get(deporte, 2.5)
    return default  # ← SIEMPRE prior neutro, nunca lam_min
```

**Impacto:** Elimina apuestas Under con prob inflada por lambda artificialmente bajo.

---

### 2. ✅ Lambda Sospechoso Endurecido — value_detector.py:620-625
**Problema:** Umbral lam < 1.5 permitía apuestas con datos API insuficientes.

**Fix:**
```python
# ANTES:
lambda_sospechoso = (deporte == "futbol" and lam < 1.5)

# DESPUÉS:
lambda_sospechoso = (deporte == "futbol" and lam < 2.0)  # 1.5 → 2.0
```

**Impacto:** Rechaza más apuestas Over/Under cuando lambda está cerca del mínimo.

---

### 3. ✅ Confidence Threshold — config.py:87
**Problema:** MIN_CONFIDENCE=55 demasiado permisivo.

**Fix:**
```python
# ANTES:
MIN_CONFIDENCE = 55

# DESPUÉS:
MIN_CONFIDENCE = 65  # 55 → 65
```

**Impacto:** Solo apuestas con score ≥65/100 se muestran al usuario.

---

### 4. ✅ Umbrales por Liga — modelos/ligas_activas.json
**Problema:** Umbrales 0.60-0.70 permitían apuestas con prob modelo sobreconfiada.

**Fix:**
```json
// ANTES:
"umbral": 0.60  // Serie A
"umbral": 0.70  // Premier, La Liga, Bundesliga, Ligue 1

// DESPUÉS:
"umbral": 0.75  // TODAS las ligas
```

**Impacto:** Solo recomienda apuestas cuando prob_modelo × confianza ≥ 0.75.

---

### 5. ✅ Penalización Diversidad Endurecida — confidence_scorer.py:40-53
**Problema:** Penalizaciones 60%/-10 y 80%/-20 insuficientes (resultado: 83% Under).

**Fix:**
```python
# ANTES:
if pct >= 0.80: return -20
if pct >= 0.60: return -10

# DESPUÉS:
if pct >= 0.70: return -30  # 80% → 70%, -20 → -30
if pct >= 0.50: return -15  # 60% → 50%, -10 → -15
```

**Impacto:** Penaliza más agresivamente si >50% de últimas 10 apuestas son del mismo tipo.

---

## VERIFICACIONES YA EXISTENTES (No requieren cambio)

### ✅ Cap 75% Probabilidades (desde 24 abril)
- value_detector.py:614: `prob_modelo = min(0.75, prob_fn())`
- Apuestas >75% en historico son pre-24 abril

### ✅ Platt Scaling (desde Sprint 18)
- entrenamiento/entrenador.py:325: `CalibratedClassifierCV(method="sigmoid")`
- Ya implementado y funcionando

### ✅ Protecciones Under
- value_detector.py:621: `under_irreal` — rechaza Under con ratio_linea > 1.25
- value_detector.py:623: `under_knockout` — rechaza Under en rondas eliminatorias

---

## PRÓXIMOS PASOS

### 1. Re-entrenar Modelo
```bash
cd C:\ClaudeWork\agente_apuestas
py entrenamiento/run_entrenamiento.py
```

**Por qué:** Los fixes de lambda requieren re-cálculo de features. Modelo actual entrenado con lambda floor bug.

### 2. Backtesting con Nuevos Parámetros
```bash
py backtesting/run_backtesting.py --ligas=135,140 --n-partidos=100
```

**Validar:**
- Distribución 1X2 vs Over/Under (target: <60% de un tipo)
- Accuracy calibrada (target: ~50-55% real si prob_modelo ~70%)
- ROI simulado (target: >0% en n≥50)

### 3. Continuar Paper Trading
- Mantener MODO_PAPER_TRADING=True
- NO apostar capital real hasta n≥50 con ROI>0
- Monitorear métricas cada 10 apuestas

### 4. Alertas
- Si prob_modelo >75% aparece en producción → investigar (debería estar capped)
- Si >60% apuestas son Under en ventana de 20 → revisar diversidad
- Si accuracy real <40% en n≥20 → re-calibrar modelo

---

## ARCHIVOS MODIFICADOS

1. `agente_apuestas/value_detector.py`
   - Lambda floor fix (línea 500-506)
   - Lambda sospechoso endurecido (línea 620-625)

2. `agente_apuestas/config.py`
   - MIN_CONFIDENCE 55 → 65 (línea 87)

3. `agente_apuestas/modelos/ligas_activas.json`
   - Todos los umbrales → 0.75
   - Notas actualizadas

4. `agente_apuestas/confidence_scorer.py`
   - Penalización diversidad endurecida (línea 40-53)

---

## RESUMEN

| Fix | Estado | Impacto Esperado |
|-----|--------|------------------|
| Lambda floor bug | ✅ Aplicado | Elimina Under con prob inflada 92% |
| Lambda sospechoso | ✅ Endurecido | Menos apuestas con datos insuficientes |
| MIN_CONFIDENCE | ✅ 55→65 | Solo apuestas con señal fuerte |
| Umbrales ligas | ✅ Todos 0.75 | Más conservador, menos volumen |
| Diversidad | ✅ Penalizaciones +50% | Fuerza balance 1X2/Over-Under |

**ETA mejora esperada:** 
- ROI: -68% → target >0% en n≥50 post-fixes
- Accuracy: 16.7% → target 50-60% (calibrado)
- Distribución: 83% Under → target <60% de cualquier tipo
