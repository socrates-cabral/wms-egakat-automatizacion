Import-Module ScheduledTasks -ErrorAction SilentlyContinue

$action   = New-ScheduledTaskAction `
    -Execute  '"C:\Users\Socrates Cabral\AppData\Local\Microsoft\WindowsApps\py.exe"' `
    -Argument '"C:\ClaudeWork\agente_apuestas\run_agent.py"'

$trigger  = New-ScheduledTaskTrigger -Daily -At "16:00"

$settings = New-ScheduledTaskSettingsSet `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2)

$principal = New-ScheduledTaskPrincipal `
    -UserId   "Q-SCABRAL\Socrates Cabral" `
    -RunLevel Highest `
    -LogonType Interactive

Register-ScheduledTask `
    -TaskName  "Agente Apuestas - Analisis Tarde" `
    -TaskPath  "\ClaudeWork\" `
    -Action    $action `
    -Trigger   $trigger `
    -Settings  $settings `
    -Principal $principal `
    -Force

Write-Host "[OK] Tarea registrada: Agente Apuestas - Analisis Tarde @ 16:00 diario"
