# MEMORY.md — FillRate_Automatizacion
_Contexto de sesion para Claude Code. Leer completo antes de escribir codigo._

---

## 1. CONTEXTO GENERAL

Modulo independiente de descarga automatica del reporte "Consulta de Fill Rate" desde el WMS EgaKat.
Forma parte del ecosistema WMS Egakat pero en carpeta separada: `C:\ClaudeWork\FillRate_Automatizacion\`

**Stack obligatorio:**
- Windows 10/11, comando `py` (NUNCA `python`)
- `py -m pip install --break-system-packages` para instalar paquetes
- Launchers: `.bat` (AppLocker bloquea `.ps1` y `.vbs`)
- Credenciales en `.env`
- Task Scheduler configurado por GUI (no `schtasks` CLI por espacios en username)

**Repositorio:** `socrates-cabral/ClaudeWork-` (branch main)
**Graph API:** ya configurada en WMS_Automatizacion; reutilizar mismas credenciales `.env`

**Excepcion aprobada:** este modulo usara Playwright en vez de Selenium para priorizar compatibilidad con el ecosistema WMS vivo.

---

## 2. ESTRUCTURA DE ARCHIVOS

```
C:\ClaudeWork\FillRate_Automatizacion\
├── fillrate_descarga.py
├── fillrate_config.py
├── fillrate_utils.py
├── run_fillrate.bat
├── MEMORY.md
├── requirements_fillrate.txt
└── logs\
    └── fillrate_YYYY-MM-DD.log
```

---

## 3. VARIABLES DE ENTORNO (.env)

El modulo no debe leer ni exponer manualmente secretos en respuestas.
Se trabajara contra este contrato de variables:

```
WMS_USUARIO
WMS_CLAVE
TENANT_ID
CLIENT_ID
CLIENT_SECRET
SHAREPOINT_SITE_ID
SHAREPOINT_DRIVE_ID
EMAIL_DESTINO
EMAIL_CC
SHAREPOINT_USER
ONEDRIVE_PATH
```

Compatibilidad hacia atras permitida con el ecosistema WMS existente:

```
Application_(client)_ID
Directory_(tenant)_ID
Client_Secret_Value
```

---

## 4. CONFIGURACION DE CLIENTES

La configuracion de clientes vive en `fillrate_config.py`.
Los nombres `empresa_wms` deben coincidir con el texto visible del dropdown en runtime.

Base SharePoint esperada:

```python
SHAREPOINT_BASE_PATH = "NNSS/NNSS Operacional"
```

Clientes esperados:
- Cerveceria ABI
- Daikin
- Derco
- Mascotas Latinas (Quilicura)
- Pochteca
- Barentz
- Cepas Chile
- Collico
- Delibest
- Intime
- Mascotas Latinas (Pudahuel) = `active=False`
- Nativo Drinks
- Runo SPA
- Unilever

---

## 5. FLUJO PRINCIPAL

Para cada cliente activo:
1. Login WMS con Playwright.
2. Seleccionar deposito.
3. Navegar a `Consulta de Fill Rate`.
4. Configurar filtros del mes actual.
5. Exportar Excel y moverlo de inmediato a `logs\temp_fillrate_{cliente}.xlsx`.
6. Procesar advertencias y datos.
7. Descargar archivo acumulado desde SharePoint.
8. Reemplazar solo el mes actual.
9. Reescribir formulas AA:AS usando fila 2 como template.
10. Subir archivo a SharePoint.
11. Acumular resultado para correo final.

---

## 6. REGLAS NO NEGOCIABLES

- `active=False` = omitir y seguir.
- `0 filas` = no modificar SharePoint.
- Graph API = un retry antes de error final.
- No tocar hoja `base`.
- Trabajar sobre `seguimiento de pedidos`; si no existe, usar la primera hoja disponible y dejarlo en log.
- No inventar dropdowns, botones ni formulas; validar en runtime o leer del archivo real.
- `Corte` solo aplica cuando `has_corte=True`.

---

## 7. FORMULAS Y CORTE

- Las formulas de columnas AA:AS deben salir de la fila 2 del archivo real del cliente.
- No hardcodear formulas como unica fuente de verdad.
- `AS` es `Corte` solo para clientes con `has_corte=True`.
- `Corte` se calcula en Python, no como formula Excel.

---

## 8. VALIDACIONES RUNTIME

Debe confirmarse en runtime:
- Textos exactos de dropdowns y botones WMS.
- Nombre real de la hoja target si no existe `seguimiento de pedidos`.
- Formulas reales de la fila 2 para AA:AS.
- Columna efectiva para identificar el mes actual en replace.
- Regla efectiva de corte y comportamiento por cliente si hay diferencias.

---

## 9. NOTAS OPERATIVAS

- Derco es cliente pesado; tratarlo como caso especial si el volumen lo exige.
- `PUDAHUEL UNITARIO` aplica especialmente a Runo SPA.
- Las advertencias por pedidos pendientes > 7 dias no detienen el proceso.
- El correo final debe salir por Graph API reutilizando el patron del ecosistema WMS.
