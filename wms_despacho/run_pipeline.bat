@echo off
REM ============================================================
REM  WMS Egakat — Pipeline completo de despacho diario
REM  1) despacho.py         → RF: despacha PLTs por contenedor
REM  2) confirmar_salida.py → WEB: confirma salida de viajes
REM ============================================================

cd /d C:\ClaudeWork\wms_despacho

SET PYTHON="C:\Users\Socrates Cabral\AppData\Local\Python\pythoncore-3.14-64\python.exe"
SET LOG=logs\pipeline_%date:~-4,4%-%date:~-7,2%-%date:~0,2%.log

echo. >> %LOG%
echo ============================================================ >> %LOG%
echo  INICIO PIPELINE: %date% %time% >> %LOG%
echo ============================================================ >> %LOG%

REM ── PASO 1: Despacho RF ─────────────────────────────────────
echo [1/2] Ejecutando despacho.py (RF)... >> %LOG%
%PYTHON% despacho.py >> %LOG% 2>&1

IF %ERRORLEVEL% NEQ 0 (
    echo [ERROR] despacho.py fallo con codigo %ERRORLEVEL% >> %LOG%
    goto :fin
)
echo [1/2] despacho.py completado OK >> %LOG%

REM Pausa para que el WMS procese los despachos
timeout /t 10 /nobreak > nul

REM ── PASO 2: Confirmar Salida WEB ────────────────────────────
echo [2/2] Ejecutando confirmar_salida.py (WEB)... >> %LOG%
%PYTHON% confirmar_salida.py >> %LOG% 2>&1

IF %ERRORLEVEL% NEQ 0 (
    echo [ERROR] confirmar_salida.py fallo con codigo %ERRORLEVEL% >> %LOG%
    goto :fin
)
echo [2/2] confirmar_salida.py completado OK >> %LOG%

:fin
echo ============================================================ >> %LOG%
echo  FIN PIPELINE: %date% %time% >> %LOG%
echo ============================================================ >> %LOG%
