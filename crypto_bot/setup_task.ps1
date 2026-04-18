# Setup Task Scheduler para Crypto Bot - Grid Trading
# Ejecutar como Administrador

$TaskName = "Crypto Bot - Grid Trading"
$WorkDir = "C:\ClaudeWork"
$PythonExe = (Get-Command py).Source
$Script = "crypto_bot\run_bot.py"

# Eliminar tarea existente si hay
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

$Action = New-ScheduledTaskAction `
    -Execute $PythonExe `
    -Argument $Script `
    -WorkingDirectory $WorkDir

# Trigger: cada 5 minutos, indefinido
$Trigger = New-ScheduledTaskTrigger -RepetitionInterval (New-TimeSpan -Minutes 5) -Once -At (Get-Date)

$Settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 4) `
    -MultipleInstances IgnoreNew `
    -RunOnlyIfNetworkAvailable $true

$Principal = New-ScheduledTaskPrincipal `
    -UserId $env:USERNAME `
    -LogonType S4U `
    -RunLevel Highest

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Principal $Principal `
    -Description "Grid Trading Bot BTC/USDT con filtro EMA 200. Paper trading mode."

Write-Host "Tarea '$TaskName' registrada. Intervalo: 5 minutos."
Write-Host "Para detener: crear C:\ClaudeWork\crypto_bot\kill_switch.txt"
