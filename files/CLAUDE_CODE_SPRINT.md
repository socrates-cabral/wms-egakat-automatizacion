# CLAUDE CODE — Sprint 1: App Streamlit Chiquito Finanzas
**Fecha:** Mar-2026
**Responsable sesión:** Sócrates Cabral
**Directorio de trabajo:** `C:\ClaudeWork\chiquito_financiero\`
**Comando Python:** `py` (Python 3.14 64-bit en este equipo)

---

## CONTEXTO DEL PROYECTO

Estamos construyendo una herramienta de gestión financiera para el negocio de muebles de la hermana de Sócrates (operador conocido como "Chiquito"), ubicado en Santiago RM, Chile.

Ya existe:
- `ChiquitoFinanzas.html` — app standalone HTML/JS (funciona offline, sin instalación)
- `Diagnostico_Financiero_Chiquito.xlsx` — análisis Excel con 6 hojas
- `MEMORY.md` — documentación completa del proyecto (léela antes de empezar)

Lo que hay que construir en este sprint es la **versión Python/Streamlit** que se conecta al Excel original y se actualiza sola cada mes.

---

## TAREA COMPLETA — APP STREAMLIT

### Estructura de archivos a crear:

```
C:\ClaudeWork\chiquito_financiero\
├── app\
│   ├── main.py              ← Streamlit app principal (CREAR)
│   ├── data_loader.py       ← Lee el Excel automáticamente (CREAR)
│   ├── calculators.py       ← Lógica financiera: PE, simulador, BCI (CREAR)
│   ├── charts.py            ← Gráficos con Plotly (CREAR)
│   ├── pdf_report.py        ← Generador de reporte PDF mensual (CREAR)
│   └── requirements.txt     ← Dependencias (CREAR)
├── ChiquitoFinanzas.html
├── Diagnostico_Financiero_Chiquito.xlsx
├── MEMORY.md
└── CLAUDE_CODE_SPRINT.md    ← este archivo
```

---

## PASO 1 — requirements.txt

```
streamlit>=1.32.0
pandas>=2.2.0
openpyxl>=3.1.2
plotly>=5.20.0
fpdf2>=2.7.9
python-dotenv>=1.0.0
watchdog>=4.0.0
```

Instalar con:
```bash
py -m pip install -r app\requirements.txt --break-system-packages
```

---

## PASO 2 — data_loader.py

Este módulo lee el Excel del negocio. El archivo original se llama `Chiquito_Act_10_02.xlsx` (o similar) y puede estar en una carpeta OneDrive sincronizada.

### Configuración de ruta (archivo `.env` en `C:\ClaudeWork\chiquito_financiero\`):
```
EXCEL_PATH=C:\Users\Socrates Cabral\OneDrive\chiquito_financiero\Chiquito_Act_10_02.xlsx
```

### Lógica de `data_loader.py`:

```python
# data_loader.py
import pandas as pd
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

EXCEL_PATH = os.getenv('EXCEL_PATH', r'C:\ClaudeWork\chiquito_financiero\Chiquito_Act_10_02.xlsx')

# Hojas que contienen el libro de caja
CAJA_SHEETS = ['Cajas', 'Cajas_2026']

# Mapeo de columnas del libro de caja (basado en análisis previo)
# Ingresos: col A=fecha, B=mes, C=descripción, D=monto
# Gastos:   col J=fecha, K=mes, L=descripción, M=monto

def load_caja() -> pd.DataFrame:
    """Lee todas las hojas de Cajas y retorna DataFrame unificado."""
    ...

def load_deuda() -> pd.DataFrame:
    """Lee hoja 'Deuda_2026 actual' y retorna estructura de deudas."""
    ...

def get_monthly_summary() -> pd.DataFrame:
    """Agrupa por mes: total ingresos, gastos, resultado."""
    ...

def get_last_update() -> str:
    """Retorna fecha de última modificación del Excel."""
    ...
```

**IMPORTANTE:** Las hojas de caja tienen esta estructura (verificada en el análisis):
- **Ingresos** (lado izquierdo): columna A=fecha, B=mes (nombre), C=descripción, D=monto numérico
- **Gastos** (lado derecho): columna J=fecha, K=mes (nombre), L=descripción, M=monto numérico
- Hay filas de encabezado y totales que deben filtrarse (ignorar filas donde mes no sea string o monto no sea numérico)

---

## PASO 3 — calculators.py

```python
# calculators.py

COSTOS_FIJOS_BASE = {
    'alquiler_taller': 700_000,
    'telefono': 45_000,
    'internet': 18_000,
    'luz_agua': 55_000,
    'mercadopago': 36_000,
    'gasolina': 100_000,
    'gastos_varios': 40_000,
}

DEUDAS_DEFAULT = [
    {'acreedor': 'Banco Itau (crédito 36m)',   'saldo': 5_749_547, 'cuota': 154_028, 'tasa': 2.8, 'tipo': 'banco'},
    {'acreedor': 'Banco Estado (crédito 36m)', 'saldo': 5_600_000, 'cuota': 174_437, 'tasa': 3.1, 'tipo': 'banco'},
    {'acreedor': 'Banco Santander (TC)',        'saldo': 3_760_935, 'cuota': 109_000, 'tasa': 2.8, 'tipo': 'tc'},
    {'acreedor': 'CMR Falabella (TC retail)',   'saldo': 1_607_443, 'cuota':  80_000, 'tasa': 3.3, 'tipo': 'tc'},
    {'acreedor': 'Líneas crédito (3 bancos)',   'saldo': 2_360_000, 'cuota':  71_660, 'tasa': 3.1, 'tipo': 'linea'},
    {'acreedor': 'Crédito automotriz Foton',   'saldo': 9_517_195, 'cuota': 264_366, 'tasa': 1.2, 'tipo': 'auto'},
    {'acreedor': 'Seguro camión Foton',        'saldo':         0, 'cuota':  65_412, 'tasa': 0.0, 'tipo': 'seguro'},
    {'acreedor': 'Hermana (dólares)',           'saldo': 1_050_000, 'cuota':       0, 'tasa': 0.0, 'tipo': 'familiar'},
]

def calc_punto_equilibrio(alquiler, cuota_tc, margen_bruto_pct) -> float:
    """Retorna monto mensual de ventas necesario para cubrir todos los costos."""
    ...

def calc_cuota_frances(monto, tasa_mensual, n_cuotas) -> float:
    """Sistema francés (cuota fija). Usado para crédito BCI."""
    # fórmula: C = P * i / (1 - (1+i)^-n)
    ...

def calc_amortizacion(monto, tasa_mensual, n_cuotas) -> list[dict]:
    """Retorna tabla de amortización mes a mes."""
    # cada fila: {mes, cuota, interes, principal, saldo}
    ...

def calc_inyeccion_capital(monto_bci, aporte_familiar, tasa_bci, cuotas_bci, deudas) -> dict:
    """
    Calcula el impacto de inyectar capital en la deuda.
    Estrategia: pagar de mayor a menor tasa.
    Retorna: {
        'asignaciones': [...],
        'cuotas_liberadas': float,
        'intereses_eliminados_mes': float,
        'cuota_bci': float,
        'impacto_neto_cuotas': float,
        'ahorro_neto_intereses_mes': float,
        'ahorro_total_periodo': float,
        'arbitraje_tasa': float,
        'acuerdo_hermana': 'Pagar cuota BCI de ${cuota_bci:,.0f}/mes (sin interés adicional)'
    }
    """
    ...
    # IMPORTANTE: el préstamo de Sócrates a su hermana NO tiene interés
    # La hermana solo debe devolver la cuota exacta del BCI: ${cuota_bci}/mes
    # No se cobra ningún interés adicional — es apoyo familiar
    ...

def calc_meses_hasta_quiebra(resultado_mensual, capital_trabajo=500_000) -> int | None:
    """Si resultado < 0, cuántos meses dura el capital de trabajo."""
    ...
```

---

## PASO 4 — main.py (Streamlit)

### Estructura de páginas (sidebar):

```
CHIQUITO FINANZAS
─────────────────
Principal
  📊 Dashboard
  🎛 Simulador

Datos
  💰 Libro de Caja
  💳 Deuda

Gestión
  ✅ Plan de Acción
  💉 Inyección Capital

Configuración
  ⚙️ Ajustes
```

### Dashboard (`main.py`):
- **KPI cards:** Ingreso prom/mes, Gasto prom/mes, Deuda total, Cuotas/mes, Resultado neto, % PE alcanzado
- **Gráfico barras:** Ingresos vs Gastos por mes (Plotly bar chart con colores verde/rojo)
- **Gráfico dona:** Composición de costos fijos
- **Alerta roja:** si resultado neto < 0
- **Alerta naranja:** si % PE < 70%
- **Indicador de última actualización** del Excel

### Simulador:
- Sliders: ventas objetivo, alquiler, cuota TCs, margen bruto %
- Checkboxes: "Vender Foton", "Separar gastos personales"
- **Escenarios rápidos:** botones que precargan valores (actual / optimista / renegociado / equilibrio)
- Proyección 12 meses con selectbox de crecimiento (0% / 2% / 5% / 10%)
- Resultado en tiempo real con color verde/rojo

### Inyección Capital:
- Inputs: aporte familiar, monto BCI, cuotas, tasa mensual
- Tabla de asignación de capital por prioridad de tasa
- Tabla de amortización del crédito BCI
- KPI: arbitraje de tasa, ahorro total, impacto neto en cuotas
- **Nota destacada:** *"Acuerdo familiar: la hermana paga la cuota BCI de ${cuota}/mes. Sin interés adicional — es apoyo sin costo para ella."*
- Lista de condiciones con checkbox de validación

### Libro de Caja:
- Filtro por mes (multiselect)
- Filtro por tipo (ingreso / gasto)
- Tabla paginada con búsqueda
- Gráfico de evolución mensual
- Botón "Actualizar desde Excel" (re-lee el archivo)

### Ajustes (`config`):
- Campo para cambiar la ruta del Excel
- Umbrales de alerta (saldo mínimo, % PE mínimo)
- Guardar en `.env` local

---

## PASO 5 — pdf_report.py

Genera un PDF de 2 páginas con:
1. Resumen ejecutivo del mes (KPIs, resultado, % PE)
2. Tabla de flujo de caja del mes
3. Estado de deudas actualizado
4. Semáforo de salud financiera (verde/amarillo/rojo)

```python
# Usar fpdf2
from fpdf import FPDF

def generar_reporte_mensual(mes: str, datos: dict) -> bytes:
    """Retorna PDF en bytes para descarga desde Streamlit."""
    ...
```

---

## PASO 6 — Lanzar la app

```bash
cd C:\ClaudeWork\chiquito_financiero
py -m streamlit run app\main.py
```

La app abre en `http://localhost:8501`

---

## REGLAS DE IMPLEMENTACIÓN

1. **`py` siempre** — nunca `python` ni `python3` en este equipo
2. **`--break-system-packages`** en todos los pip install
3. **Credenciales en `.env`** — nunca hardcodeadas
4. **Sin dependencias de internet** — debe funcionar offline (excepto la carga inicial de Streamlit)
5. **Manejo de errores** — si el Excel no existe o está abierto en Excel, mostrar mensaje claro en la UI y usar datos de ejemplo
6. **Comentarios en español** — el código es para Sócrates, comentar en español
7. **Colores consistentes con la app HTML:** verde=#3fb950, rojo=#f85149, ámbar=#d29922, azul=#58a6ff
8. **Fondo oscuro:** usar `st.set_page_config(page_icon="📊", layout="wide")` + CSS personalizado para fondo oscuro similar al HTML

---

## DATOS DE REFERENCIA CRÍTICOS

### Estructura Excel (verificada en análisis):
- Hoja `Cajas` → Nov-Dic 2025
- Hoja `Cajas_2026` → Ene-Mar 2026 (y meses futuros que se van agregando)
- Hoja `Deuda_2026 actual` → saldos más recientes de deuda

### Valores actuales para usar como defaults si el Excel falla:
```python
MONTHLY_DEFAULT = [
    {'mes': 'Nov-25', 'ing': 1_721_170, 'gas': 2_025_470},
    {'mes': 'Dic-25', 'ing': 3_024_913, 'gas': 2_715_420},
    {'mes': 'Ene-26', 'ing': 1_625_820, 'gas': 1_601_683},
    {'mes': 'Feb-26', 'ing': 1_964_928, 'gas': 1_617_387},
    {'mes': 'Mar-26', 'ing': 2_400_000, 'gas': 2_200_000},
]
```

### Crédito BCI (datos reales de simulación Mar-2026):
```python
BCI_CREDITO = {
    'monto': 10_000_000,
    'cuotas': 18,
    'tasa_mensual': 0.0143,
    'cuota': 648_805,
    'cae': 0.2024,
    'ctc': 11_678_482,
    'primera_cuota': '15-Abr-2026',
    'seguro_desgravamen': True,
    'nota_familiar': 'La hermana paga la cuota exacta del BCI al hermano. Sin interés adicional.'
}
```

---

## ORDEN DE EJECUCIÓN PARA CLAUDE CODE

```
1. Leer MEMORY.md completo
2. Crear estructura de carpetas: app\
3. Crear requirements.txt → instalar
4. Crear calculators.py → testear funciones con assert
5. Crear data_loader.py → testear con el Excel real
6. Crear charts.py → funciones Plotly reutilizables
7. Crear main.py → página por página
8. Crear pdf_report.py → probar generación
9. Ejecutar: py -m streamlit run app\main.py
10. Verificar que todos los módulos cargan sin error
```

---

## ERRORES CONOCIDOS A EVITAR

| Error | Causa | Solución |
|-------|-------|----------|
| `py: command not found` | Usar `python` en vez de `py` | Siempre `py` |
| Excel bloqueado | Archivo abierto en Excel al mismo tiempo | Usar `openpyxl` con `read_only=True` |
| Columnas NaN en caja | Filas de totales o encabezados | Filtrar donde `mes` sea string válido y `monto` > 0 |
| Streamlit no recarga | Cambios en módulos importados | Usar `st.cache_data` con `ttl=300` |
| PDF no descarga | fpdf2 en modo bytes | Retornar `bytes(pdf.output())` |

---

*Generado por Claude (Kai) — Mar-2026*
*Actualizar este archivo al final de cada sprint con los cambios realizados*
