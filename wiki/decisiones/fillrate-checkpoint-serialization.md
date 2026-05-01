---
title: FillRate Checkpoint Serialization — Manejo robusto de tipos datetime
type: decision
sources: [FillRate_Automatizacion/fillrate_utils.py, FillRate_Automatizacion/fillrate_descarga.py]
related: [wiki/proyectos/fillrate.md]
updated: 2026-04-29
confidence: high
---

# Decisión: Serialización robusta de checkpoint FillRate

## Contexto

El módulo FillRate guarda un checkpoint diario en JSON para evitar reprocesar clientes en caso de interrupciones. El checkpoint incluye métricas con campos `datetime.date` que deben serializarse.

## Problema descubierto (2026-04-29)

Bug latente introducido en commit `cdfff18` (15 abril 2026):

```python
# fillrate_descarga.py:124
json.dumps(data, ensure_ascii=False, default=str)
```

El `default=str` convierte objetos `datetime.date` a strings:
```python
# En memoria (fresh processing):
{"mas_antiguo": datetime.date(2026, 4, 21)}

# Después de JSON round-trip:
{"mas_antiguo": "2026-04-21"}  # ← string, no date object
```

La función `build_summary_html()` asumía `datetime.date` y llamaba `.strftime()` directamente:

```python
# fillrate_utils.py:1205 (ANTES del fix)
mas_antiguo = p["mas_antiguo"].strftime("%d/%m/%Y")
# ↑ ERROR si mas_antiguo es string
```

## Condiciones para manifestación

El bug estuvo **latente 14 días** porque requería:

1. ✅ Ejecución interrumpida a mitad (checkpoint guarda clientes parciales)
2. ✅ Clientes con `pendientes.total > 0` en checkpoint
3. ✅ Segunda ejecución el **mismo día** (carga checkpoint con strings)
4. ✅ Generación del resumen HTML (intenta `.strftime()` en string)

Primera manifestación: 2026-04-29 13:32 (VS Code reinicio)

## Decisión tomada

**Manejo robusto de tipos en rendering**, no cambiar serialización del checkpoint.

### Por qué NO cambiar el checkpoint:

1. Checkpoints ya guardados en producción con strings
2. `default=str` es necesario para otros objetos no-JSON-serializables
3. Cambiar formato requiere migración de archivos existentes

### Solución aplicada (commit bac0c76):

```python
# fillrate_utils.py:1205-1219
ma = p.get("mas_antiguo")
if ma:
    if isinstance(ma, str):
        # Ya es string formato YYYY-MM-DD, convertir a DD/MM/YYYY
        try:
            parsed = datetime.strptime(ma, "%Y-%m-%d")
            mas_antiguo = parsed.strftime("%d/%m/%Y")
        except ValueError:
            mas_antiguo = ma  # Usar tal cual si no se puede parsear
    else:
        # Es datetime.date
        mas_antiguo = ma.strftime("%d/%m/%Y")
else:
    mas_antiguo = "—"
```

**Ventajas**:
- ✅ Compatible con checkpoints existentes (strings)
- ✅ Compatible con datos fresh (date objects)
- ✅ No requiere migración
- ✅ Resiliente a corrupciones (fallback a string crudo)

**Tradeoff**:
- Duplica lógica de parsing (pero solo 1 lugar en código)
- Runtime type checking (mínimo overhead)

## How to apply

**Al trabajar con checkpoints persistidos**:
- Asumir que los valores pueden ser strings, no objetos nativos
- Implementar detección de tipo antes de operaciones tipo-específicas
- Proveer fallbacks para casos edge (valores None, strings malformados)

**Al diseñar nuevos checkpoints**:
- Considerar usar formato ISO 8601 para fechas: `"2026-04-29T14:30:00Z"`
- Documentar contrato de tipos en docstring
- Preferir tipos simples (str, int, float, bool) sobre objetos custom

## Referencias

- Commit introducción: `cdfff18` (2026-04-15)
- Commit fix: `bac0c76` (2026-04-29)
- Incidente registrado en: `memory/project_fillrate.md`
- Checkpoint path: `FillRate_Automatizacion/logs/fillrate_checkpoint_YYYYMMDD.json`

## Lecciones aprendidas

1. **JSON round-trip no preserva tipos**: `datetime` → `str`, `Decimal` → `float`
2. **Bugs latentes en sistemas de retry**: Solo se manifiestan cuando ocurren fallos parciales
3. **Test coverage**: Necesitamos tests que simulen interrupciones + checkpoint loading
4. **Type hints son documentación**: `Optional[Dict[str, Any]]` oculta conversiones implícitas

## Mitigación futura

- [ ] Agregar test que carga checkpoint y genera HTML (detectaría este bug)
- [ ] Considerar `pydantic` para validación de checkpoint schema
- [ ] Logging de tipo de `mas_antiguo` en desarrollo para detectar early
