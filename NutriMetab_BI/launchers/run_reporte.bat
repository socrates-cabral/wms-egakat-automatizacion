@echo off
REM ============================================================
REM  NutriMetab BI — Genera reporte Excel + HTML
REM  Salida en data\exports\
REM ============================================================
cd /d C:\ClaudeWork\NutriMetab_BI

echo Generando reportes...
py src/reportes/generar_reporte.py
echo.
echo Reportes disponibles en data\exports\
pause
