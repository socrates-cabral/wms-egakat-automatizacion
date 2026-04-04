@echo off
REM  Hackea tu Metabolismo con IA — Setup inicial
cd /d C:\ClaudeWork\HackeaMetabolismo
echo [1/3] Instalando dependencias...
py -m pip install -r requirements.txt
echo [2/3] Inicializando DB...
py src/db/schema.py
echo [3/3] Listo. Ejecuta: launchers\run.bat
pause
