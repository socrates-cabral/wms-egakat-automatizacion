---
title: NutriMetab BI — Herramienta Clínica Nutricional/Metabólica
type: proyecto
sources: []
related: [proyecto-hackea-metabolismo]
updated: 2026-04-12
confidence: high
---

# NutriMetab BI

## Rol
Herramienta clínica interna para análisis nutricional y metabólico poblacional. **Separado de HackeaMetabolismo** (que es producto de consumo masivo). NutriMetab BI es para uso profesional/clínico.

- **Ruta:** `C:\ClaudeWork\NutriMetab_BI\`
- **Puerto:** 8504
- **DB:** SQLite — `data/nutrimetab.db` (20 pacientes dummy)
- **Launcher:** `launchers\run_dashboard.bat`

## Stack
- Streamlit (5 páginas dashboard)
- SQLite (local, sin servidor)
- scikit-learn — RandomForest 92% accuracy
- pandas + openpyxl (reportes Excel con formato condicional)

## Módulos core

| Archivo | Rol |
|---------|-----|
| `src/procesamiento/calculos_nutri.py` | IMC, TMB, GET, macros (Mifflin-St Jeor) |
| `src/procesamiento/calculos_metabol.py` | Metabolismo + protocolo +40, WHtR, screening insulínico, TEF |
| `src/modelos/modelo_riesgo.py` | RandomForest — score de riesgo compuesto |
| `src/ingesta/carga_datos.py` | Pipeline CSV → SQLite |
| `src/reportes/generar_reporte.py` | Excel + HTML con KPIs |
| `dashboard/components/kpi_cards.py` | Componentes reutilizables |

## Métricas clínicas implementadas
- HOMA-IR, TG/HDL, WHtR, TEF
- Score de riesgo compuesto (4 factores)
- Protocolo +40: ajuste de TMB, resistencia insulínica, cortisol circadiano
- Módulos de sueño (`07_Sueno.py`) y ejercicio (`06_Ejercicio.py`) con jerarquía +40

## Estado sprints (todos completados)
| Sprint | Contenido | Estado |
|--------|-----------|--------|
| S1 | Estructura + DB + 20 pacientes dummy | ✅ |
| S2 | `calculos_nutri.py` — IMC, TMB, GET, macros | ✅ |
| S2b | `calculos_metabol.py` — protocolo +40 | ✅ |
| S3 | Dashboard 5 páginas | ✅ |
| S4 | HOMA-IR, TG/HDL, WHtR, TEF, score riesgo | ✅ |
| S5 | RandomForest 92% — `data/modelo_riesgo.joblib` | ✅ |
| S6 | Reporte Excel + HTML | ✅ |
| S7 | Launchers: `run_dashboard.bat`, `run_ingesta.bat`, `run_reporte.bat` | ✅ |
| S8 | 18/18 tests — `py -m pytest tests/ -v` | ✅ |
| S7b | `07_Sueno.py` — sueño, cortisol circadiano, higiene +40 | ✅ |
| S8b | `06_Ejercicio.py` — jerarquía +40, rutinas sin equipo, TDEE por nivel | ✅ |

**Estado final: sin roadmap pendiente.**

## Separación histórica
2026-03-31: Claude.ai browser había mezclado CLAUDE.md de NutriMetab con el producto HackeaMetabolismo. Se restauró CLAUDE.md de NutriMetab y se creó `C:\ClaudeWork\HackeaMetabolismo\` como proyecto separado con CLAUDE.md propio.
