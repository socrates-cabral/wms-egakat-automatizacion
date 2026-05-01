@echo off
cd /d C:\ClaudeWork\WMS_Automatizacion

set "PYTHON_EXE=C:\Users\Socrates Cabral\AppData\Local\Python\pythoncore-3.14-64\python.exe"

echo ========================================== >> C:\ClaudeWork\WMS_Automatizacion\api_operaciones_task.log
echo Iniciando API Operaciones %date% %time% >> C:\ClaudeWork\WMS_Automatizacion\api_operaciones_task.log
echo Python usado: %PYTHON_EXE% >> C:\ClaudeWork\WMS_Automatizacion\api_operaciones_task.log
echo Directorio actual: %CD% >> C:\ClaudeWork\WMS_Automatizacion\api_operaciones_task.log
echo ========================================== >> C:\ClaudeWork\WMS_Automatizacion\api_operaciones_task.log

"%PYTHON_EXE%" C:\ClaudeWork\WMS_Automatizacion\api_operaciones.py >> C:\ClaudeWork\WMS_Automatizacion\api_operaciones_task.log 2>&1