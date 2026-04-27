# Registrar Task Scheduler: Softnet Ventas - Reporte Semanal Cobranza
# Ejecutar como Administrador

$TaskName = "Softnet Ventas - Reporte Semanal Cobranza"
$PyExe    = (Get-Command py).Source
$Script   = "C:\ClaudeWork\Softnet_Ventas\bots\run_reporte_semanal.py"
$WorkDir  = "C:\ClaudeWork\Softnet_Ventas"

$Action  = New-ScheduledTaskAction -Execute $PyExe -Argument $Script -WorkingDirectory $WorkDir
$Trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At "08:00"

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
Write-Host "Horario: Lunes 08:00 | Script: $Script"
