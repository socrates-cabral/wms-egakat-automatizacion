# setup_task_tarde.ps1
# Crea la tarea "Agente Apuestas - Analisis Tarde" (16:00 diario)
# Ejecutar una sola vez como Administrador — pedira contrasena de Windows.
#
# Uso: powershell.exe -ExecutionPolicy Bypass -File setup_task_tarde.ps1

$xml = @'
<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Date>2026-04-12T16:00:00</Date>
    <Author>Q-SCABRAL\Socrates Cabral</Author>
    <Description>Segunda corrida del agente apuestas — 16:00 — captura lineups confirmados para partidos nocturnos europeos.</Description>
    <URI>\ClaudeWork\Agente Apuestas - Analisis Tarde</URI>
  </RegistrationInfo>
  <Principals>
    <Principal id="Author">
      <UserId>Q-SCABRAL\Socrates Cabral</UserId>
      <LogonType>Password</LogonType>
      <RunLevel>HighestAvailable</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <DisallowStartIfOnBatteries>true</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>true</StopIfGoingOnBatteries>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <IdleSettings>
      <Duration>PT10M</Duration>
      <WaitTimeout>PT1H</WaitTimeout>
      <StopOnIdleEnd>true</StopOnIdleEnd>
      <RestartOnIdle>false</RestartOnIdle>
    </IdleSettings>
  </Settings>
  <Triggers>
    <CalendarTrigger>
      <StartBoundary>2026-04-13T16:00:00</StartBoundary>
      <ScheduleByDay>
        <DaysInterval>1</DaysInterval>
      </ScheduleByDay>
    </CalendarTrigger>
  </Triggers>
  <Actions Context="Author">
    <Exec>
      <Command>"C:\Users\Socrates Cabral\AppData\Local\Microsoft\WindowsApps\py.exe"</Command>
      <Arguments>"C:\ClaudeWork\agente_apuestas\run_agent.py"</Arguments>
    </Exec>
  </Actions>
</Task>
'@

$taskName    = "Agente Apuestas - Analisis Tarde"
$taskPath    = "\ClaudeWork\"
$userId      = "Q-SCABRAL\Socrates Cabral"

# Pedir contrasena de Windows (necesaria para "Run whether user is logged on or not")
$cred = Get-Credential -UserName $userId -Message "Ingresa tu contrasena de Windows para registrar la tarea '$taskName'"

if (-not $cred) {
    Write-Host "[CANCELADO] No se proporcionaron credenciales." -ForegroundColor Red
    exit 1
}

try {
    $existente = Get-ScheduledTask -TaskName $taskName -TaskPath $taskPath -ErrorAction SilentlyContinue
    if ($existente) {
        Unregister-ScheduledTask -TaskName $taskName -TaskPath $taskPath -Confirm:$false
        Write-Host "[INFO] Tarea preexistente eliminada para reimportar." -ForegroundColor Yellow
    }

    Register-ScheduledTask `
        -TaskName $taskName `
        -TaskPath $taskPath `
        -Xml $xml `
        -User $userId `
        -Password $cred.GetNetworkCredential().Password `
        -Force | Out-Null

    Write-Host ""
    Write-Host "[OK] Tarea creada exitosamente:" -ForegroundColor Green
    Write-Host "     Nombre : $taskPath$taskName"
    Write-Host "     Horario: Diario a las 16:00"
    Write-Host "     Accion : py.exe run_agent.py"
    Write-Host ""
    Write-Host "Proxima ejecucion: 2026-04-13 16:00" -ForegroundColor Cyan
}
catch {
    Write-Host "[ERROR] No se pudo registrar la tarea: $_" -ForegroundColor Red
    exit 1
}
