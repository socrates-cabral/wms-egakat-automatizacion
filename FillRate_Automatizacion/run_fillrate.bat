@echo off
setlocal

cd /d C:\ClaudeWork\FillRate_Automatizacion

if not exist logs mkdir logs

py fillrate_descarga.py >> logs\fillrate_%date:~-4,4%-%date:~3,2%-%date:~0,2%.log 2>&1
REM Backup manual si alguna vez necesitas forzar usuario sin depender de .env:
REM py fillrate_descarga.py --wms-user SCABRAL >> logs\fillrate_%date:~-4,4%-%date:~3,2%-%date:~0,2%.log 2>&1

REM Recalcula la columna Canal de data Derco (AP_R/AP_E/CES) desde MovDerco -- requiere data Derco ya descargado
py ..\WMS_Automatizacion\canal_derco_auto.py >> logs\fillrate_%date:~-4,4%-%date:~3,2%-%date:~0,2%.log 2>&1

py ..\WMS_Automatizacion\generar_resumen_kpi_ops.py >> logs\fillrate_%date:~-4,4%-%date:~3,2%-%date:~0,2%.log 2>&1
