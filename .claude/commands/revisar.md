# /revisar — Lanzar el Revisor especializado del proyecto

Invoca el subagente Revisor con el checklist histórico de bugs de este proyecto.
Más preciso que /code-review para el stack Python/Streamlit/Supabase/WMS de Egakat.

## Uso

```
/revisar                    # revisa el git diff actual
/revisar <archivo o carpeta> # revisa archivos específicos
```

## Lo que Kai hace al invocar

1. Obtiene la lista de archivos modificados (`git diff --name-only` o los indicados)
2. Lanza el Revisor con esa lista y el contexto del proyecto
3. Recibe el reporte con severidades
4. Si hay 🔴 CRÍTICOS → fix antes de commitear
5. Si solo hay 🟠/🟡 → decide con el usuario si corregir o no

## Plantilla de invocación desde Kai

```python
Agent(
    subagent_type="revisor",
    description="Revisar cambios antes de commit",
    prompt="""
Revisar los siguientes archivos modificados en este sprint:

Archivos:
- <ruta1>
- <ruta2>

Contexto de los cambios:
<descripción de qué implementó el Implementador o qué cambió Kai>

Aplicar el checklist completo del proyecto. Formato de output obligatorio con severidades.
"""
)
```

## Flujo completo del equipo

```
Kai analiza tarea
      ↓
/implementar → Implementador ejecuta en worktree aislado
      ↓
/revisar → Revisor aplica checklist histórico
      ↓
🔴 críticos? → Kai o Implementador corrigen
      ↓
APROBADO → Kai commitea y pushea a idx main
```

## Diferencia con /code-review

| | /code-review | /revisar |
|--|--|--|
| Scope | Genérico, cualquier proyecto | Específico: patrones WMS, Streamlit, Supabase, crypto bot |
| Bugs conocidos | Template estándar | Historial real: 30 bugs HM, 57 finanzas, FillRate identity compuesta |
| Formato | Libre | Estructurado con severidad y veredicto obligatorio |
| Velocidad | Más lento (más general) | Más rápido (checklist acotado) |

Usar `/code-review ultra` para revisiones profundas pre-release. Usar `/revisar` en el ciclo diario.
