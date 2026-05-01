@echo off
setlocal

cd /d C:\ClaudeWork\Softnet_Ventas

set "PYTHON_EXE=C:\Users\Socrates Cabral\AppData\Local\Python\pythoncore-3.14-64\python.exe"
set "LOG_DIR=C:\ClaudeWork\Softnet_Ventas\logs"
set "LOG_FILE=%LOG_DIR%\descarga_diaria_task.log"

if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

echo. >> "%LOG_FILE%"
echo ========================================== >> "%LOG_FILE%"
echo Iniciando descarga diaria Softnet %date% %time% >> "%LOG_FILE%"
echo Directorio actual: %CD% >> "%LOG_FILE%"
echo Python configurado: %PYTHON_EXE% >> "%LOG_FILE%"
echo ========================================== >> "%LOG_FILE%"

if not exist "%PYTHON_EXE%" (
    echo ERROR: No existe PYTHON_EXE: %PYTHON_EXE% >> "%LOG_FILE%"
    exit /b 9009
)

"%PYTHON_EXE%" "C:\ClaudeWork\Softnet_Ventas\src\run_ventas.py" >> "%LOG_FILE%" 2>&1

set "RC=%ERRORLEVEL%"
echo Exit code: %RC% >> "%LOG_FILE%"
echo Fin descarga diaria Softnet %date% %time% >> "%LOG_FILE%"
echo ========================================== >> "%LOG_FILE%"

exit /b %RC%
