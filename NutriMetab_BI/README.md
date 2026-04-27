# 🧬 NutriMetab BI

Sistema integrado de seguimiento metabólico y nutricional con pipeline de datos,
modelos analíticos y dashboard Streamlit.

## Stack
- **Dashboard**: Streamlit (port 8504)
- **Análisis**: Python (pandas, scikit-learn, statsmodels)
- **Reportes**: openpyxl + HTML automatizado
- **DB**: SQLite (dev) / PostgreSQL (prod)

## Setup inicial
```bat
cd C:\ClaudeWork\NutriMetab_BI
launchers\setup_proyecto.bat
```

## Lanzar dashboard
```bat
py -m streamlit run dashboard/app.py --server.port 8504
```

## Estructura
```
NutriMetab_BI/
├── CLAUDE.md          ← instrucciones para Claude Code
├── data/              ← raw / processed / exports
├── src/               ← ingesta / procesamiento / modelos / reportes
├── dashboard/         ← Streamlit app (app.py + pages/)
├── notebooks/         ← exploración
├── tests/
└── launchers/         ← .bat para Task Scheduler
```

## Sprints
| # | Objetivo | Estado |
|---|---|---|
| S1 | Estructura base + datos dummy | ✅ |
| S2 | Cálculos nutricionales core | 🔄 |
| S3 | Dashboard páginas base | ⏳ |
| S4 | Biomarcadores + score metabólico | ⏳ |
| S5 | Modelo ML riesgo | ⏳ |
| S6 | Reportes automatizados | ⏳ |
| S7 | Task Scheduler + email | ⏳ |
| S8 | QA + documentación | ⏳ |
