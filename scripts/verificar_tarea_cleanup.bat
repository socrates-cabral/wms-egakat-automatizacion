@echo off
echo.
echo Verificando tarea en Task Scheduler...
echo.

schtasks /query /tn "ClaudeWork - Limpieza Automatica Mensual" /fo LIST /v

if %errorlevel% equ 0 (
    echo.
    echo ========================================
    echo  TAREA ENCONTRADA Y ACTIVA
    echo ========================================
) else (
    echo.
    echo ========================================
    echo  TAREA NO ENCONTRADA
    echo ========================================
    echo.
    echo La tarea aun no ha sido creada.
    echo Ejecutar: crear_tarea_cleanup.bat como Administrador
)

echo.
pause
