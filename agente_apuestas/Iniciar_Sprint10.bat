@echo off
title Agente Apuestas — Sprint 10 (ML + Serie A)
cd /d "C:\ClaudeWork\agente_apuestas"

echo ============================================================
echo   AGENTE DE APUESTAS DEPORTIVAS — Sprint 10
echo   Predictor ML XGBoost activo ^| Serie A
echo   Umbral: 0.70 ^| Value min: 0.10 ^| Bankroll: $100.000 CLP
echo ============================================================
echo.

echo Ejecutando predictor tiempo real...
py run_agent.py

echo.
echo ─────────────────────────────────────────────────────────────
echo   Abriendo reporte del dia...
echo ─────────────────────────────────────────────────────────────

REM Abrir el reporte HTML mas reciente
set "U="
for /f "delims=" %%i in ('dir /b /od "output\reporte_*.html" 2^>nul') do set "U=%%i"
if defined U (
    start "" "output\%U%"
    echo   Reporte: output\%U%
) else (
    echo   [INFO] Sin reporte HTML disponible aun
)

echo.
pause
