---
title: VDR Comparador — SAP vs Físico Derco Parts
type: proyecto
sources: [VDR_Comparador/vdr_comparador.py]
related: [proyecto-wms-egakat, wms-technical-details]
updated: 2026-04-12
confidence: high
---

# VDR Comparador — Módulo 4

## Rol
Detecta cambios entre la versión más reciente del archivo "Base VDR" de Derco Parts y la versión anterior. Compara columnas `VDR SAP` y `VDR FISICO` por Material WMS y genera un Excel de diferencias solo si hay cambios. Power Automate detecta el archivo nuevo y envía correo con adjunto.

- **Script:** `VDR_Comparador/vdr_comparador.py` v1.0
- **Schedule:** Task Scheduler cada hora L-V 8:00–19:00
- **Origen:** `C:\Users\Socrates Cabral\Grupo Planet SpA\José Caceres - Base VDR\`
- **Destino:** `C:\...\OneDrive - EGA KAT LOGISTICA SPA\Reportes VDR\`
- **Estado local:** `VDR_Comparador/vdr_ultimo_procesado.txt`

## Flujo
1. Detecta carpeta del mes en curso (dinámica por nombre `MESES_ES`)
2. Identifica archivo nuevo vs último procesado (estado en `.txt`)
3. Si el archivo no cambió → sale sin hacer nada
4. Carga `COLUMNAS_REQUERIDAS` de ambos archivos
5. Valida equivalencia `Material WMS ↔ Material SAP` entre versiones
6. Compara `VDR SAP` y `VDR FISICO` por material → detecta diferencias
7. Si hay diferencias → genera `Reporte_VDR_DDMMYYYY_HHMMSS.xlsx` (celdas amarillas en cambios)
8. Power Automate detecta el nuevo Excel en OneDrive → envía correo automático
9. Actualiza `vdr_ultimo_procesado.txt` con el archivo procesado

## Columnas comparadas
```
Material WMS | Material SAP | Desc_Material | Categoria | VDR SAP | VDR FISICO
```
Cambios marcados en amarillo (`FFFF00`) en el Excel de salida.

## Características especiales
- **Idempotente:** si no hay archivo nuevo, no hace nada
- **Sin dependencia Graph API:** usa OneDrive local sync, no upload directo
- **Power Automate trigger:** detecta archivo nuevo en carpeta OneDrive → correo automático
- **Scale:** 91,579 registros Derco Parts (histórico de referencia)

## Variables de entorno
Ninguna — usa rutas locales hardcodeadas, no requiere credenciales.

## Archivos
| Archivo | Rol |
|---------|-----|
| `vdr_comparador.py` | Script principal |
| `vdr_ultimo_procesado.txt` | Estado: último archivo procesado |
| `tarea_vdr.xml` | Definición tarea Task Scheduler |
| `crear_tarea_vdr.ps1` | Script registro tarea |

## Nota de arquitectura
Es el único módulo del stack WMS que **no usa Graph API** — depende de OneDrive local sync + Power Automate. Correcto para su caso de uso (frecuencia horaria, sin necesidad de confirmación de subida).
