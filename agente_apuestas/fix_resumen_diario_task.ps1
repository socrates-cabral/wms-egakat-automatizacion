# fix_resumen_diario_task.ps1
# Re-registra "Agente Apuestas - Resumen Diario" con LogonType Interactive.
# Motivo: LogonType Password causaba 0x80070005 (Access Denied) cuando la
# contrasena almacenada expiraba. Interactive no necesita contrasena guardada
# y es suficiente dado que la laptop esta encendida a las 22:00.
#
# Uso: powershell.exe -ExecutionPolicy Bypass -File fix_resumen_diario_task.ps1

$taskName = "Agente Apuestas - Resumen Diario"
$taskPath = "\ClaudeWork\"

$action = New-ScheduledTaskAction `
    -Execute  '"C:\Users\Socrates Cabral\AppData\Local\Microsoft\WindowsApps\py.exe"' `
    -Argument '"C:\ClaudeWork\agente_apuestas\backtesting\run_backtesting.py"'

$trigger = New-ScheduledTaskTrigger -Daily -At "22:00"

$settings = New-ScheduledTaskSettingsSet `
    -MultipleInstances  IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 10)

$principal = New-ScheduledTaskPrincipal `
    -UserId   "Q-SCABRAL\Socrates Cabral" `
    -RunLevel Highest `
    -LogonType Interactive

# Eliminar tarea anterior
$existente = Get-ScheduledTask -TaskName $taskName -TaskPath $taskPath -ErrorAction SilentlyContinue
if ($existente) {
    Unregister-ScheduledTask -TaskName $taskName -TaskPath $taskPath -Confirm:$false
    Write-Host "[INFO] Tarea anterior eliminada." -ForegroundColor Yellow
}

Register-ScheduledTask `
    -TaskName  $taskName `
    -TaskPath  $taskPath `
    -Action    $action `
    -Trigger   $trigger `
    -Settings  $settings `
    -Principal $principal `
    -Force | Out-Null

Write-Host ""
Write-Host "[OK] Tarea re-registrada con LogonType Interactive:" -ForegroundColor Green
Write-Host "     $taskPath$taskName"
Write-Host "     Horario : diario 22:00"
Write-Host "     LogonType: Interactive (sin contrasena almacenada)"
Write-Host ""
Write-Host "Verificar que corre manana a las 22:00." -ForegroundColor Cyan
