@echo off
:: Backup Claude Memory → OneDrive Egakat
:: Ejecutar manualmente o programar en Task Scheduler (semanal recomendado)

powershell -Command ^
  "$src = 'C:\Users\Socrates Cabral\.claude\projects\C--ClaudeWork\memory';" ^
  "$dst = 'C:\Users\Socrates Cabral\OneDrive - EGA KAT LOGISTICA SPA\Backups\claude_memory';" ^
  "New-Item -ItemType Directory -Force -Path $dst | Out-Null;" ^
  "Copy-Item -Path \"$src\*\" -Destination $dst -Recurse -Force;" ^
  "Write-Host \"[OK] Backup Claude Memory completado - $(Get-Date -Format 'yyyy-MM-dd HH:mm') -> $dst\""
