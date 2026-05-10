"""Genera wf_bot_ops.json con el chat_id personal y grupo ops desde .env."""
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.stdout.reconfigure(encoding="utf-8")

BASE = Path(__file__).resolve().parent.parent.parent  # C:\ClaudeWork

load_dotenv(BASE / "Softnet_Ventas" / ".env", override=False)
load_dotenv(BASE / "WMS_Automatizacion" / ".env", override=False)
load_dotenv(BASE / ".env", override=False)

CHAT_ID_PERSONAL = int(os.getenv("TELEGRAM_ID_PERSONAL", "0"))
GRUPO_OPS_ID = int(os.getenv("TELEGRAM_GRUPO_OPS_ID", "0"))

assert CHAT_ID_PERSONAL, "TELEGRAM_ID_PERSONAL no encontrado en .env"
assert GRUPO_OPS_ID, "TELEGRAM_GRUPO_OPS_ID no encontrado en .env"

CONTEXT_EXPR = (
    "={{ (() => { "
    "const src = $('Obtener Contexto Operacional').item.json || {}; "
    "const kpiOps = src.kpi_ops || {}; "
    "const productividad = kpiOps.productividad || {}; "
    "const derco = productividad.derco || {}; "
    "const contexto = { "
    "fecha_consulta: src.fecha_consulta, "
    "datos_de_ayer: src.datos_de_ayer, "
    "pipeline: src.pipeline, "
    "validacion: src.validacion, "
    "alertas: src.alertas, "
    "kpi_ops: { "
    "nnss: kpiOps.nnss, "
    "inventario: kpiOps.inventario, "
    "productividad: { "
    "global: productividad.global, "
    "diario: productividad.diario, "
    "por_fecha_cliente: productividad.por_fecha_cliente, "
    "derco: { "
    "por_fecha: derco.por_fecha, "
    "ap_por_fecha: derco.ap_por_fecha, "
    "canal_por_fecha: derco.canal_por_fecha "
    "}, "
    "metas: productividad.metas "
    "} "
    "} "
    "}; "
    "const maxContextLength = 60000; "
    "const tryAdd = (key, value) => { "
    "if (!value) return; "
    "const candidate = JSON.parse(JSON.stringify(contexto)); "
    "candidate.kpi_ops.productividad[key] = value; "
    "if (JSON.stringify(candidate).length <= maxContextLength) { "
    "contexto.kpi_ops.productividad[key] = value; "
    "} "
    "}; "
    "if (productividad.por_fecha_cliente) { "
    "contexto.kpi_ops.productividad.por_fecha_cliente = productividad.por_fecha_cliente; "
    "} "
    "tryAdd('por_fecha_cliente_canal', productividad.por_fecha_cliente_canal); "
    "tryAdd('por_fecha_cliente_turno', productividad.por_fecha_cliente_turno); "
    "return JSON.stringify(contexto); "
    "})() }}"
)

SYSTEM = (
    "Eres el analista de operaciones WMS de Egakat SPA, empresa chilena de logistica 3PL.\n\n"
    "Tu funcion es responder consultas internas sobre el estado del pipeline WMS, modulos de descarga, "
    "alertas operacionales, staging, posiciones, recepciones y productividad diaria.\n\n"
    "Tienes el contexto operacional actual inyectado al final de este mensaje.\n"
    "Usalo cuando pregunten sobre:\n"
    "- estado del WMS\n- modulos ejecutados\n- fallos o advertencias\n"
    "- duracion de la descarga\n- validacion de archivos\n- staging\n- alertas operacionales\n"
    "- productividad diaria y productividad por cliente\n\n"
    "DEFINICIONES OPERACIONALES:\n"
    "- OK: modulo ejecutado sin errores ni fallos internos.\n"
    "- PARCIAL: modulo ejecuto pero tuvo fallos en algunos clientes o centros.\n"
    "- FALLO: modulo no ejecuto correctamente.\n"
    "- OK_REINTENTO: modulo fallo pero se recupero en el reintento automatico.\n"
    "- SKIP: modulo saltado por checkpoint.\n"
    "- ADVERTENCIA: validacion detecto observaciones no bloqueantes.\n\n"
    "REGLAS CRITICAS:\n"
    "- Nunca inventes datos; si no esta en el contexto, dilo claramente.\n"
    "- Distingue entre fallos operativos y advertencias de validacion.\n"
    "- Un PARCIAL no es lo mismo que un FALLO total.\n"
    "- Si datos_de_ayer=true, indica que los datos son del dia anterior.\n"
    "- Para una fecha general, usa kpi_ops.productividad.diario o kpi_ops.productividad.por_fecha_cliente.\n"
    "- Para cliente + fecha, usa kpi_ops.productividad.por_fecha_cliente filtrado por cliente y fecha.\n"
    "- Para fecha + todos los clientes, usa kpi_ops.productividad.por_fecha_cliente filtrado por la fecha solicitada.\n"
    "- Para cliente sin fecha, usa kpi_ops.productividad.por_fecha_cliente filtrado por cliente y resume el periodo.\n"
    "- Para DERCO por fecha, usa tambien kpi_ops.productividad.derco.por_fecha, ap_por_fecha y canal_por_fecha cuando aplique.\n"
    "- No respondas que no existe informacion estructurada si kpi_ops.productividad.por_fecha_cliente existe y contiene registros aplicables.\n"
    "- Si el usuario pregunta por productividad diaria, no mezcles con alertas de NNSS ni pedidos preparados salvo que exista una alerta especifica dentro de kpi_ops.productividad.\n"
    "- OTIF POR CD: para preguntas sobre Quilicura o Pudahuel como CD, busca en kpi_ops.nnss.otif.por_cd el objeto cuyo campo 'cd' sea 'QUILICURA' o 'PUDAHUEL'. "
    "Lee pedidos_evaluados, pedidos_no_on_time, pedidos_no_in_full, pct_on_time, pct_in_full, pct_otif de ESE objeto. "
    "NO uses kpi_ops.nnss.otif.pedidos_evaluados ni pct_otif global — esos son totales de todos los CDs. "
    "NO confundas arrastres.total con pedidos_no_on_time: son campos distintos. "
    "Los arrastres se mencionan como contexto del gap si son relevantes, pero el conteo de pedidos no on time viene de pedidos_no_on_time del objeto por_cd.\n"
    "- FORMATO DE PORCENTAJES: Nunca uses nombres de campos tecnicos del JSON en la respuesta (pct_otif, pct_on_time, pct_in_full, pct_fill_rate, etc.). "
    "Siempre escribe el numero seguido del simbolo %: '91,4%' en lugar de 'pct_otif: 91.4'. Usa coma decimal, no punto.\n\n"
    "FORMATO OBLIGATORIO (Telegram HTML):\n"
    "- Titulos: <b>Seccion</b>\n"
    "- Listas con guion (-)\n"
    "- Emojis de estado: OK, advertencia o fallo\n"
    "- No uses tablas Markdown, encabezados ## ni asteriscos\n"
    "- Maximo 350 palabras\n"
    "- No menciones JSON, API, endpoint ni estructura tecnica\n\n"
    "SI EL USUARIO SALUDA:\n"
    "Hola, soy el analista de operaciones WMS de Egakat. Puedo ayudarte con el estado del pipeline, "
    "modulos ejecutados, alertas, validacion de archivos y productividad diaria.\n\n"
    "SI LOS DATOS LLEGAN VACIOS:\n"
    "No pude obtener el contexto operacional actual. Verifica que la API de Operaciones este activa.\n\n"
    "CONTEXTO OPERACIONAL ACTUAL:\n"
    + CONTEXT_EXPR
)

wf = {
    "name": "Egakat Ops Bot - WMS Intelligence v1",
    "nodes": [
        {
            "id": "n1",
            "name": "Telegram Trigger",
            "type": "n8n-nodes-base.telegramTrigger",
            "typeVersion": 1.1,
            "position": [-1800, 300],
            "webhookId": "wms-ops-v2",
            "parameters": {"updates": ["message"], "additionalFields": {}},
            "credentials": {"telegramApi": {"name": "Telegram EgakatOpsBot"}},
        },
        {
            "id": "n2",
            "name": "Es mencion o privado?",
            "type": "n8n-nodes-base.if",
            "typeVersion": 2,
            "position": [-1580, 300],
            "parameters": {
                "conditions": {
                    "options": {"caseSensitive": False},
                    "conditions": [
                        {
                            "id": "c1",
                            "leftValue": "={{ $json.message.text.includes('@EgakatOpsBot') || $json.message.chat.type === 'private' }}",
                            "rightValue": True,
                            "operator": {"type": "boolean", "operation": "true"},
                        }
                    ],
                    "combinator": "or",
                }
            },
        },
        {
            "id": "n_wl",
            "name": "Es chat autorizado?",
            "type": "n8n-nodes-base.if",
            "typeVersion": 2,
            "position": [-1360, 200],
            "parameters": {
                "conditions": {
                    "options": {"caseSensitive": False},
                    "conditions": [
                        {
                            "id": "w1",
                            "leftValue": f"={{{{ [{GRUPO_OPS_ID}, {CHAT_ID_PERSONAL}].includes($('Telegram Trigger').item.json.message.chat.id) }}}}",
                            "rightValue": True,
                            "operator": {"type": "boolean", "operation": "true"},
                        }
                    ],
                    "combinator": "and",
                }
            },
        },
        {
            "id": "n_noauth",
            "name": "No Autorizado Ops",
            "type": "n8n-nodes-base.telegram",
            "typeVersion": 1.2,
            "position": [-1360, 420],
            "parameters": {
                "chatId": "={{ $('Telegram Trigger').item.json.message.chat.id }}",
                "text": "Acceso restringido. Este bot es de uso interno del equipo de Operaciones.",
                "additionalFields": {},
            },
            "credentials": {"telegramApi": {"name": "Telegram EgakatOpsBot"}},
        },
        {
            "id": "n3",
            "name": "Limpiar mensaje",
            "type": "n8n-nodes-base.set",
            "typeVersion": 3.4,
            "position": [-1140, 200],
            "parameters": {
                "assignments": {
                    "assignments": [
                        {
                            "id": "a1",
                            "name": "chat_id",
                            "value": "={{ $('Telegram Trigger').item.json.message.chat.id }}",
                            "type": "string",
                        },
                        {
                            "id": "a2",
                            "name": "mensaje",
                            "value": "={{ $('Telegram Trigger').item.json.message.text.replace('@EgakatOpsBot', '').trim() }}",
                            "type": "string",
                        },
                    ]
                },
                "options": {},
            },
        },
        {
            "id": "n4",
            "name": "Obtener Contexto Operacional",
            "type": "n8n-nodes-base.httpRequest",
            "typeVersion": 4.2,
            "position": [-920, 200],
            "parameters": {
                "method": "GET",
                "url": "https://api-ops.socrates-labs.com/ops/contexto/resumen",
                "sendHeaders": True,
                "headerParameters": {
                    "parameters": [
                        {"name": "X-API-Key", "value": "={{ $env.API_OPS_SECRET }}"}
                    ]
                },
                "options": {},
            },
        },
        {
            "id": "n4b",
            "name": "Preparar Contexto AI",
            "type": "n8n-nodes-base.set",
            "typeVersion": 3.4,
            "position": [-810, 200],
            "parameters": {
                "assignments": {
                    "assignments": [
                        {
                            "id": "ctx1",
                            "name": "contexto_operacional_actual",
                            "value": CONTEXT_EXPR,
                            "type": "string",
                        }
                    ]
                },
                "options": {},
            },
        },
        {
            "id": "n5",
            "name": "Agente Ops Egakat",
            "type": "@n8n/n8n-nodes-langchain.agent",
            "typeVersion": 3,
            "position": [-700, 200],
            "parameters": {
                "promptType": "define",
                "text": "={{ $('Limpiar mensaje').item.json.mensaje }}",
                "options": {"systemMessage": SYSTEM},
            },
        },
        {
            "id": "n6",
            "name": "Modelo OpenAI",
            "type": "@n8n/n8n-nodes-langchain.lmChatOpenAi",
            "typeVersion": 1.3,
            "position": [-700, 420],
            "parameters": {
                "model": {"__rl": True, "mode": "list", "value": "gpt-4.1-mini"},
                "builtInTools": {},
                "options": {},
            },
            "credentials": {"openAiApi": {"name": "OpenAi account"}},
        },
        {
            "id": "n7",
            "name": "Memoria por Chat",
            "type": "@n8n/n8n-nodes-langchain.memoryBufferWindow",
            "typeVersion": 1.3,
            "position": [-700, 560],
            "parameters": {
                "sessionIdType": "customKey",
                "sessionKey": "={{ $('Telegram Trigger').item.json.message.chat.id }}",
                "contextWindowLength": 8,
            },
        },
        {
            "id": "n8",
            "name": "Enviar Respuesta",
            "type": "n8n-nodes-base.telegram",
            "typeVersion": 1.2,
            "position": [-480, 200],
            "parameters": {
                "chatId": "={{ $('Limpiar mensaje').item.json.chat_id }}",
                "text": "={{ $json.output }}",
                "additionalFields": {"parse_mode": "HTML"},
            },
            "credentials": {"telegramApi": {"name": "Telegram EgakatOpsBot"}},
        },
        {
            "id": "n9",
            "name": "Sticky Note",
            "type": "n8n-nodes-base.stickyNote",
            "typeVersion": 1,
            "position": [-1900, 100],
            "parameters": {
                "content": (
                    "## Egakat Ops Bot - WMS Intelligence v1\n\n"
                    "**Sprint 1:** Estado pipeline WMS del dia\n"
                    "**Sprint 2:** Fill Rate / OTIF\n"
                    "**Sprint 3:** Productividad\n\n"
                    "**Variables .env requeridas:**\n"
                    "- TELEGRAM_ID_PERSONAL\n"
                    "- TELEGRAM_GRUPO_OPS_ID (en Softnet_Ventas/.env)\n"
                    "- API_OPS_SECRET\n\n"
                    "**Tras activar:** Publish y registrar webhook manualmente\n"
                    f"Grupo Ops: {GRUPO_OPS_ID}\n"
                    f"Chat admin: {CHAT_ID_PERSONAL}"
                ),
                "height": 320,
                "width": 440,
                "color": 3,
            },
        },
    ],
    "connections": {
        "Telegram Trigger": {
            "main": [[{"node": "Es mencion o privado?", "type": "main", "index": 0}]]
        },
        "Es mencion o privado?": {
            "main": [[{"node": "Es chat autorizado?", "type": "main", "index": 0}], []]
        },
        "Es chat autorizado?": {
            "main": [
                [{"node": "Limpiar mensaje", "type": "main", "index": 0}],
                [{"node": "No Autorizado Ops", "type": "main", "index": 0}],
            ]
        },
        "Limpiar mensaje": {
            "main": [[{"node": "Obtener Contexto Operacional", "type": "main", "index": 0}]]
        },
        "Obtener Contexto Operacional": {
            "main": [[{"node": "Preparar Contexto AI", "type": "main", "index": 0}]]
        },
        "Preparar Contexto AI": {
            "main": [[{"node": "Agente Ops Egakat", "type": "main", "index": 0}]]
        },
        "Agente Ops Egakat": {
            "main": [[{"node": "Enviar Respuesta", "type": "main", "index": 0}]]
        },
        "Modelo OpenAI": {
            "ai_languageModel": [
                [{"node": "Agente Ops Egakat", "type": "ai_languageModel", "index": 0}]
            ]
        },
        "Memoria por Chat": {
            "ai_memory": [[{"node": "Agente Ops Egakat", "type": "ai_memory", "index": 0}]]
        },
    },
    "settings": {"executionOrder": "v1"},
}

out = Path(__file__).resolve().parent / "wf_bot_ops.json"
out.write_text(json.dumps(wf, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"OK - {out}")
print(f"Grupo Ops ID : {GRUPO_OPS_ID}")
print(f"Chat personal: {CHAT_ID_PERSONAL}")
