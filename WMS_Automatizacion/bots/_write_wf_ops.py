"""Genera wf_bot_ops.json con el chat_id personal y grupo ops desde .env."""
import sys
sys.stdout.reconfigure(encoding="utf-8")
import json
from pathlib import Path
from dotenv import load_dotenv
import os

BASE = Path(__file__).resolve().parent.parent.parent  # C:\ClaudeWork

# Softnet_Ventas primero — tiene TELEGRAM_ID_PERSONAL y TELEGRAM_GRUPO_OPS_ID
load_dotenv(BASE / "Softnet_Ventas" / ".env", override=False)
load_dotenv(BASE / "WMS_Automatizacion" / ".env", override=False)
load_dotenv(BASE / ".env", override=False)

CHAT_ID_PERSONAL   = int(os.getenv("TELEGRAM_ID_PERSONAL", "0"))
GRUPO_OPS_ID       = int(os.getenv("TELEGRAM_GRUPO_OPS_ID", "0"))

assert CHAT_ID_PERSONAL, "TELEGRAM_ID_PERSONAL no encontrado en .env"
assert GRUPO_OPS_ID,     "TELEGRAM_GRUPO_OPS_ID no encontrado en .env"

SYSTEM = (
    "Eres el analista de operaciones WMS de Egakat SPA, empresa chilena de logística 3PL.\n\n"
    "Tu función es responder consultas internas sobre el estado del pipeline WMS, módulos de descarga, "
    "alertas operacionales, staging, posiciones y recepciones.\n\n"
    "Tienes datos del pipeline WMS inyectados al final de este mensaje.\n"
    "Úsalos cuando pregunten sobre:\n"
    "- estado del WMS\n- módulos ejecutados\n- fallos o advertencias\n"
    "- duración de la descarga\n- validación de archivos\n- staging\n- alertas operacionales\n\n"
    "DEFINICIONES OPERACIONALES:\n"
    "- OK: módulo ejecutado sin errores ni fallos internos.\n"
    "- PARCIAL: módulo ejecutó pero tuvo fallos en algunos clientes/centros.\n"
    "- FALLO: módulo no ejecutó correctamente.\n"
    "- OK_REINTENTO: módulo falló pero se recuperó en el reintento automático.\n"
    "- SKIP: módulo saltado por checkpoint (ya ejecutado previamente hoy).\n"
    "- ADVERTENCIA: validación detectó observaciones no bloqueantes.\n\n"
    "REGLAS CRÍTICAS:\n"
    "- Nunca inventes datos — si no está en el JSON, dilo claramente.\n"
    "- Distingue entre fallos operativos (M1-M8) y advertencias de validación (M9).\n"
    "- Un PARCIAL no es lo mismo que un FALLO total.\n"
    "- Si datos_de_ayer=true, indica que los datos son del día anterior.\n\n"
    "FORMATO OBLIGATORIO (Telegram HTML):\n"
    "- Títulos: <b>• Sección</b>\n"
    "- Listas con guion (-)\n"
    "- Emojis de estado: ✅ OK, ⚠️ advertencia, 🔴 fallo\n"
    "- NO tablas Markdown, NO ## encabezados, NO asteriscos\n"
    "- Máximo 350 palabras\n"
    "- No menciones JSON, API, endpoint ni estructura técnica\n\n"
    "ESTRUCTURA PARA ESTADO GENERAL:\n\n"
    "<b>• Estado WMS — DD/MM/AAAA</b>\n"
    "- <b>Estado global:</b> ✅ Todo OK | ⚠️ Con advertencias | 🔴 Con fallos\n"
    "- <b>Inicio:</b> HH:MM | <b>Duración:</b> XXm XXs\n"
    "- <b>Módulos ejecutados:</b> N\n\n"
    "<b>• Módulos operativos</b>\n"
    "- ✅ Modulo 1 - Stock WMS Semanal (Xm Xs)\n"
    "- ⚠️ Modulo 2 - Staging IN/OUT (Xm Xs) — detalle si hubo fallo\n\n"
    "<b>• Validación de archivos</b>\n"
    "- OK: X | Warning: X | Error: X | Total: X\n"
    "- Observación relevante si la hay\n\n"
    "<b>• Conclusión</b>\n"
    "Texto breve orientado a acción si hay algo que revisar.\n\n"
    "SI EL USUARIO SALUDA:\n"
    "Hola, soy el analista de operaciones WMS de Egakat. Puedo ayudarte con el estado del pipeline, "
    "módulos ejecutados, alertas y validación de archivos.\n\n"
    "SI LOS DATOS LLEGAN VACÍOS:\n"
    "No pude obtener el estado del pipeline WMS. Verifica que la API de Operaciones esté activa.\n\n"
    "DATOS PIPELINE WMS:\n"
    "={{ JSON.stringify($('Obtener Estado WMS').item.json) }}"
)

wf = {
    "name": "Egakat Ops Bot — WMS Intelligence v1",
    "nodes": [
        {
            "id": "n1", "name": "Telegram Trigger",
            "type": "n8n-nodes-base.telegramTrigger", "typeVersion": 1.1,
            "position": [-1800, 300],
            "webhookId": "wms-ops-v2",
            "parameters": {"updates": ["message"], "additionalFields": {}},
            "credentials": {"telegramApi": {"name": "Telegram EgakatOpsBot"}}
        },
        {
            "id": "n2", "name": "Es mencion o privado?",
            "type": "n8n-nodes-base.if", "typeVersion": 2,
            "position": [-1580, 300],
            "parameters": {
                "conditions": {
                    "options": {"caseSensitive": False},
                    "conditions": [{"id": "c1",
                        "leftValue": "={{ $json.message.text.includes('@EgakatOpsBot') || $json.message.chat.type === 'private' }}",
                        "rightValue": True,
                        "operator": {"type": "boolean", "operation": "true"}}],
                    "combinator": "or"
                }
            }
        },
        {
            "id": "n_wl", "name": "Es chat autorizado?",
            "type": "n8n-nodes-base.if", "typeVersion": 2,
            "position": [-1360, 200],
            "parameters": {
                "conditions": {
                    "options": {"caseSensitive": False},
                    "conditions": [{"id": "w1",
                        "leftValue": f"={{{{ [{GRUPO_OPS_ID}, {CHAT_ID_PERSONAL}].includes($('Telegram Trigger').item.json.message.chat.id) }}}}",
                        "rightValue": True,
                        "operator": {"type": "boolean", "operation": "true"}}],
                    "combinator": "and"
                }
            }
        },
        {
            "id": "n_noauth", "name": "No Autorizado Ops",
            "type": "n8n-nodes-base.telegram", "typeVersion": 1.2,
            "position": [-1360, 420],
            "parameters": {
                "chatId": "={{ $('Telegram Trigger').item.json.message.chat.id }}",
                "text": "⛔ Acceso restringido. Este bot es de uso interno del equipo de Operaciones.",
                "additionalFields": {}
            },
            "credentials": {"telegramApi": {"name": "Telegram EgakatOpsBot"}}
        },
        {
            "id": "n3", "name": "Limpiar mensaje",
            "type": "n8n-nodes-base.set", "typeVersion": 3.4,
            "position": [-1140, 200],
            "parameters": {
                "assignments": {"assignments": [
                    {"id": "a1", "name": "chat_id",
                     "value": "={{ $('Telegram Trigger').item.json.message.chat.id }}", "type": "string"},
                    {"id": "a2", "name": "mensaje",
                     "value": "={{ $('Telegram Trigger').item.json.message.text.replace('@EgakatOpsBot', '').trim() }}", "type": "string"},
                ]},
                "options": {}
            }
        },
        {
            "id": "n4", "name": "Obtener Estado WMS",
            "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2,
            "position": [-920, 200],
            "parameters": {
                "method": "GET",
                "url": "https://api-ops.socrates-labs.com/ops/pipeline/hoy",
                "sendHeaders": True,
                "headerParameters": {"parameters": [
                    {"name": "X-API-Key", "value": "={{ $env.API_OPS_SECRET }}"}
                ]},
                "options": {}
            }
        },
        {
            "id": "n5", "name": "Agente Ops Egakat",
            "type": "@n8n/n8n-nodes-langchain.agent", "typeVersion": 3,
            "position": [-700, 200],
            "parameters": {
                "promptType": "define",
                "text": "={{ $('Limpiar mensaje').item.json.mensaje }}",
                "options": {"systemMessage": SYSTEM}
            }
        },
        {
            "id": "n6", "name": "Modelo OpenAI",
            "type": "@n8n/n8n-nodes-langchain.lmChatOpenAi", "typeVersion": 1.3,
            "position": [-700, 420],
            "parameters": {
                "model": {"__rl": True, "mode": "list", "value": "gpt-4.1-mini"},
                "builtInTools": {}, "options": {}
            },
            "credentials": {"openAiApi": {"name": "OpenAi account"}}
        },
        {
            "id": "n7", "name": "Memoria por Chat",
            "type": "@n8n/n8n-nodes-langchain.memoryBufferWindow", "typeVersion": 1.3,
            "position": [-700, 560],
            "parameters": {
                "sessionIdType": "customKey",
                "sessionKey": "={{ $('Telegram Trigger').item.json.message.chat.id }}",
                "contextWindowLength": 8
            }
        },
        {
            "id": "n8", "name": "Enviar Respuesta",
            "type": "n8n-nodes-base.telegram", "typeVersion": 1.2,
            "position": [-480, 200],
            "parameters": {
                "chatId": "={{ $('Limpiar mensaje').item.json.chat_id }}",
                "text": "={{ $json.output }}",
                "additionalFields": {"parse_mode": "HTML"}
            },
            "credentials": {"telegramApi": {"name": "Telegram EgakatOpsBot"}}
        },
        {
            "id": "n9", "name": "Sticky Note",
            "type": "n8n-nodes-base.stickyNote", "typeVersion": 1,
            "position": [-1900, 100],
            "parameters": {
                "content": (
                    "## Egakat Ops Bot — WMS Intelligence v1\n\n"
                    "**Sprint 1:** Estado pipeline WMS del día\n"
                    "**Sprint 2:** Fill Rate / OTIF\n"
                    "**Sprint 3:** Productividad\n\n"
                    "**Variables .env requeridas:**\n"
                    "- TELEGRAM_ID_PERSONAL\n"
                    "- TELEGRAM_GRUPO_OPS_ID (en Softnet_Ventas/.env)\n"
                    "- API_OPS_SECRET\n\n"
                    "**Tras activar:** Publish → registrar webhook manualmente\n"
                    f"Grupo Ops: {GRUPO_OPS_ID} ✅\n"
                    f"Chat admin: {CHAT_ID_PERSONAL} ✅"
                ),
                "height": 320, "width": 440, "color": 3
            }
        }
    ],
    "connections": {
        "Telegram Trigger":      {"main": [[{"node": "Es mencion o privado?", "type": "main", "index": 0}]]},
        "Es mencion o privado?": {"main": [[{"node": "Es chat autorizado?", "type": "main", "index": 0}], []]},
        "Es chat autorizado?":   {"main": [
            [{"node": "Limpiar mensaje", "type": "main", "index": 0}],
            [{"node": "No Autorizado Ops", "type": "main", "index": 0}]
        ]},
        "Limpiar mensaje":       {"main": [[{"node": "Obtener Estado WMS", "type": "main", "index": 0}]]},
        "Obtener Estado WMS":    {"main": [[{"node": "Agente Ops Egakat", "type": "main", "index": 0}]]},
        "Agente Ops Egakat":     {"main": [[{"node": "Enviar Respuesta", "type": "main", "index": 0}]]},
        "Modelo OpenAI":         {"ai_languageModel": [[{"node": "Agente Ops Egakat", "type": "ai_languageModel", "index": 0}]]},
        "Memoria por Chat":      {"ai_memory": [[{"node": "Agente Ops Egakat", "type": "ai_memory", "index": 0}]]},
    },
    "settings": {"executionOrder": "v1"}
}

out = Path(__file__).resolve().parent / "wf_bot_ops.json"
out.write_text(json.dumps(wf, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"OK — {out}")
print(f"Grupo Ops ID : {GRUPO_OPS_ID}")
print(f"Chat personal: {CHAT_ID_PERSONAL}")
