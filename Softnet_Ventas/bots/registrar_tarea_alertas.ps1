# Registrar Task Scheduler: Softnet Ventas - Alertas Telegram
# Ejecutar como Administrador: powershell -ExecutionPolicy Bypass -File registrar_tarea_alertas.ps1

$TaskName    = "Softnet Ventas - Alertas Telegram"
$PyExe       = (Get-Command py).Source
$Script      = "C:\ClaudeWork\Softnet_Ventas\bots\run_alertas.py"
$WorkDir     = "C:\ClaudeWork\Softnet_Ventas"
$LogFile     = "C:\ClaudeWork\logs\alertas_telegram_scheduler.log"

$Action  = New-ScheduledTaskAction -Execute $PyExe -Argument $Script -WorkingDirectory $WorkDir
$Trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday -At "16:15"

$Settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 10) `
    -MultipleInstances IgnoreNew

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -RunLevel Highest `
    -Force

Write-Host "Tarea registrada: $TaskName" -ForegroundColor Green
Write-Host "Horario: L-V 16:15 | Script: $Script"
