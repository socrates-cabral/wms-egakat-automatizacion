# Correcciones DAX — NNSS Bodega (OTIF / OnTime / InFull / FR)

## Validación contra WMS (Derco, Mayo 2026)

| Métrica | WMS Reporte | BI actual (Todas) | BI corregido (lógica) |
|---|---|---|---|
| Total OP | 742 pedidos | 1,673 líneas | **742 pedidos** ✅ |
| On Time | 99.1% | 84.0% | ~99.1% |
| In Full | 97.0% | 98.1% | **97.0%** ✅ |
| OTIF | 96.5% | 82.7% | ~96.5% |

Los 742 pedidos y el 97.0% In Full a nivel orden **reproducen exactamente el WMS** al aplicar el filtro base.

---

## Principio base (aplica a TODAS las medidas de OTIF/OnTime/InFull)

```
Filtro: NOT(ISBLANK(Consulta_FR[Fecha y hora de Remisión]))
```

**Por qué:** En la fuente de datos (Excel FillRate):
- Estado "Con Salida" → siempre tiene Fecha de Remisión (0 nulls)
- Estado "Preparados" → SIEMPRE null (100%)
- Estado "En Preparacion" → SIEMPRE null (100%)

El filtro por Remisión excluye automáticamente todos los pendientes sin importar el Estado Pedido.

**Granularidad:** DISTINCTCOUNT(**Nro Pedido**), no DISTINCTCOUNT(Key).  
Key = Empresa|Nro Aplica = nivel línea SKU → da 1,468 líneas en Mayo vs 742 pedidos.

---

## Total_OP2 — CORREGIDO

**Antes:**
```dax
Total_OP2 =
DISTINCTCOUNT( Consulta_FR[Key] )
```

**Después:**
```dax
Total_OP2 =
CALCULATE(
    DISTINCTCOUNT( Consulta_FR[Nro Pedido] );
    NOT( ISBLANK( Consulta_FR[Fecha y hora de Remisión] ) )
)
```

> Este es el denominador compartido. Corrección aquí impacta automáticamente InFull %, OnTime % y OTIF %.

---

## OP_OTIF — CORREGIDO

Un pedido es OTIF solo si **todas** sus líneas tienen ambas columnas = "SI".  
(22 pedidos Derco Mayo tienen líneas mixtas en InFull → cuentan diferente a nivel línea vs orden.)

**Antes:**
```dax
OP_OTIF =
CALCULATE(
    DISTINCTCOUNT( Consulta_FR[Key] );
    Consulta_FR[Entregado a tiempo?] = "SI";
    Consulta_FR[Entregado completo y sin daños?] = "SI"
)
```

**Después:**
```dax
OP_OTIF =
COUNTROWS(
    FILTER(
        ADDCOLUMNS(
            CALCULATETABLE(
                VALUES( Consulta_FR[Nro Pedido] );
                NOT( ISBLANK( Consulta_FR[Fecha y hora de Remisión] ) )
            );
            "LineasMalas";
            CALCULATE(
                COUNTROWS( Consulta_FR );
                NOT( ISBLANK( Consulta_FR[Fecha y hora de Remisión] ) );
                NOT(
                    Consulta_FR[Entregado a tiempo?] = "SI"
                    && Consulta_FR[Entregado completo y sin daños?] = "SI"
                )
            )
        );
        [LineasMalas] = 0
    )
)
```

**OTIF % — sin cambio de fórmula** (ya usa DIVIDE de los dos anteriores):
```dax
OTIF % =
DIVIDE( [OP_OTIF]; [Total_OP2]; BLANK() )
```

---

## OP_OnTime — CORREGIDO

OnTime es orden-nivel (confirmado: todas las líneas del mismo Nro Pedido comparten la misma Fecha de Remisión → mismo valor On Time). No requiere ADDCOLUMNS.

**Antes:**
```dax
OP_OnTime =
CALCULATE(
    DISTINCTCOUNT( Consulta_FR[Key] );
    Consulta_FR[Entregado a tiempo?] = "SI"
)
```

**Después:**
```dax
OP_OnTime =
CALCULATE(
    DISTINCTCOUNT( Consulta_FR[Nro Pedido] );
    NOT( ISBLANK( Consulta_FR[Fecha y hora de Remisión] ) );
    Consulta_FR[Entregado a tiempo?] = "SI"
)
```

**OnTime % — sin cambio de fórmula:**
```dax
OnTime % =
DIVIDE( [OP_OnTime]; [Total_OP2]; BLANK() )
```

---

## OP_InFull — CORREGIDO

InFull **sí** requiere lógica a nivel orden: 22 pedidos Derco Mayo tienen algunas líneas SI y otras NO.  
A nivel línea: 98.4% | A nivel orden (correcto): **97.0%** ✅ (match exacto WMS).

**Antes:**
```dax
OP_InFull =
CALCULATE(
    DISTINCTCOUNT( Consulta_FR[Key] );
    Consulta_FR[Entregado completo y sin daños?] = "SI"
)
```

**Después:**
```dax
OP_InFull =
COUNTROWS(
    FILTER(
        ADDCOLUMNS(
            CALCULATETABLE(
                VALUES( Consulta_FR[Nro Pedido] );
                NOT( ISBLANK( Consulta_FR[Fecha y hora de Remisión] ) )
            );
            "LineasNOInFull";
            CALCULATE(
                COUNTROWS( Consulta_FR );
                NOT( ISBLANK( Consulta_FR[Fecha y hora de Remisión] ) );
                Consulta_FR[Entregado completo y sin daños?] <> "SI"
            )
        );
        [LineasNOInFull] = 0
    )
)
```

**InFull % — sin cambio de fórmula:**
```dax
InFull % =
DIVIDE( [OP_InFull]; [Total_OP2]; BLANK() )
```

---

## FR_Ponderado — OK con nota menor

La lógica SWITCH es correcta:
- "En Preparacion" = 1 (diseño intencional: no penalizar órdenes en proceso)
- "Preparados/Con Salida/Remitido" = Preparada/Original
- "Despachado" = Despachada/Original

**Nota:** AVERAGEX da peso igual a cada Nro Aplica independiente de su volumen (una línea de 1 unidad pesa igual que una de 10,000). Si en algún momento se necesita una FR ponderada por volumen, cambiar `AVERAGEX(Tabla2; [FR])` por `DIVIDE(SUMX(Tabla2; [Prep]); SUMX(Tabla2; [Ori]))`.

**No requiere cambios por ahora.**

---

## FR_Bodega — CORREGIR (impacto crítico)

**Problema detectado en datos Mayo 2026:**

| | Valor |
|---|---|
| FR_Bodega con pendientes | **82.1%** ❌ |
| FR_Bodega sin pendientes | **99.6%** ✅ |
| Unidades pendientes (Ori sin despachar) | 29,337 de 166,206 = **17.7%** |

Los pedidos en "Preparados" y "En Preparacion" tienen Cantidad Despachada = 0 pero su Cantidad Original entra al denominador → hunde FR_Bodega de 99.6% a 82.1%.

**Antes:**
```dax
FR_Bodega =
VAR Apps =
    SUMMARIZE(
        Consulta_FR;
        Consulta_FR[Empresa];
        Consulta_FR[Nro Aplica]
    )
VAR Base =
    ADDCOLUMNS(
        Apps;
        "Ori";  CALCULATE( SUM( Consulta_FR[Cantidad Original] ) );
        "Desp"; CALCULATE( SUM( Consulta_FR[Cantidad Despachada] ) )
    )
RETURN
    DIVIDE(
        SUMX( Base; [Desp] );
        SUMX( Base; [Ori] );
        0
    )
```

**Después:**
```dax
FR_Bodega =
VAR Apps =
    CALCULATETABLE(
        SUMMARIZE(
            Consulta_FR;
            Consulta_FR[Empresa];
            Consulta_FR[Nro Aplica]
        );
        NOT( ISBLANK( Consulta_FR[Fecha y hora de Remisión] ) )
    )
VAR Base =
    ADDCOLUMNS(
        Apps;
        "Ori";  CALCULATE(
                    SUM( Consulta_FR[Cantidad Original] );
                    NOT( ISBLANK( Consulta_FR[Fecha y hora de Remisión] ) )
                );
        "Desp"; CALCULATE(
                    SUM( Consulta_FR[Cantidad Despachada] );
                    NOT( ISBLANK( Consulta_FR[Fecha y hora de Remisión] ) )
                )
    )
RETURN
    DIVIDE(
        SUMX( Base; [Desp] );
        SUMX( Base; [Ori] );
        0
    )
```

---

## Resumen de cambios

| Medida | Problema | Acción |
|---|---|---|
| `Total_OP2` | Cuenta líneas + incluye pendientes | **Corregir** |
| `OP_OTIF` | Nivel línea + pendientes | **Corregir** |
| `OP_OnTime` | Nivel línea + pendientes | **Corregir** |
| `OP_InFull` | Nivel línea + pendientes (22 pedidos mixtos) | **Corregir** |
| `FR_Ponderado` | AVERAGEX no pondera por volumen | Aceptable por ahora |
| `FR_Bodega` | Pendientes hunden FR: 82.1% vs 99.6% | **Corregir** |

**Orden recomendado de aplicación en Power BI:**
1. Corregir `Total_OP2` primero (denominador compartido)
2. Corregir `OP_OnTime` (más simple)
3. Corregir `OP_InFull`
4. Corregir `OP_OTIF`
5. Corregir `FR_Bodega`
