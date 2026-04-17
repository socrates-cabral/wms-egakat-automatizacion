---
title: context.on vs page.on para captura de requests en Playwright (WMS DERCO)
type: decision
sources: []
related: [proyectos/productividad.md]
updated: 2026-04-17
confidence: high
---

## Decisión
Usar `context.on("request", handler)` en lugar de `page.on("request", handler)` para capturar URLs de descarga de Excel en WMS DERCO.

## Por qué

WMS Egakat abre el archivo Excel en una **nueva pestaña** cuando el usuario hace clic en el ícono de exportación. El listener `page.on("request")` solo captura requests originados desde esa página específica — no ve requests de páginas/pestañas nuevas. El resultado era el error `"No se capturó URL del Excel tras 60s"` aunque el WMS sí generaba el archivo.

`context.on("request")` escucha **todas** las páginas del contexto (todas las pestañas), lo que permite interceptar la request de descarga aunque ocurra en una pestaña nueva.

## Cómo aplicar

```python
# MAL — no captura nuevas pestañas
page.on("request", _on_request)
# ...
page.remove_listener("request", _on_request)

# BIEN — captura todas las pestañas del contexto
context.on("request", _on_request)
# ...
context.remove_listener("request", _on_request)
```

Aplicado en `Productividad_Automatizacion/productividad_descarga.py`.

## Regla general
Cualquier WMS que abra descargas en nueva pestaña requiere el listener a nivel `context`, no `page`.
