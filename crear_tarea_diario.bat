@echo off
echo === Crear tarea: Productividad Diario - EGA KAT ===
echo.
set /p PWD="Ingresa tu password de Windows: "

schtasks /delete /tn "Productividad Diario - EGA KAT" /f 2>nul

schtasks /create ^
  /tn "Productividad Diario - EGA KAT" ^
  /tr "\"C:\Users\Socrates Cabral\AppData\Local\Python\pythoncore-3.14-64\python.exe\" \"C:\ClaudeWork\Productividad_Automatizacion\productividad_diario.py\"" ^
  /sc WEEKLY ^
  /d MON,TUE,WED,THU,FRI ^
  /st 10:30 ^
  /ru "Q-SCABRAL\Socrates Cabral" ^
  /rp "%PWD%" ^
  /rl HIGHEST ^
  /f

echo.
echo Resultado: %ERRORLEVEL%
schtasks /query /tn "Productividad Diario - EGA KAT" /fo LIST | findstr /i "nombre estado hora"
echo.
pause
