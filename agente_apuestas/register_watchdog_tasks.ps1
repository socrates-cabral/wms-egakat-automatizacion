$action = New-ScheduledTaskAction `
    -Execute  '"C:\Users\Socrates Cabral\AppData\Local\Microsoft\WindowsApps\py.exe"' `
    -Argument '"C:\ClaudeWork\agente_apuestas\watchdog.py"'

$settings = New-ScheduledTaskSettingsSet `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 2)

$principal = New-ScheduledTaskPrincipal `
    -UserId   "Q-SCABRAL\Socrates Cabral" `
    -RunLevel Highest `
    -LogonType Interactive

# Watchdog manana — verifica corrida 09:00 a las 10:05
$trigger1 = New-ScheduledTaskTrigger -Daily -At "10:05"
Register-ScheduledTask `
    -TaskName  "Agente Apuestas - Watchdog Manana" `
    -TaskPath  "\ClaudeWork\" `
    -Action    $action `
    -Trigger   $trigger1 `
    -Settings  $settings `
    -Principal $principal `
    -Force

# Watchdog tarde — verifica corrida 16:00 a las 17:05
$trigger2 = New-ScheduledTaskTrigger -Daily -At "17:05"
Register-ScheduledTask `
    -TaskName  "Agente Apuestas - Watchdog Tarde" `
    -TaskPath  "\ClaudeWork\" `
    -Action    $action `
    -Trigger   $trigger2 `
    -Settings  $settings `
    -Principal $principal `
    -Force

Write-Host "[OK] Watchdog Manana (10:05) y Watchdog Tarde (17:05) registrados en ClaudeWork\"
