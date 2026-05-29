# /skillopt — Auto-optimizar skills con SkillOpt

Ejecuta el motor SkillOpt sobre un skill del proyecto.
Evalua el skill contra casos de prueba reales, detecta fallos y genera
versiones mejoradas iterativamente (epocas + validation gate).

## Uso

```
/skillopt revisor                   # optimiza revisor (2 epocas, lr moderate)
/skillopt revisor --epochs 3        # mas epocas = mas iteraciones
/skillopt revisor --lr conservative # cambios minimos y quirurgicos
/skillopt revisor --lr aggressive   # puede reescribir secciones completas
/skillopt revisor --eval-only       # solo mide el score, no modifica
/skillopt --list                    # muestra todos los skills con su ultimo score
```

## Que hace internamente

```
1. Lee el skill (.claude/agents/<skill>.md)
2. Backup automatico (skillopt/backups/)
3. Evalua contra casos de prueba (skillopt/cases/<skill>_cases.json)
   - Ejecuta el skill via Claude API sobre cada caso
   - Evalua output vs bugs esperados (recall, precision, formato, accionabilidad)
   - Score 0-10 por caso, promedio general
4. Si score < umbral optimo:
   - Genera prompt mejorado (Claude API con instruccion de LR)
   - Evalua el candidato contra los mismos casos
   - Si mejora >= 0.5 puntos: reemplaza el skill
   - Si no: descarta y mantiene el actual
5. Repite por N epocas
6. Guarda log en skillopt/resultados/
```

## Learning rates

| LR | Comportamiento |
|----|---------------|
| conservative | Solo retoques minimos en secciones con fallo claro |
| moderate | Puede reorganizar y agregar ejemplos (default) |
| aggressive | Puede reescribir secciones completas |

## Validation gate

Cambio se acepta solo si mejora el score en >= 0.5 puntos (sobre 10).
Si ningun candidato supera el gate, el skill queda sin cambios.

## Casos de prueba por skill

| Skill | Cases file | N casos |
|-------|-----------|---------|
| revisor | revisor_cases.json | 6 (bugs reales del historial) |
| implementador | (pendiente) | — |
| agente-logistica | (pendiente) | — |

## Agregar nuevos casos

Editar `skillopt/cases/<skill>_cases.json` y agregar entradas con:
- `code`: el codigo a revisar
- `bugs_esperados`: lista de bugs que el skill DEBE encontrar
- `veredicto_esperado`: APROBADO / APROBADO CON CONDICIONES / RECHAZADO

Cuanto mas casos reales del proyecto, mejor la optimizacion.
