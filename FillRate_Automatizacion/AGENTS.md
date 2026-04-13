# AGENTS.md

## Proposito del proyecto
Este repositorio implementa una automatizacion independiente para descargar el reporte "Consulta de Fill Rate" desde WMS EgaKat, procesarlo y actualizar archivos acumulados en SharePoint via Microsoft Graph API, ademas de enviar un correo resumen final.

## Contexto operativo obligatorio
- Entorno: Windows 10/11.
- Comando Python: usar siempre `py`.
- Instalacion de paquetes: usar siempre `py -m pip`.
- Launchers: usar `.bat`. No usar `.ps1` ni `.vbs`.
- Credenciales: leer siempre desde `.env`. Nunca hardcodear secretos.
- Task Scheduler: se configura manualmente desde GUI; no usar `schtasks` CLI.
- Carpeta del proyecto: `C:\ClaudeWork\FillRate_Automatizacion\`
- Repositorio: `socrates-cabral/ClaudeWork-`
- Microsoft Graph API ya esta disponible en el ecosistema WMS existente y debe reutilizarse.

## Excepcion aprobada
- Aunque la especificacion inicial de FillRate mencionaba Selenium, este repositorio usara Playwright como excepcion aprobada.
- Motivo: mantener compatibilidad con el ecosistema WMS vivo existente en `C:\ClaudeWork\WMS_Automatizacion\`.
- Esta excepcion aplica solo a la automatizacion WMS. No cambia el resto de reglas operativas del proyecto.

## Estructura esperada del proyecto
- `fillrate_descarga.py` = script principal
- `fillrate_config.py` = configuracion de clientes
- `fillrate_utils.py` = helpers de Graph API, formulas, corte y correo
- `run_fillrate.bat` = launcher
- `requirements_fillrate.txt` = dependencias
- `logs\` = salida de logs diarios

## Reglas duras que no se deben romper
- No cambiar el stack base sin instruccion explicita.
- No cambiar Playwright por otra libreria sin instruccion explicita.
- No inventar nombres del dropdown WMS. Verificar siempre el texto visible exacto en runtime.
- No tocar la hoja `base` del archivo SharePoint.
- Trabajar siempre sobre la hoja `seguimiento de pedidos`; si no existe, usar la primera hoja disponible y dejarlo documentado en log.
- Antes de escribir formulas en columnas AA:AS, leer la fila 2 del archivo real y usarla como template.
- `Corte` se calcula en Python y solo aplica cuando `has_corte=True`.
- Si un cliente tiene `active=False`, omitirlo y continuar. No tratarlo como error.
- Si el WMS devuelve 0 filas, no modificar SharePoint para ese cliente.
- Si falla Graph API, reintentar una vez antes de marcar error.
- No exponer credenciales, tokens, client secrets, tenant IDs ni contrasenas en logs o respuestas.
- Mantener compatibilidad con la arquitectura existente del ecosistema WMS Egakat.

## Flujo funcional que se debe preservar
Para cada cliente activo:
1. Abrir Chrome con Playwright.
2. Ir a `https://egakatwms.cl/sglwms_EGA_prod/hinicio.aspx`
3. Hacer login con `WMS_USUARIO` y `WMS_CLAVE`.
4. Seleccionar deposito segun `cliente.deposito_wms`.
5. Entrar a `Procesos WMS`.
6. Entrar a `Consulta de Fill Rate`.
7. Configurar filtros:
   - deposito = cliente.deposito_wms
   - empresa = cliente.empresa_wms
   - operacion = `ORDEN DE PREP. C/STOCK`
   - fecha desde = primer dia del mes actual
   - fecha hasta = ayer
8. Exportar Excel.
9. Renombrar o mover la descarga a `logs\temp_fillrate_{cliente.nombre}.xlsx`
10. Procesar Excel descargado.
11. Descargar archivo SharePoint del cliente via Graph API.
12. Reemplazar solo el mes actual en el archivo acumulado.
13. Escribir formulas AA:AR y `AS` cuando aplique.
14. Subir archivo actualizado via Graph API.
15. Acumular resultado para correo final.
16. Al terminar todos los clientes, enviar correo resumen y escribir log final.

## Restricciones de negocio y datos
- El archivo descargado del WMS puede repetirse con el mismo nombre. Moverlo inmediatamente despues de descargar.
- El replace en SharePoint es solo del mes actual.
- Mantener el enfoque historico acumulado del archivo de cliente.
- El correo final debe incluir tabla por cliente con estado, filas nuevas, filas reemplazadas y advertencias.
- Las advertencias por estados pendientes > 7 dias no detienen el proceso.
- Derco es cliente de alto volumen: tratarlo como caso pesado.
- PUDAHUEL UNITARIO aplica especialmente a Runo SPA.

## Validaciones minimas despues de cada cambio
- Revisar sintaxis.
- Confirmar que se sigue usando `py`.
- Confirmar que `.env`, `.bat`, rutas Windows y Graph API siguen intactos.
- Confirmar que no se rompio la logica de:
  - `active=False`
  - `0 filas`
  - retry de Graph API
  - `Corte`
  - hoja `base` intacta
  - hoja `seguimiento de pedidos`
- Indicar exactamente que archivos se tocaron y por que.

## Seguridad
- Nunca imprimir secretos.
- Nunca cambiar credenciales.
- No habilitar accesos extra fuera de la necesidad real del flujo.
