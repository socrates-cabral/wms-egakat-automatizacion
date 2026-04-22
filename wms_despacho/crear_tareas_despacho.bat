@echo off
REM Crea 3 tareas Task Scheduler para WMS Despacho Automatico
REM Ejecutar como Administrador

powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
"$vbs = 'C:\ClaudeWork\wms_despacho\ejecutar_despacho_silencioso.vbs'; " ^
"$action = New-ScheduledTaskAction -Execute 'wscript.exe' -Argument $vbs; " ^
"$trigger08 = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday -At '08:00'; " ^
"$trigger13 = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday -At '13:00'; " ^
"$trigger17 = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday -At '17:00'; " ^
"$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Hours 2) -MultipleInstances IgnoreNew; " ^
"$principal = New-ScheduledTaskPrincipal -UserId (whoami) -LogonType Interactive -RunLevel Highest; " ^
"Unregister-ScheduledTask -TaskName 'WMS Despacho - Manana 08:00' -Confirm:$false -ErrorAction SilentlyContinue; " ^
"Unregister-ScheduledTask -TaskName 'WMS Despacho - Mediodia 13:00' -Confirm:$false -ErrorAction SilentlyContinue; " ^
"Unregister-ScheduledTask -TaskName 'WMS Despacho - Tarde 17:00' -Confirm:$false -ErrorAction SilentlyContinue; " ^
"Register-ScheduledTask -TaskName 'WMS Despacho - Manana 08:00' -Action $action -Trigger $trigger08 -Settings $settings -Principal $principal -Force | Out-Null; Write-Host 'Creada: WMS Despacho - Manana 08:00'; " ^
"Register-ScheduledTask -TaskName 'WMS Despacho - Mediodia 13:00' -Action $action -Trigger $trigger13 -Settings $settings -Principal $principal -Force | Out-Null; Write-Host 'Creada: WMS Despacho - Mediodia 13:00'; " ^
"Register-ScheduledTask -TaskName 'WMS Despacho - Tarde 17:00' -Action $action -Trigger $trigger17 -Settings $settings -Principal $principal -Force | Out-Null; Write-Host 'Creada: WMS Despacho - Tarde 17:00'; " ^
"Get-ScheduledTask | Where-Object { $_.TaskName -like '*Despacho*' } | Select-Object TaskName,State | Format-Table -AutoSize"

echo.
pause
