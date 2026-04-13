# MEMORY.md — Productividad_Automatizacion
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
