PAQUETE WMS VALIDATOR — IMPORTANTE
=================================

Este paquete fue armado para NO cambiar los nombres de tus scripts actuales
ni alterar la secuencia principal de trabajo.

Contenido:
- WMS_Automatizacion\validation_utils.py
- WMS_Automatizacion\validation_rules.py
- WMS_Automatizacion\validator_agent.py
- WMS_Automatizacion\run_todos.py   (version parcheada sobre tu archivo actual)

Que cambia:
- Se agrega un Modulo 9 de validacion post-ejecucion.
- El validador NO bloquea la corrida principal.
- Si el validador falla por cualquier razon, solo deja [WARN] en el log/correo.
- No se cambian los nombres de tus modulos existentes.
- No se toca el orden de ejecucion de tus modulos actuales.

Como instalar:
1) Haz respaldo de tu archivo actual:
   C:\ClaudeWork\WMS_Automatizacion\run_todos.py
2) Copia estos 4 archivos dentro de:
   C:\ClaudeWork\WMS_Automatizacion\
3) Sustituye solo run_todos.py si quieres activar la validacion integrada.

Si quieres usar el validador sin tocar run_todos.py:
- Copia validation_utils.py
- Copia validation_rules.py
- Copia validator_agent.py
- Ejecuta manualmente:
  py C:\ClaudeWork\WMS_Automatizacion\validator_agent.py

Salida del validador:
C:\ClaudeWork\logs\validaciones\
