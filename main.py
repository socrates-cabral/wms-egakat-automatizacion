import os
import json
try:
    import readline
except ImportError:
    import pyreadline3 as readline
from dotenv import load_dotenv
import dashscope
from dashscope import Generation
import requests  # Para integración con APIs

# 1. Configuración de rutas y .env
ENV_PATH = os.path.join(os.path.dirname(__file__), ".env")

def ensure_dotenv():
    if not os.path.exists(ENV_PATH):
        with open(ENV_PATH, "w", encoding="utf-8") as f:
            f.write("# Configuración de DashScope\n")
            f.write("DASHSCOPE_API_KEY=tu_api_key_aqui\n")
            f.write("OWNER_ACCOUNT=tu_owner_account_aqui\n")
        raise SystemExit(
            "✅ Se creó un archivo .env de ejemplo.\n" 
            "Edita el archivo (agrega tu API key) y vuelve a ejecutar el script."
        )
    load_dotenv(dotenv_path=ENV_PATH, override=True)

# 2. Cargar credenciales
ensure_dotenv()
api_key = os.getenv("DASHSCOPE_API_KEY")
owner_account = os.getenv("OWNER_ACCOUNT")

# 3. Limpiar y validar API Key
if api_key:
    api_key = api_key.strip().strip('"').strip("'")

if not api_key:
    raise ValueError("No se encontró la API KEY. Revisa tu archivo .env")

# 4. Configurar SDK de DashScope
dashscope.api_key = api_key
dashscope.base_http_api_url = "https://dashscope-intl.aliyuncs.com/api/v1/"

# Variables globales para mejoras
messages = [{"role": "system", "content": "Eres un asistente útil."}]
alias_dict = {"ls": "echo 'listado simulado'", "hola": "consultar_modelo('Hola, ¿cómo estás?')"}
HIST_FILE = os.path.join(os.path.dirname(__file__), "historial.txt")

def consultar_modelo(mensaje_usuario, modelo="qwen-plus"):
    """
    Envía un mensaje al modelo y devuelve la respuesta.
    
    Args:
        mensaje_usuario: El mensaje del usuario
        modelo: Nombre del modelo (qwen-plus, qwen-turbo, qwen-max, etc.)
    
    Returns:
        str: Respuesta del modelo o None si hay error
    """
    try:
        headers = {}
        if owner_account:
            headers["owner-account"] = owner_account
        
        # Usar historial de conversación
        current_messages = messages + [{"role": "user", "content": mensaje_usuario}]
        
        response = Generation.call(
            model=modelo,
            messages=current_messages,
            headers=headers
        )
        
        if getattr(response, "status_code", None) == 200:
            respuesta = response.output.text
            messages.append({"role": "user", "content": mensaje_usuario})
            messages.append({"role": "assistant", "content": respuesta})
            return respuesta
        else:
            print(f"❌ Error: {response.code} - {response.message}")
            return None
            
    except Exception as e:
        print(f"❌ Error de conexión: {str(e)}")
        return None

# Función para autocompletado
def completar_comando(text, state):
    comandos = ["salir", "exit", "quit", "load", "alias", "historial", "clear", "api"] + list(alias_dict.keys())
    matches = [cmd for cmd in comandos if cmd.startswith(text)]
    return matches[state] if state < len(matches) else None

if __name__ == '__main__':
    # Configurar readline para historial y autocompletado
    if os.path.exists(HIST_FILE):
        readline.read_history_file(HIST_FILE)
    readline.set_completer(completar_comando)
    readline.parse_and_bind("tab: complete")
    
    print("🤖 Asistente DashScope - Qwen Plus (Mejorado)")
    print("=" * 50)
    print("Comandos disponibles: salir, load <archivo.json>, api <url>, alias <clave> <valor>, historial, clear")
    print("Usa flechas ↑/↓ para historial de comandos, Tab para autocompletado.")
    
    while True:
        try:
            usuario = input("\n👤 Tú: ").strip()
            if not usuario:
                continue
            
            # Procesar alias
            if usuario in alias_dict:
                usuario = alias_dict[usuario]
            
            # Procesar comandos especiales
            partes = usuario.split(" ", 1)
            comando = partes[0].lower()
            args = partes[1] if len(partes) > 1 else ""
            
            if comando in ['salir', 'exit', 'quit']:
                print("👋 ¡Hasta luego!")
                break
            elif comando == "load" and args.endswith(".json"):
                try:
                    with open(args, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        print(f"✅ Cargado: {data}")
                        # Opcional: usar data en messages o configuración
                except FileNotFoundError:
                    print("❌ Archivo no encontrado.")
                except json.JSONDecodeError:
                    print("❌ Error al parsear JSON.")
            elif comando == "api" and args:
                try:
                    response = requests.get(args)
                    if response.status_code == 200:
                        print(f"✅ Respuesta API: {response.json()}")
                    else:
                        print(f"❌ Error API: {response.status_code}")
                except Exception as e:
                    print(f"❌ Error API: {e}")
            elif comando == "alias" and args:
                subpartes = args.split(" ", 1)
                if len(subpartes) == 2:
                    clave, valor = subpartes
                    alias_dict[clave] = valor
                    print(f"✅ Alias agregado: {clave} → {valor}")
                else:
                    print("❌ Uso: alias <clave> <valor>")
            elif comando == "historial":
                print("📜 Historial de conversación:")
                for msg in messages[-10:]:  # Últimos 10 mensajes
                    print(f"{msg['role'].capitalize()}: {msg['content']}")
            elif comando == "clear":
                messages[:] = [{"role": "system", "content": "Eres un asistente útil."}]
                print("✅ Historial de conversación limpiado.")
            else:
                # Procesar como mensaje normal
                print("🤖 IA: ", end="", flush=True)
                respuesta = consultar_modelo(usuario)
                if respuesta:
                    print(respuesta)
        
        except KeyboardInterrupt:
            print("\n👋 ¡Hasta luego!")
            break
    
    # Guardar historial al salir
    readline.write_history_file(HIST_FILE)
