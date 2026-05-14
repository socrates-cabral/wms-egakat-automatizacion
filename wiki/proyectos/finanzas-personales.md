---
title: Finanzas Personales — App Streamlit con migración a Supabase
type: proyecto
sources: []
related: [inversiones-ia, hackea-metabolismo, decision-haiku-modelo]
updated: 2026-05-14
confidence: high
---

# Finanzas Personales

## Rol
App Streamlit de finanzas personales (mercado chileno) para uso familiar — dashboard, presupuesto, patrimonio, deudas, AFP/AFC, liquidaciones e importador bancario. Originalmente sobre Excel `.xlsm` local; desde Sprint 5 con capa Supabase en coexistencia y deploy en Streamlit Cloud.

- **Ruta dev:** `C:\ClaudeWork\finanzas_personales\` — desde Sprint 5 es **repo git propio** (patrón HackeaMetabolismo), no parte del monorepo
- **Repo:** `github.com/socrates-cabral/finanzas-personales` (privado→público para deploy)
- **Deploy:** `finanzas-socrates.streamlit.app` (Streamlit Community Cloud, app pública)
- **Puerto local:** 8501 — launcher `abrir_app_silencioso.vbs`
- **Main file (cloud):** `app/main.py`

## Stack
- Streamlit + Plotly (tema dark, CSS centralizado en `main.py`)
- Supabase (PostgreSQL + Auth + RLS) — proyecto dedicado, separado de crypto_bot
- Claude / OpenAI / Gemini — insights IA con fallback en cadena
- pdfplumber (liquidaciones, CMF, BancoEstado TDC), openpyxl (Excel)
- extra-streamlit-components (CookieManager para sesión persistente)

## Arquitectura — coexistencia Excel ↔ Supabase
Toggle `DATA_SOURCE` (env): `excel` (default, dev local) | `supabase` (nube).
- `app/data_source.py` — facade: las 4 funciones con equivalente en Supabase
  (transacciones, categorías, patrimonio, config) togglan; el resto (parsers PDF)
  pasa directo a `data_loader`. Funciones Excel-only degradan a vacío si no hay `.xlsm`.
- `app/supabase_repo.py` — capa de acceso. Cliente service_role para scripts backend;
  cliente con JWT del usuario post-login (RLS real).
- `app/cloud_config.py` — unifica `.env` local + `st.secrets` nube en `os.environ`.
- `db/schema.sql` — 4 tablas + RLS multi-usuario (`auth.uid() = user_id`) + triggers.
- `db/migrar_excel_a_supabase.py` — migración con `--reset`/`--dry-run`.
- `db/crear_usuario.py` — alta de usuario vía Supabase Auth admin API.

## Login (Supabase Auth)
- `app/auth.py` — `require_login()` gate; solo exige login si `DATA_SOURCE=supabase`.
  Login vía `sign_in_with_password`; sesión entrega UUID → `set_authenticated_client()`.
- Sesión persistente con cookie (refresh_token, 7 días) — sobrevive F5.
- Agregar persona = crear su cuenta en Supabase Auth; RLS aísla cada usuario.

## Decisiones clave Sprint 5
- **Supabase Auth directo** (no streamlit-authenticator) — un solo almacén de usuarios,
  UUID automático desde la sesión, RLS nativo con el JWT.
- **Coexistencia con toggle** (no cutover) — Excel sigue siendo fuente en dev hasta validar.
- **Repo dedicado** (no deploy desde el monorepo) — Streamlit Cloud solo ve esta app,
  no WMS/apuestas/crypto.
- **Cookie `secure=True, same_site="none"`** — el default `Strict` se pierde en el iframe
  cross-site de Streamlit Cloud (causa raíz del F5 que deslogueaba).
- **IA standalone** — `_claude_personal` usa el SDK `anthropic` directo, sin el módulo
  `agentes` del monorepo (ausente en el repo dedicado).

## Importador bancario
`app/bank_importer.py` — parser universal BCI / BancoEstado (CC + TDC PDF) / Itaú /
Falabella / Consorcio. Dedup cross-file, categorización 4 niveles
(auto-patrimonial → caché → patrón lógico → Claude Haiku), panel de revisión con
cascada grupo→concepto y toggle TEF. Exporta CSV (aún no escribe a Supabase).

## Páginas
Dashboard · Gastos · Ingresos/Liquidaciones · Mes Detalle · Vista Anual · Patrimonio ·
AFP y Previsión (inc. AFC) · Deudas · Importar Banco · Simulador Financiero · Ajustes · Información

## Estado
- **Sprint 5 completo (2026-05-14):** Supabase + RLS + migración + login + deploy. App en producción.
- Migración validada en paridad: 348 transacciones + 69 categorías + 22 config, Excel == Supabase.

## Pendientes / follow-ups
- `config_manager.py` lee config de `os.getenv()`+DEFAULTS, no de la tabla `config_usuario`
  de Supabase — en la nube usa los defaults hardcodeados. Falta cablear.
- La app aún no **escribe** a Supabase — editar gastos sigue siendo vía Excel; el importador
  exporta CSV. El write-back es la próxima pieza grande.
- `use_container_width` deprecado — limpieza cosmética.
