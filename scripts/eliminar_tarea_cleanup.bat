@echo off
REM ============================================================
REM Eliminar Tarea de Task Scheduler (si quieres desactivarla)
REM Ejecutar como Administrador
REM ============================================================

echo.
echo ADVERTENCIA: Esto eliminara la tarea de limpieza automatica
echo.
set /p confirm="¿Estas seguro? (S/N): "

if /i "%confirm%" neq "S" (
    echo Operacion cancelada.
    pause
    exit /b
)

echo.
echo Eliminando tarea...
echo.

schtasks /delete /tn "ClaudeWork - Limpieza Automatica Mensual" /f

if %errorlevel% equ 0 (
    echo.
    echo ========================================
    echo  TAREA ELIMINADA EXITOSAMENTE
    echo ========================================
    echo.
    echo La limpieza automatica ha sido desactivada.
    echo Puedes volver a crearla ejecutando: crear_tarea_cleanup.bat
    echo.
) else (
    echo.
    echo ========================================
    echo  ERROR AL ELIMINAR TAREA
    echo ========================================
    echo.
    echo Posible causa: La tarea no existe o no tienes permisos de Administrador
    echo.
)

pause
