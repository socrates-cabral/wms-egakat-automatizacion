@echo off
echo Ejecutar este script como ADMINISTRADOR
echo.

REM Deshabilitar tarea antigua de productividad
schtasks /change /tn "Productividad Egakat - Descarga Diaria" /disable
echo [1] Tarea antigua deshabilitada (errorlevel=%ERRORLEVEL%)

REM Eliminar tarea nueva si ya existe
schtasks /delete /tn "Productividad Diario - EGA KAT" /f 2>nul

REM Crear tarea nueva
schtasks /create ^
  /tn "Productividad Diario - EGA KAT" ^
  /tr "\"C:\Users\Socrates Cabral\AppData\Local\Python\pythoncore-3.14-64\python.exe\" \"C:\ClaudeWork\Productividad_Automatizacion\productividad_diario.py\"" ^
  /sc WEEKLY ^
  /d MON,TUE,WED,THU,FRI ^
  /st 10:30 ^
  /ru "Q-SCABRAL\Socrates Cabral" ^
  /rp %2 ^
  /rl HIGHEST ^
  /f
echo [2] Tarea nueva creada (errorlevel=%ERRORLEVEL%)

echo.
echo === Verificacion ===
schtasks /query /tn "Productividad Egakat - Descarga Diaria" /fo LIST | findstr /i "nombre estado"
schtasks /query /tn "Productividad Diario - EGA KAT" /fo LIST | findstr /i "nombre estado"
echo.
pause
