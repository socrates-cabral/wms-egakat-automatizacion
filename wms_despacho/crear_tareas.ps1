$vbs = 'C:\ClaudeWork\wms_despacho\ejecutar_despacho_silencioso.vbs'
$tr = 'wscript.exe "C:\ClaudeWork\wms_despacho\ejecutar_despacho_silencioso.vbs"'

schtasks /delete /tn "WMS Despacho - Manana 08:00" /f 2>$null
schtasks /create /tn "WMS Despacho - Manana 08:00" /tr $tr /sc WEEKLY /d MON,TUE,WED,THU,FRI /st 08:00 /rl HIGHEST /f
schtasks /delete /tn "WMS Despacho - Mediodia 13:00" /f 2>$null
schtasks /create /tn "WMS Despacho - Mediodia 13:00" /tr $tr /sc WEEKLY /d MON,TUE,WED,THU,FRI /st 13:00 /rl HIGHEST /f
schtasks /delete /tn "WMS Despacho - Tarde 17:00" /f 2>$null
schtasks /create /tn "WMS Despacho - Tarde 17:00" /tr $tr /sc WEEKLY /d MON,TUE,WED,THU,FRI /st 17:00 /rl HIGHEST /f

Write-Host ""
schtasks /query /fo TABLE | findstr /i "Despacho"
