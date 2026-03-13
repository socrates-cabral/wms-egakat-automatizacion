import os
import base64
import numpy as np
import soundfile as sf
from dotenv import load_dotenv
from openai import OpenAI
from datetime import datetime

# ============================================================================
# CONFIGURACIÓN INICIAL
# ============================================================================

# Cargar variables del archivo .env
load_dotenv()

# Verificar que existe la API Key
api_key = os.getenv("DASHSCOPE_API_KEY")
if not api_key:
    raise ValueError("❌ No se encontró DASHSCOPE_API_KEY en el archivo .env")

# Inicializar cliente OpenAI (compatible con DashScope)
client = OpenAI(
    api_key=api_key,
    base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
)

# ============================================================================
# CONFIGURACIÓN DE AUDIO
# ============================================================================

VOICE_CONFIG = {
    "voice": "Cherry",
    "format": "wav",
    "samplerate": 24000
}

# Carpeta de salida para los audios generados
AUDIO_DIR = "audio"

# ============================================================================
# CONFIGURACIÓN DEL ASISTENTE
# ============================================================================

class AsistenteQwen:
    def __init__(self, con_audio=True):
        self.con_audio = con_audio
        self.mensajes = []
        self.contador_turnos = 0
        self.total_tokens = 0
        
        # Mensaje del sistema para definir la personalidad
        self.mensajes.append({
            "role": "system",
            "content": "Eres un asistente útil, amigable y conciso. Responde de manera clara y natural. Si te preguntan algo que no sabes, sé honesto."
        })
        
        print("\n" + "=" * 70)
        print("🤖 ASISTENTE QWEN3-OMNI - Modo Conversacional")
        print("=" * 70)
        print(f"🎤 Audio: {'✅ Activado' if self.con_audio else '❌ Desactivado'}")
        print(f"🎵 Voz: {VOICE_CONFIG['voice']}")
        print(f"📁 Carpeta de audio: {AUDIO_DIR}")
        print("=" * 70)
        print("\n📋 COMANDOS DISPONIBLES:")

        # Asegurar que exista la carpeta de audio
        os.makedirs(AUDIO_DIR, exist_ok=True)
        print("   /salir o /quit       - Salir del asistente")
        print("   /limpiar o /clear    - Limpiar historial de conversación")
        print("   /audio on/off        - Activar/desactivar audio")
        print("   /voz [nombre]        - Cambiar voz (ej: /voz Serena)")
        print("   /historial           - Ver historial de conversación")
        print("   /tokens              - Ver uso de tokens")
        print("   /ayuda o /help       - Mostrar esta ayuda")
        print("=" * 70)
        print("\n💬 Escribe tu mensaje y presiona Enter para chatear.\n")

    def enviar_mensaje(self, mensaje_usuario):
        """Envía un mensaje al modelo y recibe la respuesta"""
        
        # Agregar mensaje del usuario al historial
        self.mensajes.append({
            "role": "user",
            "content": mensaje_usuario
        })
        
        try:
            # Configurar modalidades según estado del audio
            modalidades = ["text", "audio"] if self.con_audio else ["text"]
            
            # Crear solicitud
            completion = client.chat.completions.create(
                model="qwen3-omni-flash",
                messages=self.mensajes,
                modalities=modalidades,
                audio={
                    "voice": VOICE_CONFIG["voice"],
                    "format": VOICE_CONFIG["format"]
                } if self.con_audio else None,
                stream=True,
                stream_options={"include_usage": True},
            )

            # Variables para acumular respuesta
            respuesta_texto = ""
            audio_base64 = ""
            
            print("\n🤖 IA: ", end="", flush=True)
            
            # Procesar streaming
            for chunk in completion:
                if chunk.choices:
                    delta = chunk.choices[0].delta
                    
                    # Texto
                    if hasattr(delta, "content") and delta.content:
                        print(delta.content, end="", flush=True)
                        respuesta_texto += delta.content
                    
                    # Audio
                    if self.con_audio and hasattr(delta, "audio") and delta.audio:
                        audio_data = delta.audio.get("data", "")
                        if audio_data:
                            audio_base64 += audio_data
                
                # Uso de tokens
                elif hasattr(chunk, "usage") and chunk.usage:
                    self.total_tokens += chunk.usage.total_tokens
            
            print()  # Nueva línea después de la respuesta
            
            # Agregar respuesta al historial
            self.mensajes.append({
                "role": "assistant",
                "content": respuesta_texto
            })
            
            self.contador_turnos += 1
            
            # Guardar audio si está activado
            if self.con_audio and audio_base64:
                self._guardar_audio(audio_base64, self.contador_turnos)
            
            return respuesta_texto

        except Exception as e:
            print(f"\n❌ Error: {str(e)}")
            # Remover último mensaje si hubo error
            self.mensajes.pop()
            return None

    def _guardar_audio(self, audio_base64, turno):
        """Guarda el audio en un archivo WAV"""
        try:
            wav_bytes = base64.b64decode(audio_base64)
            audio_np = np.frombuffer(wav_bytes, dtype=np.int16)
            
            # Nombre del archivo con timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = os.path.join(AUDIO_DIR, f"audio_turno_{turno:03d}_{timestamp}.wav")
            
            sf.write(output_file, audio_np, samplerate=VOICE_CONFIG["samplerate"])
            print(f"   🎵 Audio guardado: {output_file}")
            
        except Exception as e:
            print(f"   ⚠️ Error al guardar audio: {str(e)}")

    def mostrar_historial(self):
        """Muestra el historial de conversación"""
        print("\n" + "=" * 70)
        print("📜 HISTORIAL DE CONVERSACIÓN")
        print("=" * 70)
        
        for i, msg in enumerate(self.mensajes):
            if msg["role"] == "system":
                continue
            emoji = "👤" if msg["role"] == "user" else "🤖"
            print(f"\n{emoji} Turno {(i//2)+1}:")
            print(f"   {msg['content'][:200]}{'...' if len(msg['content']) > 200 else ''}")
        
        print("=" * 70)

    def mostrar_tokens(self):
        """Muestra el uso de tokens"""
        print("\n" + "=" * 70)
        print("📊 USO DE TOKENS")
        print("=" * 70)
        print(f"   Turnos conversados: {self.contador_turnos}")
        print(f"   Tokens totales: {self.total_tokens}")
        print(f"   Mensajes en historial: {len(self.mensajes) - 1}")  # -1 system
        print("=" * 70)

    def limpiar_historial(self):
        """Limpia el historial manteniendo el mensaje del sistema"""
        self.mensajes = [self.mensajes[0]]  # Mantener solo system
        self.contador_turnos = 0
        print("\n✅ Historial limpiado. Nueva conversación iniciada.\n")

    def ejecutar(self):
        """Bucle principal del asistente"""
        
        while True:
            try:
                # Obtener input del usuario
                entrada = input("\n👤 Tú: ").strip()
                
                if not entrada:
                    continue
                
                # Procesar comandos
                if entrada.lower() in ["/salir", "/quit", "salir", "quit"]:
                    print("\n👋 ¡Hasta luego! Fue un placer conversar contigo.")
                    self.mostrar_tokens()
                    break
                
                elif entrada.lower() in ["/limpiar", "/clear", "limpiar", "clear"]:
                    self.limpiar_historial()
                    continue
                
                elif entrada.lower().startswith("/audio"):
                    partes = entrada.split()
                    if len(partes) > 1:
                        if partes[1].lower() == "on":
                            self.con_audio = True
                            print("\n✅ Audio activado.")
                        elif partes[1].lower() == "off":
                            self.con_audio = False
                            print("\n❌ Audio desactivado.")
                    else:
                        estado = "✅ Activado" if self.con_audio else "❌ Desactivado"
                        print(f"\n🎤 Estado actual del audio: {estado}")
                    continue
                
                elif entrada.lower().startswith("/voz"):
                    partes = entrada.split()
                    if len(partes) > 1:
                        nueva_voz = partes[1]
                        VOICE_CONFIG["voice"] = nueva_voz
                        print(f"\n✅ Voz cambiada a: {nueva_voz}")
                    else:
                        print(f"\n🎤 Voz actual: {VOICE_CONFIG['voice']}")
                    continue
                
                elif entrada.lower() in ["/historial", "/history"]:
                    self.mostrar_historial()
                    continue
                
                elif entrada.lower() in ["/tokens", "/uso"]:
                    self.mostrar_tokens()
                    continue
                
                elif entrada.lower() in ["/ayuda", "/help", "ayuda", "help"]:
                    print("\n📋 COMANDOS DISPONIBLES:")
                    print("   /salir o /quit       - Salir del asistente")
                    print("   /limpiar o /clear    - Limpiar historial")
                    print("   /audio on/off        - Activar/desactivar audio")
                    print("   /voz [nombre]        - Cambiar voz")
                    print("   /historial           - Ver conversación")
                    print("   /tokens              - Ver uso de tokens")
                    print("   /ayuda o /help       - Mostrar esta ayuda")
                    continue
                
                # Enviar mensaje normal
                self.enviar_mensaje(entrada)

            except KeyboardInterrupt:
                print("\n\n⚠️ Interrumpido por el usuario.")
                self.mostrar_tokens()
                break
            except Exception as e:
                print(f"\n❌ Error inesperado: {str(e)}")

# ============================================================================
# EJECUCIÓN PRINCIPAL
# ============================================================================

if __name__ == '__main__':
    import sys
    
    # Modo de ejecución
    con_audio = True
    if len(sys.argv) > 1 and sys.argv[1] == "--texto":
        con_audio = False
        print(" Iniciando en modo SOLO TEXTO...")
    else:
        print("🚀 Iniciando en modo TEXTO + AUDIO...")
    
    # Crear y ejecutar asistente
    asistente = AsistenteQwen(con_audio=con_audio)
    asistente.ejecutar()
