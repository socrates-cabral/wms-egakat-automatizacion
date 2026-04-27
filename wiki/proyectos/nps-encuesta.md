---
title: NPS_Encuesta — CSAT y NPS desde LimeSurvey
type: proyecto
sources: [NPS_Encuesta/nps_descarga.py]
related: [proyecto-wms-egakat, graph-api-microsoft]
updated: 2026-04-12
confidence: high
---

# NPS_Encuesta — Módulo 5

## Rol
Descarga respuestas de encuestas CSAT y NPS desde LimeSurvey vía RemoteControl 2 API, genera un Excel consolidado para Power BI y lo sube a SharePoint via Graph API.

- **Script:** `NPS_Encuesta/nps_descarga.py` v3.0
- **Destino SharePoint:** `NPS_EK/Reportes NPS/NPS_PBI_datos.xlsx`
- **Local temporal:** `NPS_Encuesta/NPS_PBI_datos.xlsx`
- **Logs:** `C:\ClaudeWork\logs\nps_run_YYYYMMDD_HHMMSS.log`

## Encuestas configuradas

| ID | Tipo | Tokens |
|----|------|--------|
| 386641 | CSAT (mensual) | `tokens_csat.csv` |
| 418429 | NPS (trimestral) | `tokens_nps.csv` |

## Preguntas CSAT mapeadas
| Código LimeSurvey | Col Excel | Descripción |
|-------------------|-----------|-------------|
| G01Q01 | 1 | Satisfacción general del servicio |
| G01Q05 | 5 | Cumplimiento de tiempos de entrega |
| G01Q06 | 6 | Precisión de pedidos preparados |
| G01Q07 | 7 | Información y seguimiento de pedidos |

**Áreas evaluadas:** Recepción, Preparación de pedidos, Despacho, Gestión de inventarios, Transporte, Calidad, Servicio al cliente.

## Flujo
1. Login LimeSurvey RCAPI → `get_session_key()`
2. Descarga respuestas CSV codificado en base64 → `export_responses()`
3. Parsea respuestas → mapea preguntas → cruza con `Contactos_Clientes.xlsx`
4. Genera `NPS_PBI_datos.xlsx` con formato PowerBI (estilos, columnas calculadas)
5. Sube a SharePoint via Graph API (`subir_archivo_sp`)
6. Cierra sesión LimeSurvey → `release_session_key()`

## Dependencia de Graph API
Importa `get_token`, `get_drive_id` desde `WMS_Automatizacion/azure_graph.py`. No tiene su propia implementación Graph.

## Tareas programadas (3)
| Archivo XML | Tipo | Trigger |
|-------------|------|---------|
| `tarea_nps_primera.xml` | Primera corrida | Manual / inicio ronda |
| `tarea_nps_csat_mensual.xml` | CSAT | Mensual |
| `tarea_nps_trimestral.xml` | NPS completo | Trimestral |

## Variables de entorno requeridas
```
LIMESURVEY_URL
LIMESURVEY_USER / LIMESURVEY_PASSWORD
LIMESURVEY_SURVEY_ID_CSAT   (386641)
LIMESURVEY_SURVEY_ID_NPS    (418429)
TENANT_ID / CLIENT_ID / CLIENT_SECRET  (Graph API)
SHAREPOINT_USER
```

## Archivos de referencia
- `Contactos_Clientes.xlsx` — mapeo token → empresa cliente
- `tokens_csat.csv` / `tokens_nps.csv` — tokens de acceso por ronda (actualizar manualmente cada ronda)
- `Propuesta Configuracion Encuestas NPS_CSAT.docx` — documento de diseño original
