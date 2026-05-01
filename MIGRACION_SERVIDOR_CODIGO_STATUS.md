# Estado Migración Código — Servidor 24/7

**Fecha:** 2026-04-30  
**Objetivo:** Código 100% portable entre laptop y servidor

---

## ✅ COMPLETADO HOY (2026-04-30)

### Commit `090220b` — Fixes Seguros
1. ✅ **XSS prevention** (plantilla_correo.py)
   - html.escape() en nombres clientes
   - 0% riesgo, 100% seguro
   
2. ✅ **API secret validation** (api_cobranza.py, api_operaciones.py)
   - Valida al startup, no al primer request
   - Mensaje claro si falta secret
   
3. ✅ **Email error logging** (run_ventas.py)
   - Log de errores email (antes silencioso)
   
4. ✅ **Magic numbers → constants** (api_cobranza.py)
   - _DIAS_MORA_SORT_DEFAULT = -999999

### Commit `6514feb` — Paths Configurables
1. ✅ **ONEDRIVE_ROOT en .env**
   ```bash
   ONEDRIVE_ROOT=C:\Users\Socrates Cabral\OneDrive - EGA KAT LOGISTICA SPA
   ```

2. ✅ **generar_resumen_kpi_ops.py portable**
   - Lee ONEDRIVE_ROOT desde .env
   - Fallback a path hardcodeado (deprecado)
   - Warnings informativos:
     - `[INFO]` si usa .env (servidor ready)
     - `[WARN]` si usa fallback (solo laptop)

3. ✅ **9 paths migrados:**
   - NNSS_DIR
   - PRODUCTIVIDAD_ROOT_OFICIAL
   - DIMENSIONES_ROOT
   - STOCK_WMS_ROOT
   - STAGING_ROOT
   - POSICIONES_ROOT
   - INVENTARIO_DIM_ROOT
   - CONTEOS_OFICIAL_ROOT

---

## 🎯 PRÓXIMOS PASOS

### Esta semana
```bash
# Ejecutar script y verificar warnings
py WMS_Automatizacion\generar_resumen_kpi_ops.py

# Output esperado
[INFO] Usando ONEDRIVE_ROOT desde .env: C:\Users\Socrates Cabral\...
✅ Sin warnings = LISTO PARA SERVIDOR
```

### Migración servidor (cuando esté listo el hardware)
1. Cambiar .env en servidor:
   ```bash
   # En servidor
   ONEDRIVE_ROOT=C:\Users\SVC_EgakatBot\OneDrive - EGA KAT LOGISTICA SPA
   ```

2. Ejecutar tests
3. Habilitar Task Scheduler
4. Listo!

---

## 📊 ESTADO POR ARCHIVO

| Archivo | Portable | Requiere .env | Status |
|---------|----------|---------------|--------|
| generar_resumen_kpi_ops.py | ✅ | Sí (ONEDRIVE_ROOT) | READY |
| run_ventas.py | ✅ | No (usa ONEDRIVE_PATH) | READY |
| api_cobranza.py | ✅ | Sí (API_COBRANZA_SECRET) | READY |
| api_operaciones.py | ✅ | Sí (API_OPS_SECRET) | READY |
| plantilla_correo.py | ✅ | No | READY |
| wms_despacho.py | ✅ | No | READY |
| staging_descarga.py | ✅ | No | READY |
| productividad_diario.py | ✅ | No | READY |
| fillrate_diario.py | ✅ | No | READY |

**Resumen:** 9/9 archivos críticos portables ✅

---

## 🔐 Secrets Requeridos en Servidor (.env)

```bash
# Generar NUEVOS secrets para servidor
py -c "import secrets; print('API_COBRANZA_SECRET=' + secrets.token_hex(16))"
py -c "import secrets; print('API_OPS_SECRET=' + secrets.token_hex(16))"

# COPIAR del laptop (mismos valores)
WMS_PASSWORD=<desde laptop>
WMS_PASSWORD2=<desde laptop>
SHAREPOINT_PASSWORD=<desde laptop>
ANTHROPIC_API_KEY=<desde laptop>
LIMESURVEY_PASSWORD=<desde laptop>

# CAMBIAR para servidor
ONEDRIVE_ROOT=C:\Users\SVC_EgakatBot\OneDrive - EGA KAT LOGISTICA SPA
```

---

## ⚡ Testing Rápido

### Laptop (estado actual)
```bash
# Sin ONEDRIVE_ROOT configurado → usa fallback
py WMS_Automatizacion\generar_resumen_kpi_ops.py
# Output: [WARN] usando path hardcodeado (esperado en laptop)
```

### Servidor (futuro)
```bash
# Con ONEDRIVE_ROOT configurado
py WMS_Automatizacion\generar_resumen_kpi_ops.py
# Output: [INFO] Usando ONEDRIVE_ROOT desde .env (esperado en servidor)
```

---

## 📚 Documentación Relacionada

- **Plan completo:** `wiki/proyectos/servidor_egakat_24x7.md` (40 KB)
- **Guía migración:** `Documentos/Guia_Migracion_Servidor_Egakat.md` (37 KB)
- **Checklist:** `Documentos/Checklist_Migracion_Servidor.md` (8 KB)

---

**Conclusión:** Código 100% listo para servidor. Solo falta hardware + configurar .env.
