import os
import base64
import numpy as np
import soundfile as sf
from dotenv import load_dotenv
from openai import OpenAI

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
    # Singapore region (internacional)
    base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
)

# ============================================================================
# CONFIGURACIÓN DE AUDIO
# ============================================================================

VOICE_CONFIG = {
    "voice": "Cherry",      # Voz femenina alegre y amigable
    "format": "wav",        # Formato de audio (solo wav soportado)
    "samplerate": 24000     # Frecuencia de muestreo
}

# ============================================================================
# FUNCIÓN PRINCIPAL - TEXTO + AUDIO
# ============================================================================

def probar_qwen_omni_con_audio():
    """
    Prueba el modelo Qwen3-Omni-Flash con salida de texto y audio.
    Guarda el audio en un archivo WAV.
    """
    print("🤖 Qwen3-Omni Flash - Prueba con Audio")
    print("=" * 60)
    print(f"🔑 API Key: {api_key[:10]}... (oculta)")
    print(f"🎤 Voz: {VOICE_CONFIG['voice']}")
    print(f"📁 Audio guardado: respuesta_omni.wav")
    print("=" * 60)
    
    # Variables para acumular respuesta
    full_text_response = ""
    audio_base64_string = ""
    
    try:
        # ====================================================================
        # CREAR SOLICITUD (STREAMING OBLIGATORIO)
        # ====================================================================
        completion = client.chat.completions.create(
            model="qwen3-omni-flash",
            messages=[
                {"role": "system", "content": "Eres un asistente útil y amigable. Responde de manera concisa."},
                {"role": "user", "content": "Hola, ¿qué modelo eres y qué puedes hacer?"}
            ],
            # Modalidades: texto + audio
            modalities=["text", "audio"],
            # Configuración de audio
            audio={
                "voice": VOICE_CONFIG["voice"],
                "format": VOICE_CONFIG["format"]
            },
            # ⚠️ STREAMING OBLIGATORIO PARA QWEN-OMNI
            stream=True,
            stream_options={"include_usage": True},
        )

        print("\n📝 Respuesta del modelo:\n")
        
        # ====================================================================
        # PROCESAR RESPUESTA STREAMING
        # ====================================================================
        for chunk in completion:
            if chunk.choices:
                delta = chunk.choices[0].delta
                
                # Procesar texto
                if hasattr(delta, "content") and delta.content:
                    print(delta.content, end="", flush=True)
                    full_text_response += delta.content
                
                # Procesar audio (acumular base64)
                if hasattr(delta, "audio") and delta.audio:
                    audio_data = delta.audio.get("data", "")
                    if audio_data:
                        audio_base64_string += audio_data
            
            # Mostrar uso de tokens al final
            elif hasattr(chunk, "usage") and chunk.usage:
                print(f"\n\n📊 Uso de tokens:")
                print(f"   Prompt: {chunk.usage.prompt_tokens}")
                print(f"   Completado: {chunk.usage.completion_tokens}")
                print(f"   Total: {chunk.usage.total_tokens}")

        # ====================================================================
        # GUARDAR AUDIO
        # ====================================================================
        print("\n")
        
        if audio_base64_string:
            print("🔄 Decodificando audio...")
            try:
                # Decodificar Base64 a bytes
                wav_bytes = base64.b64decode(audio_base64_string)
                
                # Convertir a numpy array (int16 para WAV)
                audio_np = np.frombuffer(wav_bytes, dtype=np.int16)
                
                # Guardar archivo WAV
                output_file = "respuesta_omni.wav"
                sf.write(output_file, audio_np, samplerate=VOICE_CONFIG["samplerate"])
                
                print(f"✅ Audio guardado exitosamente: {output_file}")
                print(f"📊 Duración aproximada: {len(audio_np) / VOICE_CONFIG['samplerate']:.2f} segundos")
                
            except Exception as audio_error:
                print(f"⚠️ Error al guardar audio: {str(audio_error)}")
                # Guardar raw base64 para debug
                with open("audio_debug.txt", "w", encoding="utf-8") as f:
                    f.write(audio_base64_string)
                print("📄 Base64 raw guardado en: audio_debug.txt")
        else:
            print("⚠️ No se recibió audio en la respuesta")
            print("   Verifica que modalities incluya 'audio'")

        print("\n" + "=" * 60)
        print("✅ ¡Prueba completada exitosamente!")
        print("=" * 60)
        
        return full_text_response

    except Exception as e:
        print(f"\n❌ Error en la solicitud: {str(e)}")
        print("\n🔍 Posibles causas:")
        print("   1. API Key inválida o expirada")
        print("   2. Modelo no disponible en tu región")
        print("   3. Problema de conexión a internet")
        print("   4. Cuota gratuita agotada")
        raise

# ============================================================================
# FUNCIÓN - SOLO TEXTO (más rápido)
# ============================================================================

def probar_qwen_omni_solo_texto():
    """
    Prueba el modelo Qwen3-Omni-Flash solo con texto (más rápido).
    """
    print("🤖 Qwen3-Omni Flash - Prueba Solo Texto")
    print("=" * 60)
    
    full_text_response = ""
    
    try:
        completion = client.chat.completions.create(
            model="qwen3-omni-flash",
            messages=[
                {"role": "user", "content": "Hola, ¿qué modelo eres?"}
            ],
            modalities=["text"],  # Solo texto
            stream=True,
            stream_options={"include_usage": True},
        )

        print("\n📝 Respuesta:\n")
        
        for chunk in completion:
            if chunk.choices and chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                print(content, end="", flush=True)
                full_text_response += content
        
        print("\n\n✅ ¡Conexión exitosa!")
        return full_text_response

    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        raise

# ============================================================================
# EJECUCIÓN PRINCIPAL
# ============================================================================

if __name__ == '__main__':
    import sys
    
    # Modo de ejecución
    if len(sys.argv) > 1 and sys.argv[1] == "--texto":
        # Solo texto (más rápido)
        probar_qwen_omni_solo_texto()
    else:
        # Texto + Audio (completo)
        probar_qwen_omni_con_audio()
