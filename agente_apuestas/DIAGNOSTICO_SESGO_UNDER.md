# Diagnóstico: Sesgo Under en Agente Apuestas
**Fecha:** 2026-04-29  
**Estado actual:** ROI -68.3%, Accuracy 16.7% (1/6), 5/6 apuestas Under

---

## 1. HALLAZGOS CRÍTICOS

### Distribución de Apuestas Reales (n=6)
| Tipo | Cantidad | Ganadas | Accuracy | ROI |
|------|----------|---------|----------|-----|
| Under | 5 | 1 | 20% | -78% aprox |
| Over | 1 | 0 | 0% | -100% |

**⚠️ PROBLEMA PRINCIPAL:** 83% de apuestas fueron Under (5/6)

### Análisis por Apuesta

| # | Partido | Tipo | Prob Modelo | Lambda | Score | Resultado | Flags |
|---|---------|------|-------------|--------|-------|-----------|-------|
| 1 | MLB Twins-Tigers | Over 6.5 | 78.4% | ? | 4-2 (6 runs) | ❌ | - |
| 2 | Premier Palace-Newcastle | Under 2.5 | **92.0%** | ? | 2-1 (3 goles) | ❌ | 🐛 lambda_sospechoso |
| 3 | Premier Forest-Villa | Under 2.5 | **92.0%** | ? | 1-1 (2 goles) | ✅ | 🐛 lambda_sospechoso |
| 4 | NBA Celtics-Magic | Under 215.5 | 50.0% | ? | 113-108 (221) | ❌ | - |
| 5 | UCL Bayern-Madrid | Under 4.5 | **89.1%** | ? | 4-3 (7 goles) | ❌ | - |
| 6 | Serie A Inter-Cagliari | Under 2.25 | 54.4% | ? | 3-0 (3 goles) | ❌ | - |

---

## 2. CÓDIGO ACTUAL - PROTECCIONES EXISTENTES

### value_detector.py:612 — Cap de Calibración
```python
prob_modelo = min(0.75, prob_fn())   # cap calibración: Poisson sobreestima confianza
```
✅ **Existe** un cap del 75%, pero apuestas #2, #3 y #5 tienen prob >75%

**Conclusión:** El cap de 75% NO se está aplicando correctamente, o se está bypasseando en algún flujo.

### value_detector.py:617-620 — Detección Lambda Sospechoso
```python
lambda_sospechoso = (
    (deporte == "futbol" and lam < 1.5) or
    (deporte != "futbol" and abs(ratio_linea - 1.0) > 0.30)
)
```

### value_detector.py:635 — Filtro Tiene Value
```python
tiene_value = (value >= VALUE_THRESHOLD and 
               not lambda_sospechoso and 
               not under_irreal and 
               not under_knockout)
```

✅ **Existen** protecciones, pero las apuestas #2 y #3 pasaron el filtro y fueron marcadas retroactivamente.

---

## 3. LAMBDA FLOOR BUG DETECTADO

### value_detector.py:501-504
```python
# Si el lambda calculado es irreal (datos vacíos/cero de API), usar prior neutro
# — NO usar lam_min (1.0) porque eso daría P(Under 2.5) ≈ 92% sin fundamento real
lam_min = LAMBDA_MINIMO.get(deporte, 0.0)
if lam_calculado < lam_min:
    return LAMBDA_DEFAULT.get(deporte, lam_min)  # ← PROBLEMA AQUÍ
```

**LAMBDA_MINIMO:**
- futbol: 1.0
- baseball: 6.0
- basketball: 180.0

**LAMBDA_DEFAULT:**
- futbol: 2.5
- baseball: 8.5
- basketball: 220.0

### Escenarios problemáticos:

**Caso 1: Deporte no reconocido**
```python
LAMBDA_DEFAULT.get("football", lam_min)  # typo: "football" vs "futbol"
# Devuelve lam_min = 1.0 en lugar de 2.5
# → P(Under 2.5) con lambda=1.0 ≈ 92%
```

**Caso 2: Datos API vacíos**
- Si api-sports no devuelve goles_esperados
- Y FootyStats no tiene xG
- Lambda se calcula bajo → se aplica el floor
- Dependiendo del flujo, podría usarse 1.0 en lugar de 2.5

---

## 4. SOBRECONFIANZA DEL MODELO

### Probabilidades observadas vs accuracy real

| Prob Modelo | Apuestas | Ganadas | Accuracy Real | Brecha |
|-------------|----------|---------|---------------|--------|
| 90-92% | 2 | 1 | 50% | **-42%** |
| 75-90% | 2 | 0 | 0% | **-82%** |
| 50-60% | 2 | 0 | 0% | **-55%** |

**Conclusión:** El modelo está **sistemáticamente sobreconfiado**. Probabilidades 78-92% tienen accuracy real 0-50%.

---

## 5. CAUSAS RAÍZ IDENTIFICADAS

### A. Lambda Floor Bug (value_detector.py:504)
- Fallback incorrecto cuando deporte no coincide exactamente
- Posible typo "football" vs "futbol" en fixtures_collector
- Devuelve lambda=1.0 → P(Under 2.5) = 92% sin fundamento

### B. Cap 75% No Aplicado Consistentemente
- Código tiene `min(0.75, prob_fn())` pero apuestas reales >75%
- Posible bypass en flujo XGBoost o ensemble

### C. Sin Calibración Platt Scaling
- XGBoost devuelve probabilidades raw sin calibrar
- Poisson sobreestima certeza en rangos extremos
- No hay ajuste post-predicción

### D. Sesgo de Selección — Favorece Under
- confidence_scorer.py:42 menciona "bias de lambda"
- Penalización de diversidad existe pero no suficiente
- 83% Under indica filtro inefectivo

---

## 6. RECOMENDACIONES INMEDIATAS

### 🔴 CRÍTICO — Pausar Apuestas Reales
- Mantener paper trading hasta n≥50 con ROI>0

### 🟠 ALTA PRIORIDAD

1. **Fix Lambda Floor (Tarea #2)**
   ```python
   # value_detector.py:504
   # ANTES:
   return LAMBDA_DEFAULT.get(deporte, lam_min)
   
   # DESPUÉS:
   default = LAMBDA_DEFAULT.get(deporte, 2.5)  # prior neutro siempre
   return max(default, lam_min)  # nunca menor al default
   ```

2. **Verificar Cap 75% (Tarea #2)**
   - Agregar logging de prob_modelo DESPUÉS del cap
   - Verificar que XGBoost predictions también pasen por cap
   - Confirmar que ensemble no byppassea el límite

3. **Implementar Platt Scaling (Tarea #3)**
   ```python
   from sklearn.calibration import CalibratedClassifierCV
   # Calibrar XGBoost con set de validación
   # Reducir prob 90% → 60-70% realista
   ```

4. **Ajustar Umbrales (Tarea #4)**
   - Subir umbral_confianza: 0.60-0.70 → **0.75**
   - Endurecer lambda_sospechoso: `lam < 1.5` → `lam < 2.0`
   - Penalización diversidad más agresiva si Under >60% últimas 10

5. **Validación Cruzada (Tarea #5)**
   - Backtesting con nuevos parámetros
   - Verificar distribución 1X2 vs Over/Under
   - Target: max 40% de un solo tipo en últimas 20 apuestas

---

## 7. PRÓXIMOS PASOS

1. ✅ Diagnóstico completado
2. ⏳ Verificar y corregir bug lambda floor
3. ⏳ Implementar Platt Scaling
4. ⏳ Ajustar umbrales y diversidad
5. ⏳ Backtesting + validación
6. ⏳ Documentar en wiki

**ETA Fix Completo:** ~4-6 horas de desarrollo + testing
