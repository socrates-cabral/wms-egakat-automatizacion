# Ejecutar como Administrador: PowerShell → clic derecho → "Ejecutar como administrador"
# powershell -ExecutionPolicy Bypass -File "C:\ClaudeWork\Softnet_Ventas\registrar_tarea.ps1"

$action  = New-ScheduledTaskAction -Execute "py" -Argument "C:\ClaudeWork\Softnet_Ventas\src\run_ventas.py"
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday -At "16:00"
$settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2) `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew

Register-ScheduledTask `
    -TaskName "Softnet Ventas - Descarga Diaria" `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -RunLevel Highest `
    -Force

Write-Host "Tarea registrada OK: 'Softnet Ventas - Descarga Diaria' - L-V 16:00"
