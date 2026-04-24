@echo off
setlocal
cd /d C:\ClaudeWork
for /f "tokens=1,* delims==" %%A in ('findstr /i "^WMS_USUARIO_2=" .env') do set WMS_USUARIO=%%B
for /f "tokens=1,* delims==" %%A in ('findstr /i "^WMS_PASSWORD2=" .env') do set WMS_PASSWORD=%%B
cd /d C:\ClaudeWork\Productividad_Automatizacion
py productividad_descarga.py %*
exit /b %errorlevel%
