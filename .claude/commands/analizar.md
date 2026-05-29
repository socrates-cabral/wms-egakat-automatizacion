# /analizar — Invocar agentes Python de análisis desde conversación

Kai delega al agente-logistica que ejecuta el agente Python correcto.

## Uso

```
/analizar stock "archivo.xlsx"
/analizar nps "encuesta.xlsx"
/analizar staging "movimientos.csv"
/analizar dax "total unidades bloqueadas por cliente"
/analizar query "limpiar y normalizar columnas del stock WMS"
/analizar finanzas "pregunta sobre P&L o portfolio"
/analizar extraer "Stock WMS"       # busca en OneDrive
```

## Ejemplos reales

```
/analizar stock "OneDrive/Stock_WMS_2026-05-28.xlsx"
/analizar nps "OneDrive/Encuesta_Mayo2026.xlsx"
/analizar dax "% de pedidos completados a tiempo por cliente"
/analizar query "unir tabla de despachos con maestro de clientes por código empresa"
/analizar finanzas "¿cómo está la posición de caja de Egakat este mes?"
```

## Lo que hace Kai

1. Identifica el tipo de análisis pedido
2. Busca el archivo si no se especifica ruta completa (Glob en OneDrive + ClaudeWork)
3. Lanza `agente-logistica` con el comando correcto
4. Recibe output y lo presenta en conversación
5. Si hay error → diagnostica y sugiere solución

## Agentes disponibles internamente

| Comando | Agente Python | Descripción |
|---------|--------------|-------------|
| stock | analista.py stock | KPIs inventario WMS |
| nps | analista.py nps | Score NPS/CSAT + distribución |
| staging | analista.py staging | Flujo pallets IN/OUT |
| comparar | analista.py comparar | Diff entre dos archivos |
| dax | power_bi.py dax | Genera medida DAX |
| query | power_bi.py query | Genera Power Query M |
| kpis | power_bi.py kpis | KPIs sugeridos para el área |
| finanzas | finanzas.py consulta | Análisis financiero libre |
| extraer | extractor.py analizar | Lee Excel/PDF + análisis Claude |
