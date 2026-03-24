@echo off
chcp 65001 >nul
echo.
echo ============================================================
echo  AGENTE APUESTAS — Tarea Resumen 22:00
echo  (requiere ejecutar como Administrador)
echo ============================================================
echo.

:: Eliminar tarea anterior si existe
schtasks /delete /tn "\ClaudeWork\Agente Apuestas - Resumen Diario" /f >nul 2>&1

:: Pedir contraseña (no queda guardada en ningún archivo)
set /p WINPASS=Ingresa tu contraseña de Windows:

:: Crear la tarea
schtasks /create ^
  /tn "\ClaudeWork\Agente Apuestas - Resumen Diario" ^
  /tr "\"C:\Users\Socrates Cabral\AppData\Local\Microsoft\WindowsApps\py.exe\" \"C:\ClaudeWork\agente_apuestas\backtesting\run_backtesting.py\"" ^
  /sc DAILY ^
  /st 22:00 ^
  /ru "%USERNAME%" ^
  /rp "%WINPASS%" ^
  /rl HIGHEST ^
  /f ^
  /sd 01/01/2025

:: Limpiar variable de memoria
set WINPASS=

if %ERRORLEVEL% EQU 0 (
    echo.
    echo [OK] Tarea creada correctamente.
    echo.
    echo Nombre:   \ClaudeWork\Agente Apuestas - Resumen Diario
    echo Horario:  Todos los dias a las 22:00
    echo Script:   C:\ClaudeWork\agente_apuestas\backtesting\run_backtesting.py
    echo.
    echo Verificando tarea...
    schtasks /query /tn "\ClaudeWork\Agente Apuestas - Resumen Diario" /fo LIST
) else (
    echo.
    echo [FALLO] No se pudo crear la tarea.
    echo Asegurate de ejecutar este .bat como Administrador.
)

echo.
pause
