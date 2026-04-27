# Registrar Task Scheduler: API Cobranza Egakat (microservicio para n8n)
# Ejecutar como Administrador

$TaskName = "Softnet Ventas - API Cobranza (n8n)"
$PyExe    = (Get-Command py).Source
$Script   = "C:\ClaudeWork\Softnet_Ventas\bots\api_cobranza.py"
$WorkDir  = "C:\ClaudeWork\Softnet_Ventas"

$Env     = [System.Environment]::GetEnvironmentVariables("Machine")
$Action  = New-ScheduledTaskAction -Execute $PyExe -Argument $Script -WorkingDirectory $WorkDir

# Arrancar al inicio del sistema + reiniciar si falla
$Trigger  = New-ScheduledTaskTrigger -AtStartup

$Settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Hours 0) `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -MultipleInstances IgnoreNew

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -RunLevel Highest `
    -Force

# Iniciar ahora mismo
Start-ScheduledTask -TaskName $TaskName

Write-Host "Tarea registrada y arrancada: $TaskName" -ForegroundColor Green
Write-Host "La API estara disponible en http://localhost:8085"
