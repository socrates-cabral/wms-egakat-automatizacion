$action = New-ScheduledTaskAction `
    -Execute 'C:\Users\Socrates Cabral\AppData\Local\Python\pythoncore-3.14-64\python.exe' `
    -Argument 'C:\ClaudeWork\VDR_Comparador\vdr_comparador.py'

$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday -At 08:00:00
$trigger.Repetition.Interval = 'PT1H'
$trigger.Repetition.Duration = 'PT11H'

$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 30)

$principal = New-ScheduledTaskPrincipal -UserId 'Socrates Cabral' -LogonType Password -RunLevel Highest

Register-ScheduledTask `
    -TaskName 'VDR Comparador - EGA KAT' `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Principal $principal `
    -Force
