@echo off
setlocal
cd /d C:\ClaudeWork\Productividad_Automatizacion
py productividad_descarga.py %*
exit /b %errorlevel%
