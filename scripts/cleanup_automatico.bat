@echo off
REM ============================================================
REM Script de Limpieza Automatica - C:\ClaudeWork
REM Autor: Sistema Automatizado Egakat
REM Uso: Ejecutar manualmente o programar en Task Scheduler
REM ============================================================

echo.
echo ========================================
echo  LIMPIEZA AUTOMATICA C:\ClaudeWork
echo  Fecha: %date% %time%
echo ========================================
echo.

REM === 1. Crear backup del log de limpieza ===
set LOGDIR=C:\ClaudeWork\logs\cleanup
if not exist "%LOGDIR%" mkdir "%LOGDIR%"
set LOGFILE=%LOGDIR%\cleanup_%date:~-4%%date:~-7,2%%date:~-10,2%_%time:~0,2%%time:~3,2%%time:~6,2%.log
set LOGFILE=%LOGFILE: =0%

echo Iniciando limpieza automatica... > "%LOGFILE%"
echo Fecha: %date% %time% >> "%LOGFILE%"
echo. >> "%LOGFILE%"

REM === 2. Eliminar archivos __pycache__ y .pyc ===
echo [1/5] Eliminando cache Python...
echo [1/5] Eliminando cache Python... >> "%LOGFILE%"

for /d /r C:\ClaudeWork %%d in (__pycache__) do (
    if exist "%%d" (
        rd /s /q "%%d" 2>nul
        if not errorlevel 1 echo   - Eliminado: %%d >> "%LOGFILE%"
    )
)

del /s /q C:\ClaudeWork\*.pyc 2>nul
echo   OK - Cache Python eliminado >> "%LOGFILE%"
echo   OK

REM === 3. Eliminar logs antiguos (>30 dias) ===
echo [2/5] Eliminando logs antiguos ^(^>30 dias^)...
echo [2/5] Eliminando logs antiguos (>30 dias)... >> "%LOGFILE%"

REM Logs generales
forfiles /p "C:\ClaudeWork\logs" /s /m *.log /d -30 /c "cmd /c del @path" 2>nul
if not errorlevel 1 echo   - Logs generales antiguos eliminados >> "%LOGFILE%"

REM Logs Productividad
forfiles /p "C:\ClaudeWork\Productividad_Automatizacion\logs" /m *.log /d -30 /c "cmd /c del @path" 2>nul
forfiles /p "C:\ClaudeWork\Productividad_Automatizacion\logs" /m *.html /d -30 /c "cmd /c del @path" 2>nul
if not errorlevel 1 echo   - Logs Productividad antiguos eliminados >> "%LOGFILE%"

REM Logs FillRate
forfiles /p "C:\ClaudeWork\FillRate_Automatizacion\logs" /m *.log /d -30 /c "cmd /c del @path" 2>nul
if not errorlevel 1 echo   - Logs FillRate antiguos eliminados >> "%LOGFILE%"

REM Logs WMS
forfiles /p "C:\ClaudeWork\WMS_Automatizacion\logs" /m *.log /d -30 /c "cmd /c del @path" 2>nul
if not errorlevel 1 echo   - Logs WMS antiguos eliminados >> "%LOGFILE%"

REM Logs Softnet
forfiles /p "C:\ClaudeWork\Softnet_Ventas\logs" /m *.log /d -30 /c "cmd /c del @path" 2>nul
if not errorlevel 1 echo   - Logs Softnet antiguos eliminados >> "%LOGFILE%"

echo   OK - Logs antiguos eliminados >> "%LOGFILE%"
echo   OK

REM === 4. Limpiar outputs antiguos agente_apuestas (>15 dias) ===
echo [3/5] Limpiando outputs agente_apuestas antiguos...
echo [3/5] Limpiando outputs agente_apuestas antiguos... >> "%LOGFILE%"

forfiles /p "C:\ClaudeWork\agente_apuestas\output" /m *.html /d -15 /c "cmd /c del @path" 2>nul
if not errorlevel 1 echo   - Outputs antiguos eliminados >> "%LOGFILE%"

echo   OK >> "%LOGFILE%"
echo   OK

REM === 5. Limpiar archivos temporales con patrones conocidos ===
echo [4/5] Eliminando archivos temporales...
echo [4/5] Eliminando archivos temporales... >> "%LOGFILE%"

REM Archivos con path corrupto (C:ClaudeWork*)
del /s /q "C:\ClaudeWork\C:ClaudeWork*" 2>nul
if not errorlevel 1 echo   - Archivos path corrupto eliminados >> "%LOGFILE%"

REM Archivos chunk temporales
del /s /q "C:\ClaudeWork\*_chunk_*.xlsx" 2>nul
del /s /q "C:\ClaudeWork\*_chunk_*.xls" 2>nul
if not errorlevel 1 echo   - Archivos chunk eliminados >> "%LOGFILE%"

REM Archivos .tmp
del /s /q "C:\ClaudeWork\*.tmp" 2>nul
if not errorlevel 1 echo   - Archivos .tmp eliminados >> "%LOGFILE%"

echo   OK >> "%LOGFILE%"
echo   OK

REM === 6. Reportar espacio liberado ===
echo [5/5] Generando reporte final...
echo [5/5] Generando reporte final... >> "%LOGFILE%"
echo. >> "%LOGFILE%"
echo ======================================== >> "%LOGFILE%"
echo  LIMPIEZA COMPLETADA >> "%LOGFILE%"
echo  Log guardado en: >> "%LOGFILE%"
echo  %LOGFILE% >> "%LOGFILE%"
echo ======================================== >> "%LOGFILE%"

echo.
echo ========================================
echo  LIMPIEZA COMPLETADA
echo  Log: %LOGFILE%
echo ========================================
echo.

REM === 7. Opcional: Mostrar estadisticas de disco ===
echo Espacio en disco C:
wmic logicaldisk where "DeviceID='C:'" get FreeSpace,Size /format:list

pause
