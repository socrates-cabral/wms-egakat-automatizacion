@echo off
REM ============================================================
REM Crear Tarea en Task Scheduler para Limpieza Automatica
REM Ejecutar como Administrador
REM ============================================================

echo.
echo Creando tarea en Task Scheduler...
echo.

schtasks /create ^
  /tn "ClaudeWork - Limpieza Automatica Mensual" ^
  /tr "C:\ClaudeWork\scripts\cleanup_automatico.bat" ^
  /sc monthly ^
  /d 1 ^
  /st 02:00 ^
  /ru SYSTEM ^
  /rl HIGHEST ^
  /f

if %errorlevel% equ 0 (
    echo.
    echo ========================================
    echo  TAREA CREADA EXITOSAMENTE
    echo ========================================
    echo.
    echo Nombre: ClaudeWork - Limpieza Automatica Mensual
    echo Frecuencia: Primer dia de cada mes a las 02:00 AM
    echo Script: C:\ClaudeWork\scripts\cleanup_automatico.bat
    echo.
    echo Para verificar: Abrir Task Scheduler y buscar la tarea
    echo.
) else (
    echo.
    echo ========================================
    echo  ERROR AL CREAR TAREA
    echo ========================================
    echo.
    echo Posible causa: No se ejecuto como Administrador
    echo Solucion: Click derecho en este archivo ^> Ejecutar como administrador
    echo.
)

pause
