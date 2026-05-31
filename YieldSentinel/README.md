# ⚡ YIELD SENTINEL — Guía de Instalación (Windows)

Sistema híbrido de trading automatizado: noticias macro → señales → paper trading → Hyperliquid

---

## ESTRUCTURA DEL PROYECTO

```
YieldSentinel/
├── config.py                    ← TUS CREDENCIALES (editar primero)
├── orchestrator.py              ← Orquestador principal
├── agents/
│   ├── market_agent.py          ← Precios de Hyperliquid
│   ├── news_agent.py            ← Noticias macro (RSS)
│   ├── signal_agent.py          ← Generador de señales
│   ├── paper_agent.py           ← Simulador de trades
│   └── telegram_agent.py        ← Notificaciones
├── data/
│   ├── logs/                    ← Logs de cada agente
│   ├── trades/                  ← Historial de trades
│   └── backtest/                ← Resultados de backtesting
├── n8n_workflows/
│   └── orchestrator_workflow.json  ← Importar en n8n
└── dashboard/
    └── YieldSentinelDashboard.jsx  ← Dashboard visual
```

---

## INSTALACIÓN PASO A PASO

### Paso 1: Instalar Python (si no lo tienes)

1. Ve a https://www.python.org/downloads/
2. Descarga Python 3.11 o superior
3. **IMPORTANTE:** Marcar "Add Python to PATH" durante la instalación
4. Verificar: abre CMD y escribe `python --version`

### Paso 2: Crear carpeta del proyecto

```cmd
mkdir C:\YieldSentinel
cd C:\YieldSentinel
```

Copia todos los archivos del proyecto en esta carpeta.

### Paso 3: Instalar dependencias

```cmd
cd C:\YieldSentinel
pip install requests feedparser
```

Eso es todo. Sin dependencias pesadas.

### Paso 4: Configurar credenciales

Abre `config.py` con el Bloc de Notas y edita:

```python
# Tu bot de Telegram actual
TELEGRAM_BOT_TOKEN = "123456789:ABCdef..."   # Tu token real
TELEGRAM_CHAT_ID   = "987654321"             # Tu Chat ID

# Hyperliquid (por ahora dejarlo como está - testnet)
HL_USE_TESTNET    = True   # True = paper trading, sin dinero real
HL_WALLET_ADDRESS = ""     # Dejar vacío por ahora
HL_PRIVATE_KEY    = ""     # Dejar vacío por ahora
```

**¿Cómo encontrar tu Chat ID de Telegram?**
1. Escribe a @userinfobot en Telegram
2. Te responde con tu ID

### Paso 5: Primera prueba

```cmd
cd C:\YieldSentinel
python orchestrator.py --mode test
```

Deberías ver:
```
1. Market Agent... ✅ 5 activos
2. News Agent...   ✅ X noticias relevantes
3. Telegram Agent... ✅ Telegram
4. Paper Agent...  ✅ Capital: $1,000.00
```

### Paso 6: Correr el primer ciclo completo

```cmd
python orchestrator.py --mode once
```

Revisa tu Telegram — deberías recibir alertas si hay noticias relevantes.

### Paso 7: Automatizar con el Programador de Tareas de Windows

1. Abre "Programador de tareas" (buscar en inicio)
2. Clic en "Crear tarea básica"
3. Nombre: "Yield Sentinel - 15min"
4. Desencadenador: "Diariamente", repetir cada 15 minutos
5. Acción: "Iniciar un programa"
   - Programa: `python`
   - Argumentos: `C:\YieldSentinel\orchestrator.py --mode once`
   - Inicio en: `C:\YieldSentinel`
6. Guardar

**Alternativa: importar en n8n**
1. Abrir n8n → Workflows → Import from file
2. Seleccionar `n8n_workflows/orchestrator_workflow.json`
3. Cambiar la ruta en los nodos Execute Command
4. Activar el workflow

---

## FLUJO DE TRABAJO

```
Cada 15 minutos:
[Precio HL] → [Noticias RSS] → [Evaluar señal] → [Paper Trade] → [Telegram]

Cada 6 horas:
[Reporte de performance] → [Telegram]

Al llegar a ROI >= 20% con >= 20 trades:
[DECISIÓN: ¿pasar a producción real?]
```

---

## REGLAS DE HIERRO (inamovibles en producción)

| Regla                   | Valor             |
|-------------------------|-------------------|
| Leverage máximo         | 2x                |
| Stop-Loss               | 1.5% (obligatorio)|
| Take-Profit             | 3.0%              |
| Riesgo por trade        | 2% del capital    |
| Posiciones simultáneas  | máx. 2            |
| Tiempo máximo posición  | 48 horas          |
| **ROI mínimo producción** | **>= 20%**      |

---

## FASES DEL PROYECTO

| Fase | Estado | Descripción |
|------|--------|-------------|
| 1 | ✅ Activa | Paper trading local (este código) |
| 2 | ⏳ Siguiente | Testnet de Hyperliquid (ejecución real simulada) |
| 3 | 🔒 Bloqueada | Producción real (solo con ROI >= 20% validado) |

**La Fase 3 está bloqueada hasta que el sistema demuestre ROI >= 20%.**
No hay excepciones. El código te lo recordará.

---

## COMANDOS ÚTILES

```cmd
# Un ciclo completo
python orchestrator.py --mode once

# Modo continuo (corre sin parar)
python orchestrator.py --mode continuous

# Ver reporte en Telegram
python orchestrator.py --mode report

# Probar que todo funciona
python orchestrator.py --mode test

# Probar solo un agente
python agents/market_agent.py
python agents/news_agent.py
python agents/signal_agent.py
python agents/paper_agent.py
```

---

## SEGURIDAD

- **NUNCA** compartas `config.py`
- **NUNCA** subas este proyecto a GitHub con las credenciales
- La API key de Kraken que tienes: no se usa aquí (Hyperliquid usa wallet)
- Las API keys de Hyperliquid para producción: permisos solo de trading, NUNCA de retiro

---

## PRÓXIMOS PASOS (Fase 2)

Cuando el paper trading local muestre ROI >= 20%:

1. Crear wallet separada en MetaMask (solo para el bot)
2. Depositar fondos mínimos de testnet (gratis)
3. Cambiar `HL_USE_TESTNET = True` (ya está configurado)
4. El bot ejecutará órdenes reales en testnet con fondos virtuales
5. Validar que los resultados son consistentes con el paper trading local

---

*Yield Sentinel v1.0 — Construido con Python + n8n + Hyperliquid API*
