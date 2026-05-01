---
title: Remediación de seguridad — agente_apuestas 2026-05-01
type: decision
sources: [SECURITY_REMEDIATION_STEPS.md, .gitignore, agente_apuestas/multi_llm_analyst.py, agente_apuestas/claude_agent.py]
related: [wiki/proyectos/agente-apuestas-orquestador.md, wiki/proyectos/agente-apuestas-fixes-2026-04-29.md]
updated: 2026-05-01
confidence: high
---

# Remediación de seguridad — agente_apuestas 2026-05-01

## Incidente
Se detectó que `agente_apuestas/.footystats_profile/` había quedado versionado con artefactos sensibles de navegador persistente: cache, cookies y storage local. La key antigua de Google Cloud asociada al incidente fue revocada fuera de Git antes de continuar.

## Estado final
- La key vigente se mantiene solo en `C:\ClaudeWork\.env` como `GOOGLE_API_KEY`.
- `multi_llm_analyst.py` y `claude_agent.py` cargan ese `.env` raíz y leen `GOOGLE_API_KEY` sin hardcodearla.
- `agente_apuestas/.footystats_profile/` fue eliminado del working tree, del tracking y de todo el historial Git.
- El repo principal `C:\ClaudeWork` quedó limpio y luego fue publicado en `idx/main`.

## Reglas de hardening agregadas o confirmadas
- `.env`
- `*.env`
- `.env.local`
- `.env.*.local`
- `**/.footystats_profile/`
- `**/Cache/`
- `**/Cache_Data/`
- `**/Local Storage/`
- `**/Session Storage/`
- `**/IndexedDB/`
- `**/Cookies`
- `**/Network/`
- `**/GPUCache/`
- `**/Code Cache/`
- `**/Service Worker/`
- `playwright-report/`
- `test-results/`

## Validaciones post-limpieza
- `PATH_COUNT=0` al buscar rutas históricas del perfil y artefactos sensibles.
- `MATCH_COUNT=0` al buscar patrón histórico `AIza`.
- `git log --all -- agente_apuestas/.footystats_profile` sin resultados.
- `HEAD` ya no contiene `.footystats_profile`.

## Nota operativa
La rama `main` de este repo trackea `idx/main`. `origin` apunta a otro remoto y no debe asumirse como destino correcto para publicar fixes de seguridad o historia reescrita.