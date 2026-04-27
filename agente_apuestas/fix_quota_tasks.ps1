# fix_quota_tasks.ps1
# Actualiza los argumentos de las tareas de analisis diario y tarde
# para usar --max-fixtures y respetar el limite de 90 req/dia de api-sports.
#
# Presupuesto:
#   Manana (--max-fixtures 4): 4x11 + 9 = 53 req
#   Tarde  (--max-fixtures 2): 2x11 + 9 = 31 req
#   Total:                              = 84 req (< 90 limite)
#
# Uso: powershell.exe -ExecutionPolicy Bypass -File fix_quota_tasks.ps1

$py = '"C:\Users\Socrates Cabral\AppData\Local\Microsoft\WindowsApps\py.exe"'
$script = '"C:\ClaudeWork\agente_apuestas\run_agent.py"'
$taskPath = "\ClaudeWork\"

$settings = New-ScheduledTaskSettingsSet `
    -MultipleInstances  IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2)

$principal = New-ScheduledTaskPrincipal `
    -UserId   "Q-SCABRAL\Socrates Cabral" `
    -RunLevel Highest `
    -LogonType Interactive

# ── Analisis Diario — 09:00 — max-fixtures 4 ─────────────────────────────────
$actionManana = New-ScheduledTaskAction `
    -Execute  $py `
    -Argument "$script --max-fixtures 4"

$triggerManana = New-ScheduledTaskTrigger -Daily -At "09:00"

Register-ScheduledTask `
    -TaskName  "Agente Apuestas - Analisis Diario" `
    -TaskPath  $taskPath `
    -Action    $actionManana `
    -Trigger   $triggerManana `
    -Settings  $settings `
    -Principal $principal `
    -Force | Out-Null

Write-Host "[OK] Analisis Diario  09:00 -> --max-fixtures 4 (53 req)" -ForegroundColor Green

# ── Analisis Tarde — 16:00 — max-fixtures 2 ──────────────────────────────────
$actionTarde = New-ScheduledTaskAction `
    -Execute  $py `
    -Argument "$script --max-fixtures 2"

$triggerTarde = New-ScheduledTaskTrigger -Daily -At "16:00"

Register-ScheduledTask `
    -TaskName  "Agente Apuestas - Analisis Tarde" `
    -TaskPath  $taskPath `
    -Action    $actionTarde `
    -Trigger   $triggerTarde `
    -Settings  $settings `
    -Principal $principal `
    -Force | Out-Null

Write-Host "[OK] Analisis Tarde   16:00 -> --max-fixtures 2 (31 req)" -ForegroundColor Green
Write-Host ""
Write-Host "Presupuesto total: 53 + 31 = 84 req/dia (limite: 90)" -ForegroundColor Cyan
