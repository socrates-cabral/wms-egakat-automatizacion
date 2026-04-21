@echo off
REM Crea tarea Task Scheduler para productividad_diario.py
REM Ejecutar como Administrador

set TASK_NAME=Productividad Diario - EGA KAT
set SCRIPT_PATH=C:\ClaudeWork\Productividad_Automatizacion\productividad_diario.py
set PYTHON_PATH=C:\Users\Socrates Cabral\AppData\Local\Python\pythoncore-3.14-64\python.exe
set START_TIME=10:30

schtasks /delete /tn "%TASK_NAME%" /f 2>nul
echo Creando tarea: %TASK_NAME%

schtasks /create ^
  /tn "%TASK_NAME%" ^
  /tr "\"%PYTHON_PATH%\" \"%SCRIPT_PATH%\"" ^
  /sc WEEKLY ^
  /d MON,TUE,WED,THU,FRI ^
  /st %START_TIME% ^
  /ru "Socrates Cabral" ^
  /rp ^
  /rl HIGHEST ^
  /f

echo.
echo Tarea creada. Verificando:
schtasks /query /tn "%TASK_NAME%" /fo LIST
