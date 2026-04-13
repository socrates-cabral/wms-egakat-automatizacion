# AGENTS.md

## Proposito del proyecto
Este proyecto implementa una automatizacion independiente para descargar el reporte de Productividad desde WMS EgaKat y guardarlo en la estructura historica real de carpetas locales.

## Contexto operativo obligatorio
- Entorno: Windows 10/11.
- Comando Python: usar siempre `py`.
- Instalacion de paquetes: usar siempre `py -m pip`.
- Launchers: usar `.bat`.
- Credenciales: leer siempre desde `.env`. Nunca hardcodear secretos.
- Carpeta actual de trabajo: `C:\ClaudeWork\Productividad_Automatizacion\`
- Destino oficial final: `SharePoint` en `DatosparaDashboard / Documentos compartidos / Productividad`
- OneDrive local solo se usa como referencia historica, no como destino oficial final.

## Estructura esperada del proyecto
- `productividad_descarga.py` = script principal
- `productividad_config.py` = configuracion central y catalogo historico
- `productividad_utils.py` = helpers de rango, validacion y logging
- `run_productividad.bat` = launcher
- `requirements_productividad.txt` = dependencias
- `logs\` = salida de logs y staging de descargas

## Reglas duras que no se deben romper
- La lista de empresas no sale del dropdown WMS; sale del historico real de archivos.
- No inventar aliases nuevos sin respaldo historico.
- Respetar exactamente el patron `...\Productividad\CD <CD>\2026\MM. Mes\Mov<AliasEmpresa>.xlsx`.
- No agregar fecha al nombre del archivo.
- `MovRuno` se descarga desde `PUDAHUEL UNITARIO`, pero se guarda bajo `CD PUDAHUEL`.
- `MovMascota Latina` en `PUDAHUEL` queda fuera del alcance operativo actual (`active=False`).
- `WILD FOODS` y `THE NOT COMPANY` quedan inactivos por instruccion explicita.
- Si el Excel descargado no coincide con alias esperado, CD esperado o empresa esperada:
  - marcar error critico
  - no sobrescribir archivo oficial
  - dejar evidencia en log
  - incluir el caso en el resumen final
- Tratar archivos sin movimientos como validos/vacios, no como fallo.
- No improvisar selectores ni labels WMS no confirmados.

## Regla oficial de rango
- Mes en curso:
  - Desde: primer dia del mes a las `08:00:00`
  - Hasta: dia de ejecucion a las `06:00:00`
- Mes cerrado:
  - Desde: primer dia del mes a las `08:00:00`
  - Hasta: primer dia del mes siguiente a las `06:00:00`

## Validaciones post-descarga
- Hoja valida: `Reporte de Movimientos` o `Hoja1`
- Encabezado historico esperado en fila 9
- CD interno consistente
- Empresa interna consistente
- Alias consistente cuando pueda inferirse desde el contenido
- No sobrescribir oficial si hay inconsistencia critica
- Backup remoto obligatorio antes de cualquier overwrite en SharePoint.
- Verificacion post-subida obligatoria con criterio semantico/estructural, no binario estricto.

## Validaciones pendientes de runtime
- Selector exacto de menu/ruta del reporte de Productividad en WMS
- Textos exactos de dropdown de empresa y deposito por cliente
- Boton de exportacion real del reporte
- Comportamiento real de descarga del navegador
- Confirmacion operativa de si el campo visible del reporte expone deposito en forma util para validacion dura

