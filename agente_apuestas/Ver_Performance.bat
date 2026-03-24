@echo off
title Performance del Modelo - Agente Apuestas
color 0B
echo.
echo  ============================================
echo   REPORTE DE PERFORMANCE
echo   Calculando metricas del modelo...
echo  ============================================
echo.

cd /d "C:\ClaudeWork\agente_apuestas"

py backtesting\reporte_performance.py

echo.
echo  Abriendo dashboard de performance...

for /f "delims=" %%i in ('dir /b /od "output\performance_*.html" 2^>nul') do set ULTIMO=%%i
if defined ULTIMO (
    start "" "output\%ULTIMO%"
) else (
    echo  [AVISO] Sin datos de backtesting aun.
    echo  El reporte estara disponible tras los primeros partidos verificados.
)

echo.
pause
