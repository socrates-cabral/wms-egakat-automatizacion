# Setup Task Scheduler para Crypto Bot - Grid Trading
# Ejecutar como Administrador

$TaskName = "Crypto Bot - Grid Trading"
$WorkDir = "C:\ClaudeWork"
$BatFile = "C:\ClaudeWork\crypto_bot\run_bot.bat"

# Eliminar tarea existente si hay
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

$Action = New-ScheduledTaskAction `
    -Execute "cmd.exe" `
    -Argument "/c `"$BatFile`"" `
    -WorkingDirectory $WorkDir

# Trigger: cada 5 minutos, indefinido
$Trigger = New-ScheduledTaskTrigger -RepetitionInterval (New-TimeSpan -Minutes 5) -Once -At (Get-Date)

$Settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 4) `
    -MultipleInstances IgnoreNew `
    -RunOnlyIfNetworkAvailable

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
    -Description "Grid Trading Bot BTC/USDT + ETH/USDT con filtro EMA 200. Modo REAL — Kraken."

Write-Host "Tarea '$TaskName' registrada. Intervalo: 5 minutos."
Write-Host "Para detener: crear C:\ClaudeWork\crypto_bot\kill_switch.txt"

# ── Tarea 2: Cleanup niveles huérfanos (1x día a las 06:00) ──────────────────
$CleanupTaskName = "Crypto Bot - Cleanup Huerfanos"
$CleanupBat      = "C:\ClaudeWork\crypto_bot\run_cleanup.bat"

Unregister-ScheduledTask -TaskName $CleanupTaskName -Confirm:$false -ErrorAction SilentlyContinue

$CleanupAction = New-ScheduledTaskAction `
    -Execute "cmd.exe" `
    -Argument "/c `"$CleanupBat`"" `
    -WorkingDirectory $WorkDir

$CleanupTrigger = New-ScheduledTaskTrigger -Daily -At "06:00"

$CleanupSettings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 2) `
    -MultipleInstances IgnoreNew `
    -RunOnlyIfNetworkAvailable

Register-ScheduledTask `
    -TaskName $CleanupTaskName `
    -Action $CleanupAction `
    -Trigger $CleanupTrigger `
    -Settings $CleanupSettings `
    -Principal $Principal `
    -Description "Detecta y limpia niveles buy_open sin respaldo en Kraken spot (ej: BTC en Staking)."

Write-Host "Tarea '$CleanupTaskName' registrada. Corre diariamente a las 06:00."
