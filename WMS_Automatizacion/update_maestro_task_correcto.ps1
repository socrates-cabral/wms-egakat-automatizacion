$taskName = "WMS Egakat - Maestro Articulos Derco"
$script = "C:\ClaudeWork\WMS_Automatizacion\ejecutar_maestro_silencioso.vbs"

$action = New-ScheduledTaskAction -Execute "wscript.exe" -Argument "`"$script`"" -WorkingDirectory "C:\ClaudeWork"

# Trigger: lunes a viernes a las 09:00 AM
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday -At 09:00

$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal -Description "Descarga Maestro DERCO desde WMS Egakat (30-45 min) — L-V 09:00 AM" -Force

Write-Host "✅ Tarea corregida:"
Write-Host "   Horario: Lunes a Viernes a las 09:00 AM"
Write-Host "   Programa: wscript.exe"
Write-Host "   Script: $script"
