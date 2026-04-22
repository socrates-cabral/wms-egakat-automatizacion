$vbs = 'C:\ClaudeWork\wms_despacho\ejecutar_pipeline_silencioso.vbs'
$action = New-ScheduledTaskAction -Execute 'wscript.exe' -Argument $vbs
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Hours 2) -MultipleInstances IgnoreNew

$tareas = @(
    @{ Nombre = 'WMS Pipeline - Manana 08:00';   Hora = '08:00' },
    @{ Nombre = 'WMS Pipeline - Mediodia 13:00'; Hora = '13:00' },
    @{ Nombre = 'WMS Pipeline - Tarde 17:00';    Hora = '17:00' }
)

foreach ($t in $tareas) {
    $trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday -At $t.Hora
    Unregister-ScheduledTask -TaskName $t.Nombre -Confirm:$false -ErrorAction SilentlyContinue
    Register-ScheduledTask -TaskName $t.Nombre -Action $action -Trigger $trigger -Settings $settings -RunLevel Highest -Force | Out-Null
    Write-Host "Creada: $($t.Nombre)" -ForegroundColor Green
}

Write-Host ""
Write-Host "NOTA: Eliminar las tareas antiguas 'WMS Despacho - *' si ya no se usan." -ForegroundColor Yellow
Write-Host ""
Get-ScheduledTask | Where-Object { $_.TaskName -like '*Pipeline*' -or $_.TaskName -like '*Despacho*' } | ForEach-Object {
    $i = Get-ScheduledTaskInfo $_.TaskName
    Write-Host "$($_.TaskName) | $($_.State) | $($i.NextRunTime)"
}
