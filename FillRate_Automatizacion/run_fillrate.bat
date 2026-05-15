@echo off
setlocal

cd /d C:\ClaudeWork\FillRate_Automatizacion

if not exist logs mkdir logs

REM Ruta absoluta a python.exe -- evita el App Execution Alias de Microsoft Store
REM ("py" en WindowsApps\ no resuelve bajo Task Scheduler --> "Acceso denegado.").
set "PYTHON=C:\Users\Socrates Cabral\AppData\Local\Python\pythoncore-3.14-64\python.exe"

"%PYTHON%" fillrate_descarga.py >> logs\fillrate_%date:~-4,4%-%date:~3,2%-%date:~0,2%.log 2>&1
REM Backup manual si alguna vez necesitas forzar usuario sin depender de .env:
REM "%PYTHON%" fillrate_descarga.py --wms-user SCABRAL >> logs\fillrate_%date:~-4,4%-%date:~3,2%-%date:~0,2%.log 2>&1

REM Recalcula la columna Canal de data Derco (AP_R/AP_E/CES) desde MovDerco -- requiere data Derco ya descargado
"%PYTHON%" ..\WMS_Automatizacion\canal_derco_auto.py >> logs\fillrate_%date:~-4,4%-%date:~3,2%-%date:~0,2%.log 2>&1

"%PYTHON%" ..\WMS_Automatizacion\generar_resumen_kpi_ops.py >> logs\fillrate_%date:~-4,4%-%date:~3,2%-%date:~0,2%.log 2>&1
