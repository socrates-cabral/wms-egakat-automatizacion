@echo off
title Agente Apuestas Deportivas
color 0A
echo.
echo  ============================================
echo   AGENTE DE APUESTAS DEPORTIVAS
echo   Iniciando analisis del dia...
echo  ============================================
echo.

cd /d "C:\ClaudeWork\agente_apuestas"

echo  [1/3] Verificando cuota API...
echo  [2/3] Descargando partidos y lineups...
echo  [3/3] Generando recomendaciones...
echo.

py run_agent.py

echo.
echo  ============================================
echo   Reporte generado en output\
echo   Abriendo en el navegador...
echo  ============================================

:: Abre el reporte HTML mas reciente en el navegador
for /f "delims=" %%i in ('dir /b /od "output\reporte_*.html" 2^>nul') do set ULTIMO=%%i
if defined ULTIMO (
    start "" "output\%ULTIMO%"
) else (
    echo  [AVISO] No se encontro reporte generado aun.
)

echo.
pause
