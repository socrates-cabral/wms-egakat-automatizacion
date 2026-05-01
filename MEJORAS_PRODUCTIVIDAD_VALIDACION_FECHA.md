# Mejoras al módulo Productividad — Validación de columna Fecha

## Problema detectado (28 abril 2026)

El WMS envió HTML con columna "Fecha" vacía para 11,049 filas en DERCO y 2 filas en 7 clientes más. Al hacer merge con pandas, las filas quedaron con `Fecha=NaN`, generando archivos corruptos en SharePoint.

## Causa raíz

`productividad_diario.py:_parse_wms_html_to_df()` crea el DataFrame desde el HTML del WMS sin validar que las columnas críticas (Fecha, Hora, Comprobante) tengan valores válidos.

## Mejora 1: Validación post-parsing (CRÍTICA)

**Archivo**: `productividad_diario.py`  
**Función**: `_parse_wms_html_to_df()`  
**Línea**: Después de línea 458 (creación del DataFrame)

```python
# VALIDACIÓN CRÍTICA: Verificar que columnas esenciales no estén vacías
if not df.empty:
    if "Fecha" not in df.columns or "Hora" not in df.columns:
        raise RuntimeError(
            "El chunk WMS no contiene las columnas Fecha/Hora esperadas. "
            "HTML corrupto o cambio de formato WMS."
        )

    # Contar cuántas filas tienen Fecha vacía
    if "Fecha" in df.columns:
        vacias_fecha = df["Fecha"].isna().sum()
        if vacias_fecha > 0:
            pct = (vacias_fecha / len(df)) * 100
            if pct > 5.0:  # Si >5% de filas tienen Fecha vacía, es un error crítico
                raise RuntimeError(
                    f"El chunk WMS tiene {vacias_fecha}/{len(df)} filas ({pct:.1f}%) "
                    f"con columna Fecha vacía. Descarga rechazada — revisar WMS."
                )
            else:
                # Si <5%, loguear advertencia pero permitir continuar
                log(
                    f"[WARN] Chunk WMS: {vacias_fecha}/{len(df)} filas ({pct:.1f}%) "
                    f"con Fecha vacía. Se rellenará con fecha de checkpoint.",
                    log_path
                )
                # Rellenar filas vacías con fecha del checkpoint
                fecha_checkpoint = from_dt.strftime("%d/%m/%Y")
                df.loc[df["Fecha"].isna(), "Fecha"] = fecha_checkpoint

log(f"[OK] Chunk WMS: {len(df)} filas | Fecha válida en todas las filas.", log_path)
```

**Rationale**:
- Si >5% de filas tienen Fecha vacía → rechazar el chunk (error WMS)
- Si <5% → rellenar con fecha del checkpoint y continuar
- Evita que datos corruptos lleguen a SharePoint

## Mejora 2: Validación pre-merge

**Archivo**: `productividad_diario.py`  
**Función**: `_process_client()`  
**Línea**: Antes de llamar `_dedup_merge()` (línea ~800)

```python
# Validar que df_new_month tenga Comprobante numérico válido
if not df_new_month.empty and "Comprobante" in df_new_month.columns:
    comp_numericos = pd.to_numeric(df_new_month["Comprobante"], errors="coerce").notna().sum()
    if comp_numericos == 0:
        log(
            f"[CRITICO] Chunk WMS no tiene comprobantes numéricos válidos. "
            f"Saltando merge para evitar corrupción.",
            log_path
        )
        continue
```

## Mejora 3: Alerta por email si hay validación fallida

**Archivo**: `productividad_diario.py`  
**Función**: `main()` o `_process_client()`

Cuando se rechaza un chunk por validación fallida:
1. Loguear con marcador `[VALIDACION_FALLIDA]`
2. Agregar al resumen de email un apartado "Alertas de validación"
3. Incluir detalles: cliente, filas afectadas, porcentaje

## Mejora 4: Checkpoint granular por fecha-hora

Actualmente el checkpoint guarda solo la fecha. Si el script falla a mitad de día y se re-ejecuta, puede duplicar datos de ese día.

**Propuesta**: Guardar `checkpoint["derco"] = "2026-04-28 14:30"` en lugar de solo `"2026-04-28"`.

**Beneficio**: Ventana más precisa en re-ejecuciones.

## Implementación sugerida

1. Aplicar **Mejora 1** (validación post-parsing) — PRIORIDAD ALTA
2. Aplicar **Mejora 2** (validación pre-merge) — PRIORIDAD MEDIA
3. Aplicar **Mejora 3** (alertas email) — PRIORIDAD MEDIA
4. **Mejora 4** (checkpoint granular) — considerar para futuro

## Testing

Casos de prueba:
1. HTML del WMS con Fecha vacía en >5% filas → script debe rechazar chunk
2. HTML del WMS con Fecha vacía en <5% filas → script rellena y continúa
3. HTML sin columna Fecha → script rechaza con error claro
4. Re-ejecución tras fallo → no duplica datos del día parcialmente procesado

## Notas adicionales

- El problema del 28 de abril afectó 8 de 17 clientes → sugiere que fue un problema transitorio del WMS, no del código
- Reparación manual completada: 11,063 filas rellenadas con fecha 27/04/2026
- Todos los archivos verificados y corregidos en SharePoint
