@echo off
REM  Hackea tu Metabolismo con IA — Lanzador (Puerto 8505)
cd /d C:\ClaudeWork\HackeaMetabolismo
echo Iniciando en http://localhost:8505 ...
py -m streamlit run dashboard/app.py --server.port 8505 --server.headless false
pause
