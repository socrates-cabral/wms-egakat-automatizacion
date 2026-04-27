@echo off
REM ============================================================
REM  NutriMetab BI — Pipeline de ingesta (CSV -> SQLite)
REM  Usar para actualizar datos desde data\raw\
REM ============================================================
cd /d C:\ClaudeWork\NutriMetab_BI

echo Ejecutando pipeline de ingesta...
py src/ingesta/carga_datos.py
echo.
echo Ingesta completada. Revisa logs\ para detalles.
pause
