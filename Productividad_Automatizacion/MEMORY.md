# MEMORY.md â€” Productividad_Automatizacion
_Contexto de sesion para futuras iteraciones del modulo._

---

## 1. DECISIONES CONFIRMADAS

- El modulo vive en `C:\ClaudeWork\Productividad_Automatizacion\`.
- La estructura del proyecto debe ser simple y alineada al ecosistema de `run_todos.py` y `fillrate_descarga.py`.
- La hora operativa oficial de inicio es `08:00:00`.
- La hora operativa oficial de cierre es `06:00:00`.
- La lista de empresas sale del historico real de archivos, no del dropdown WMS.
- No se agregan fechas al nombre del archivo.
- No se inventan aliases nuevos sin respaldo historico.

---

## 2. PATRON HISTORICO DE DESTINO

```
...\Productividad\CD <CD>\2026\MM. Mes\Mov<AliasEmpresa>.xlsx
```

Ejemplos confirmados:
- `CD PUDAHUEL\2026\03. Marzo\MovRuno.xlsx`
- `CD QUILICURA\2026\02. Febrero\MovDerco.xlsx`

---

## 3. CATALOGO INICIAL CONFIRMADO

### CD PUDAHUEL
- MovBarentz
- MovBuraschi
- MovCepas Chile
- MovCollico
- MovDelibest
- MovMascota Latina
- MovRuno
- Movtresmontes
- MovUnilever
- Movintime
- MovWildFoods Moderno = inactive
- MovwildFoods Tradicional = inactive
- MovNotCompany = inactive

### CD QUILICURA
- MovABInbev
- MovBha
- MovDaikin
- MovDerco
- MovMascota
- MovPochteca

---

## 4. REGLA DE RANGO OFICIAL

- Mes en curso:
  - Desde: primer dia del mes a las `08:00:00`
  - Hasta: dia de ejecucion a las `06:00:00`
- Mes cerrado:
  - Desde: primer dia del mes a las `08:00:00`
  - Hasta: primer dia del mes siguiente a las `06:00:00`

La hora debe quedar centralizada en `productividad_config.py`.

---

## 5. CASOS ESPECIALES

- `MovRuno`:
  - deposito WMS origen = `PUDAHUEL UNITARIO`
  - carpeta destino historica = `CD PUDAHUEL`
- `WILD FOODS`:
  - mantener en catalogo historico
  - `active=False`
- `THE NOT COMPANY`:
  - mantener en catalogo historico
  - `active=False`

---

## 6. HALLAZGOS DE INSPECCION IMPORTANTES

- Los archivos historicos inspeccionados fueron `xlsx`.
- Hoja habitual: `Reporte de Movimientos`.
- Excepcion observada: algunos `MovDerco.xlsx` usan `Hoja1`.
- El encabezado historico estable aparece en fila 9.
- Hay archivos validos sin movimientos; deben tratarse como `validos/vacios`.
- Se observo un riesgo real de inconsistencia:
  - `CD QUILICURA\2026\04. Abril\MovDerco.xlsx`
  - el nombre del archivo indica Derco
  - el contenido interno observado mostro `CERVECERIA ABI`
  - este caso justifica la validacion critica antes de sobrescribir

---

## 7. VALIDACIONES PENDIENTES DE RUNTIME

- Ruta exacta del menu WMS para Productividad
- Selectores reales de login, deposito, empresa y exportacion
- Confirmacion del label exacto del reporte en el menu
- Confirmacion de si el valor interno del libro en `A5` sirve como validacion confiable del deposito origen
- Comportamiento real del archivo descargado desde navegador
- Politica exacta de staging temporal antes de mover al archivo oficial

---

## 8. CRITERIO DE SEGURIDAD OPERATIVA

- No sobrescribir el archivo oficial si falla validacion critica.
- Dejar siempre evidencia en log cuando haya inconsistencia.
- No asumir que el contenido interno del libro siempre coincide con el alias historico.
- No automatizar navegacion WMS hasta confirmar selectores y labels reales.

---

## 9. ARQUITECTURA OFICIAL DE DESTINO

- `staging local` se mantiene como zona de trabajo.
- `staging local` se usa para:
  - descarga
  - validacion
  - normalizacion
  - comparacion
  - cuarentena si aplica
- El `historico oficial final` ya no debe considerarse OneDrive local.
- El destino oficial final debe ser `SharePoint`, en el sitio `DatosparaDashboard`, bajo:

```text
Documentos compartidos/Productividad/<CD>/<ano>/<MM. Mes>/Mov<AliasEmpresa>.xlsx
```

Ejemplos oficiales de referencia:
- `DatosparaDashboard/Documentos compartidos/Productividad/CD QUILICURA/2026/03. Marzo/MovDaikin.xlsx`
- `DatosparaDashboard/Documentos compartidos/Productividad/CD PUDAHUEL/2026/03. Marzo/MovBarentz.xlsx`

---

## 10. ESTADO ACTUAL DEL MODULO

1. La escritura oficial controlada a SharePoint ya quedo implementada y validada.
2. El staging local se mantiene como zona de trabajo para:
   - descarga
   - validacion
   - normalizacion
   - comparacion
   - cuarentena si aplica
3. Todos los clientes activos quedaron cerrados:
   - Quilicura livianos
   - Pudahuel estandar
   - Runo
   - Derco heavy/chunked
4. `MovMascota Latina` en `PUDAHUEL` quedo fuera de alcance operativo (`active=False`).
5. El historico oficial final vive en SharePoint; OneDrive local no se usa como destino oficial.
6. La migracion final al root oficial ya fue ejecutada; staging queda como respaldo operativo/historico durante la estabilizacion.

---

## 11. CONTROLES DE OVERWRITE EN SHAREPOINT

- Antes de un overwrite oficial en SharePoint, el modulo debe crear un backup remoto auditable.
- Politica actual:
  - si el archivo remoto existe
  - descargar la version remota actual
  - subir snapshot a:

```text
Productividad/_backups/<CD>/<ano>/<MM. Mes>/<Alias>/YYYYMMDD_HHMMSS_Mov<Alias>.xlsx
```

- La verificacion post-subida ya no se limita a verificar existencia del archivo.
- Debe validar al menos:
  - tamano remoto
  - fecha/hora de modificacion remota
  - relectura del archivo remoto a staging
  - validacion basica del remoto
  - validacion estructural del remoto
  - comparacion exacta del remoto contra layout historico
  - comparacion deterministica del workbook remoto contra el candidato local

- Si el binario remoto difiere del candidato, pero la huella semantica del workbook coincide:
  - dejar advertencia en log
  - aceptar la escritura como valida

- Si la huella semantica del remoto no coincide con el candidato:
  - marcar fallo critico post-subida
  - no considerar la escritura como confirmada

- DERCO sigue fuera de esta etapa.

---

## 12. PRODUCCION ACOTADA CLIENTES LIVIANOS

- Produccion acotada habilitada solo para:
  - `daikin`
  - `pochteca`
  - `barentz`

- Reglas:
  - staging local se mantiene
  - SharePoint sigue siendo el unico destino oficial
  - backup remoto obligatorio antes de overwrite
  - verificacion post-subida obligatoria
  - si un cliente falla gating o publicacion, no bloquea a los otros en el lote
  - el lote debe dejar resumen final por cliente

- Esta etapa ya fue superada; DERCO quedo cerrado despues con flujo heavy/chunked.

---

## 13. CIERRE DERCO

- `MovDerco` se ejecuto como `heavy_client=True`.
- Chunking aplicado y validado:
  - `01/04/2026 08:00:00 -> 08/04/2026 06:00:00`
  - `08/04/2026 06:00:00 -> 11/04/2026 06:00:00`
- Cobertura exacta del rango operativo: sin huecos ni solapes.
- No fue necesaria subdivision adicional.
- Consolidacion final staging:
  - `MovDerco_20260411_115200.xlsx`
- Commit individual SharePoint confirmado con:
  - backup remoto previo
  - verificacion post-subida
  - huella semantica remota igual al candidato local
  - aceptacion correcta aunque el binario remoto no sea identico

---

## 14. CORREO FINAL DEL MODULO

- Se dejo integrado un correo final ejecutivo para Productividad.
- El correo genera:
  - preview HTML en `logs/`
  - resumen JSON en `logs/`
  - envio opcional via Graph API con fallback Outlook Desktop
- El correo resume:
  - clientes activos cerrados
  - destino oficial SharePoint
  - staging local separado
  - cierre DERCO heavy


