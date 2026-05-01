# Ejecutar como Administrador:
# PowerShell → clic derecho → "Ejecutar como administrador"
# powershell -ExecutionPolicy Bypass -File "C:\ClaudeWork\Softnet_Ventas\registrar_tarea.ps1"

$baseDir = "C:\ClaudeWork\Softnet_Ventas"
$batPath = "$baseDir\iniciar_descarga_diaria.bat"
$logDir  = "$baseDir\logs"

if (!(Test-Path $logDir)) {
    New-Item -ItemType Directory -Path $logDir | Out-Null
}

# Crear launcher robusto para la descarga diaria
$batContent = @'
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
'@

Set-Content -Path $batPath -Value $batContent -Encoding ASCII

# Acción robusta para Programador de tareas
$action = New-ScheduledTaskAction `
    -Execute "C:\Windows\System32\cmd.exe" `
    -Argument '/c "C:\ClaudeWork\Softnet_Ventas\iniciar_descarga_diaria.bat"' `
    -WorkingDirectory "C:\ClaudeWork\Softnet_Ventas"

# Lunes a viernes a las 16:00
$trigger = New-ScheduledTaskTrigger `
    -Weekly `
    -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday `
    -At "16:00"

$settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2) `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -WakeToRun

# Playwright: mejor ejecutar solo si el usuario inició sesión
$principal = New-ScheduledTaskPrincipal `
    -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType Interactive `
    -RunLevel Highest

Register-ScheduledTask `
    -TaskName "Softnet Ventas - Descarga Diaria" `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Principal $principal `
    -Force

Write-Host "Tarea registrada OK: 'Softnet Ventas - Descarga Diaria' - L-V 16:00"
Write-Host "Launcher creado en: $batPath"
Write-Host "Log esperado en: C:\ClaudeWork\Softnet_Ventas\logs\descarga_diaria_task.log"