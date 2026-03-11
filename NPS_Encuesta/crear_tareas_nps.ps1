# crear_tareas_nps.ps1
# Ejecutar en PowerShell como Administrador

$python = "C:\Users\Socrates Cabral\AppData\Local\Python\pythoncore-3.14-64\python.exe"
$script = "C:\ClaudeWork\NPS_Encuesta\nps_descarga.py"
$usuario = "Socrates Cabral"

# ── Tarea 1: Primera descarga unica 28/03/2026 10:00 ─────────────────────────
$xml1 = @"
<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>Descarga unica NPS + CSAT primera corrida post-envio marzo 2026</Description>
  </RegistrationInfo>
  <Triggers>
    <TimeTrigger>
      <StartBoundary>2026-03-28T10:00:00</StartBoundary>
      <Enabled>true</Enabled>
    </TimeTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <LogonType>Password</LogonType>
      <RunLevel>HighestAvailable</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>true</RunOnlyIfNetworkAvailable>
    <ExecutionTimeLimit>PT1H</ExecutionTimeLimit>
    <Enabled>true</Enabled>
  </Settings>
  <Actions>
    <Exec>
      <Command>$python</Command>
      <Arguments>$script</Arguments>
    </Exec>
  </Actions>
</Task>
"@

# ── Tarea 2: CSAT mensual dia 11 de cada mes 10:00 ───────────────────────────
$xml2 = @"
<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>Descarga CSAT operacional dia 11 de cada mes</Description>
  </RegistrationInfo>
  <Triggers>
    <CalendarTrigger>
      <StartBoundary>2026-04-11T10:00:00</StartBoundary>
      <Enabled>true</Enabled>
      <ScheduleByMonth>
        <DaysOfMonth>
          <Day>11</Day>
        </DaysOfMonth>
        <Months>
          <January/><February/><March/><April/><May/><June/>
          <July/><August/><September/><October/><November/><December/>
        </Months>
      </ScheduleByMonth>
    </CalendarTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <LogonType>Password</LogonType>
      <RunLevel>HighestAvailable</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>true</RunOnlyIfNetworkAvailable>
    <ExecutionTimeLimit>PT1H</ExecutionTimeLimit>
    <Enabled>true</Enabled>
  </Settings>
  <Actions>
    <Exec>
      <Command>$python</Command>
      <Arguments>$script</Arguments>
    </Exec>
  </Actions>
</Task>
"@

# ── Tarea 3: NPS trimestral dia 16 mar/jun/sep/dic 10:00 ─────────────────────
$xml3 = @"
<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>Descarga NPS trimestral dia 16 de marzo junio septiembre diciembre</Description>
  </RegistrationInfo>
  <Triggers>
    <CalendarTrigger>
      <StartBoundary>2026-06-16T10:00:00</StartBoundary>
      <Enabled>true</Enabled>
      <ScheduleByMonth>
        <DaysOfMonth>
          <Day>16</Day>
        </DaysOfMonth>
        <Months>
          <March/><June/><September/><December/>
        </Months>
      </ScheduleByMonth>
    </CalendarTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <LogonType>Password</LogonType>
      <RunLevel>HighestAvailable</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>true</RunOnlyIfNetworkAvailable>
    <ExecutionTimeLimit>PT1H</ExecutionTimeLimit>
    <Enabled>true</Enabled>
  </Settings>
  <Actions>
    <Exec>
      <Command>$python</Command>
      <Arguments>$script</Arguments>
    </Exec>
  </Actions>
</Task>
"@

# Guardar XML y crear tareas
$tareas = @(
    @{ Nombre = "NPS Egakat - Primera descarga"; XML = $xml1; Desc = "28/03/2026 10:00 una sola vez" },
    @{ Nombre = "NPS Egakat - CSAT Mensual";     XML = $xml2; Desc = "dia 11 de cada mes 10:00" },
    @{ Nombre = "NPS Egakat - NPS Trimestral";   XML = $xml3; Desc = "dia 16 mar/jun/sep/dic 10:00" }
)

foreach ($t in $tareas) {
    $xmlPath = "$env:TEMP\tarea_nps_temp.xml"
    $t.XML | Out-File -FilePath $xmlPath -Encoding Unicode

    $resultado = schtasks /create /tn $t.Nombre /xml $xmlPath /ru $usuario /rp /f 2>&1
    Remove-Item $xmlPath

    if ($LASTEXITCODE -eq 0) {
        Write-Host "OK  $($t.Nombre) - $($t.Desc)"
    } else {
        Write-Host "ERR $($t.Nombre): $resultado"
    }
}

Write-Host ""
Write-Host "Verificar en: Programador de tareas > Biblioteca del Programador de tareas"
