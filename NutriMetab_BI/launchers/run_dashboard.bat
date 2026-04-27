@echo off
REM ============================================================
REM  NutriMetab BI — Lanzador dashboard Streamlit
REM  Puerto: 8504
REM ============================================================
cd /d C:\ClaudeWork\NutriMetab_BI

echo Iniciando NutriMetab BI en http://localhost:8504 ...
py -m streamlit run dashboard/app.py --server.port 8504 --server.headless true
pause
