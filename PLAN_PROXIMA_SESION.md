# Plan próxima sesión — Egakat SPA
Creado: 2026-03-20

---

## 1. VERIFICACIÓN DIARIA (primero siempre)
- [ ] Revisar si staging del día descargó bien MASCOTAS LATINAS y DELIBEST (fix 45s SCABRAL aplicado ayer)
- [ ] Revisar si Maestro Artículos DERCO corrió a las 09:00 AM

---

## 2. NPS / POWER BI (prioridad alta — en curso)

### 2a. Conectar Power BI al nuevo Excel
- Abrir Power BI Desktop
- Cambiar fuente de datos: Google Sheets → `OneDrive\Reportes NPS\NPS_PBI_datos.xlsx`
- Mapear columnas nuevas: fClientes, fÁreas, fClientes_mes, dClientes
- Verificar que medidas DAX existentes siguen funcionando
- Publicar al servicio Power BI

### 2b. Rediseño Power BI (carta blanca del usuario)
- Documentar M code existente línea por línea
- Mejorar visuales: gráficos de barras, gauges NPS, tabla de comentarios
- Nuevo diseño: paleta corporativa Egakat, layout limpio
- Agregar filtros por: Sistema (WMS/Odoo/SAP), Área, Mes, Clasificación

### 2c. 25/03 — NPS lanza
- Descargar tokens survey 418429 desde LimeSurvey → guardar como `NPS_Encuesta\tokens_nps.csv`
- Verificar que nps_descarga.py procesa NPS correctamente
- Agregar contacto NATIVO DRINKS SPA en LimeSurvey para esta ronda
- **Retirar a Fabiola Segovia (Syntheon)** de participantes — es proveedor IMO, no cliente. Mercancía es de POCHTECA.

---

## 3. STAGING — VERIFICACIÓN FIX
- Confirmar que MASCOTAS LATINAS y DELIBEST descargaron correctamente con el wait de 45s
- Si siguen fallando: investigar si es problema de horario/hibernación vs WMS lento

---

## 4. PENDIENTES OPERATIVOS

### Azure Graph API
- Seguimiento con José Contreras (IT): `Sites.ReadWrite.All` bajo Microsoft Graph
- Sin esto SharePoint directo no funciona (no urgente — OneDrive sync OK)

### finanzas_personales Sprint 4 (cuando haya tiempo)
- BCI scraper (tiene captcha → modo visible)
- ITAÚ scraper (confirmar descarga nativa Excel)
- playwright-stealth para BancoEstado automático
- CMF PDF parser: prueba final con PDF real subido en app
- Recargar saldo API Anthropic → AI Insights

---

## CONTEXTO CLAVE PARA RETOMAR

**nps_descarga.py v2.1** — completado 20/03:
- Genera 4 hojas Excel para Power BI
- Mapeo token→cliente vía `tokens_csat.csv` + `Contactos_Clientes.xlsx`
- NOMBRES_WMS con 21 clientes (WMS/Odoo/SAP)
- Columna `Sistema` en dClientes distingue WMS vs Odoo vs SAP
- CSAT: 3 respuestas de 21 (Cepas, Daikin, San Joaquin)
- NPS: lanza 25/03

**Clientes pendientes de agregar en LimeSurvey próxima ronda:**
- NATIVO DRINKS SPA (Cód WMS 34) — empresa de Juan Pablo Barahona, sin contacto propio aún
