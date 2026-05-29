# /implementar — Delegar tarea al subagente Implementador

Kai analiza la tarea, construye el contexto completo y lanza el Implementador en worktree aislado.

## Uso

```
/implementar <descripción de la tarea>
```

## Qué hace Kai antes de delegar

1. Identifica los archivos relevantes (Glob + Grep)
2. Lee los archivos clave para entender el estado actual
3. Construye el prompt con contexto completo (rutas, líneas, qué cambiar y por qué)
4. Lanza el Implementador con `isolation="worktree"`
5. Recibe el output, revisa, y decide si commitear

## Plantilla de invocación

```python
Agent(
    subagent_type="implementador",
    isolation="worktree",
    description="<3-5 palabras del task>",
    prompt="""
Tarea: <descripción exacta de qué implementar>

Contexto:
- Archivo principal: <ruta>:<línea>
- Estado actual: <qué hace ahora>
- Estado deseado: <qué debe hacer después>
- Restricciones: <qué NO tocar>

Archivos a leer primero:
- <ruta1> — <por qué>
- <ruta2> — <por qué>

Criterio de éxito:
- <cómo saber que está bien implementado>

Syntax check requerido en: <lista de archivos .py>
"""
)
```

## Cuándo NO usar el Implementador

- Fixes de 1-2 líneas obvias → Kai lo hace directo
- Exploraciones o análisis → Kai lo hace directo
- Tareas que requieren múltiples decisiones en el camino → Kai coordina iterativamente

## Cuándo SÍ usar el Implementador

- Features nuevas con alcance claro (>50 líneas)
- Refactorizaciones acotadas con spec exacta
- Implementar algo que requiere tocar 3+ archivos
- Cuando Kai quiere proteger el worktree principal mientras experimenta
