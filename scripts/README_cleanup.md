# Script de Limpieza Automática

## Descripción
`cleanup_automatico.bat` realiza limpieza periódica de archivos temporales en C:\ClaudeWork sin afectar archivos críticos o en producción.

## ¿Qué elimina?

### ✅ Siempre seguro de eliminar:
1. **Cache Python**: `__pycache__/` y `*.pyc` (se regeneran automáticamente)
2. **Logs antiguos**: `*.log` con más de 30 días en:
   - `C:\ClaudeWork\logs\`
   - `Productividad_Automatizacion\logs\`
   - `FillRate_Automatizacion\logs\`
   - `WMS_Automatizacion\logs\`
   - `Softnet_Ventas\logs\`
3. **Outputs HTML antiguos**: `agente_apuestas\output\*.html` >15 días
4. **Archivos temporales**:
   - Archivos con path corrupto (`C:ClaudeWork*`)
   - Chunks de procesamiento (`*_chunk_*.xlsx/xls`)
   - Archivos `.tmp`

### ❌ Nunca toca:
- Archivos `.env`
- Scripts de producción
- Bases de datos (`*.db`, `*.json` de estado)
- Configuraciones
- Datos actuales (<30 días)
- Carpeta `wiki/`
- Carpeta `Solicitudes_IT/`

## Uso

### Ejecución Manual
```cmd
cd C:\ClaudeWork\scripts
cleanup_automatico.bat
```

### Programar en Task Scheduler (RECOMENDADO)

1. Abrir Task Scheduler (`taskschd.msc`)
2. Crear tarea básica:
   - **Nombre**: `ClaudeWork - Limpieza Automatica`
   - **Trigger**: Mensual (primer día del mes, 02:00 AM)
   - **Action**: Ejecutar programa
     - Programa: `C:\ClaudeWork\scripts\cleanup_automatico.bat`
   - **Configuración adicional**:
     - ✅ Ejecutar tanto si el usuario inició sesión como si no
     - ✅ Ejecutar con los privilegios más altos
     - ⚠️ No activar "Detener tarea si se ejecuta más de X tiempo"

## Logs
Los logs de cada ejecución se guardan en:
```
C:\ClaudeWork\logs\cleanup\cleanup_YYYYMMDD_HHMMSS.log
```

## Estimación de Espacio Liberado
- **Por ejecución típica**: 50-200 MB
- **Primera ejecución**: Puede liberar hasta 2-3 GB (si hay backlog)

## Personalización

### Cambiar retención de logs (actualmente 30 días)
Editar línea 44:
```batch
forfiles ... /d -30 ...
```
Cambiar `-30` por `-60` para 60 días, etc.

### Cambiar retención outputs agente_apuestas (actualmente 15 días)
Editar línea 67:
```batch
forfiles ... /d -15 ...
```

### Agregar nuevas carpetas de logs
Agregar después de línea 60:
```batch
forfiles /p "C:\ClaudeWork\TU_CARPETA\logs" /m *.log /d -30 /c "cmd /c del @path" 2>nul
```

## Troubleshooting

### Error: "No se puede encontrar el archivo especificado"
- Alguna carpeta de logs no existe aún
- Es normal, el script continúa sin problemas

### Error: "Acceso denegado"
- Ejecutar como Administrador
- Verificar que ningún archivo esté en uso

### No se eliminan archivos
- Verificar que hay archivos que cumplan los criterios (>30 días)
- Revisar el log en `logs\cleanup\` para detalles

## Seguridad
✅ Este script es seguro para ejecutar regularmente  
✅ Solo elimina archivos regenerables o logs antiguos  
✅ Genera log de cada ejecución para auditoría  
⚠️ Revisar el log la primera vez para confirmar comportamiento
