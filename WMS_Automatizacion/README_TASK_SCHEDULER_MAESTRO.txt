CONFIGURACIÓN TASK SCHEDULER — MAESTRO ARTÍCULOS DERCO
======================================================

NOMBRE TAREA: "WMS Egakat - Maestro DERCO" (o similar)

CONFIGURACIÓN:
──────────────

GENERAL:
  Nombre: WMS Egakat - Maestro DERCO
  Descripción: Descarga automática del Maestro de Artículos DERCO (30-45 min)
  ✓ Ejecutar sin importar si el usuario ha iniciado sesión o no
  ✓ Ejecutar con los privilegios más altos

DESENCADENADORES:
  Opción 1 — Diario (ej: 2 veces por mes)
    Recurrencia: Mensual el 1º y 15º
    Hora: 22:00 (para no interferir con descarga WMS diaria 08:00)

  Opción 2 — Manual (recomendado inicial)
    Sin desencadenador automático — ejecutar manualmente con Ejecutar botón

ACCIONES:
─────────

Programa/script:    wscript.exe
Argumentos:         "C:\ClaudeWork\WMS_Automatizacion\ejecutar_maestro_silencioso.vbs"
Comenzar en:        C:\ClaudeWork

EJEMPLO POWERSHELL (crear tarea automáticamente):
──────────────────────────────────────────────────

$taskName = "WMS Egakat - Maestro DERCO"
$script = "C:\ClaudeWork\WMS_Automatizacion\ejecutar_maestro_silencioso.vbs"

$action = New-ScheduledTaskAction `
  -Execute "wscript.exe" `
  -Argument "`"$script`"" `
  -WorkingDirectory "C:\ClaudeWork"

$trigger = New-ScheduledTaskTrigger `
  -At 22:00 `
  -DaysOfMonth 1,15 `
  -Monthly

$principal = New-ScheduledTaskPrincipal `
  -UserId "SYSTEM" `
  -LogonType ServiceAccount `
  -RunLevel Highest

Register-ScheduledTask `
  -TaskName $taskName `
  -Action $action `
  -Trigger $trigger `
  -Principal $principal `
  -Description "Descarga Maestro DERCO desde WMS Egakat (30-45 min)" `
  -Force

VERIFICACIÓN:
─────────────

Después de crear la tarea:
1. Abrir Task Scheduler (taskschd.msc)
2. Buscar "WMS Egakat - Maestro DERCO"
3. Clic derecho → Ejecutar → debería correr en segundo plano
4. Verificar log: C:\ClaudeWork\logs\maestro_run_*.log

SI LA VENTANA APARECE:
  - Verificar que "Comenzar en" = C:\ClaudeWork
  - Verificar que "Ejecutar sin importar si usuario ha iniciado sesión" ✓
  - Verificar que Argumentos entre comillas: "C:\...\vbs"

NOTAS:
──────

- maestro_articulos_derco.py tarda 30-45 minutos
- NO ejecutar durante descarga WMS diaria (08:00 L-V)
- Recomendado: 22:00 (10 PM) o madrugada (02:00)
- El script enviará correo HTML al finalizar (via Graph API)
- Log completo en: C:\ClaudeWork\logs\maestro_run_YYYYMMDD_HHMMSS.log

CAMBIOS v1.5 (desde v1.4):
────────────────────────

✅ NUEVO: ejecutar_maestro_silencioso.vbs (VBS wrapper)
✅ Task Scheduler ahora ejecuta vía wscript.exe (segundo plano)
✅ Patrón consistente con finanzas_personales (abrir_app_silencioso.vbs)
