"""
Crea borrador Outlook para Franco Perez con instrucciones LimeSurvey.
"""
import pythoncom, win32com.client
pythoncom.CoInitialize()

try:
    outlook = win32com.client.GetActiveObject("Outlook.Application")
except:
    outlook = win32com.client.Dispatch("Outlook.Application")

CUERPO = """\
Hola Franco,

Te paso los ajustes que necesitamos hacer en las dos encuestas de LimeSurvey. Son cambios puntuales y no deberian tomar mas de 20-30 minutos en total.

──────────────────────────────────────────────
ENCUESTA NPS — ID 418429 ("¿Nos recomendarias?")
──────────────────────────────────────────────

1. Activar Tabla de Participantes (Tokens)

   Configuracion de encuesta → Participantes → activar "Encuesta cerrada"
   Luego en Participantes → Atributos personalizados → agregar:
     - Atributo 1: Empresa
     - Atributo 2: Cargo

   Con esto, cuando enviemos la encuesta por email, LimeSurvey ya sabe quien
   es cada cliente y no necesitamos pedirle sus datos dentro de la encuesta.

2. Simplificar a 2 preguntas

   Como los datos del participante los toma de los tokens, las preguntas de
   contacto (G01Q04 y G01Q05) ya no son necesarias. La encuesta queda con:

     - Q00: Score 0-10 (ya esta correcto, mantener)
     - G01Q02: Reemplazar la seleccion multiple de criterios por un texto
               libre con la pregunta: "¿Cual es la principal razon de tu
               puntuacion?" — marcarla como opcional.
     - G01Q03, G01Q04, G01Q05: eliminar o desactivar.

   Resultado: encuesta de 2 preguntas, menos de 1 minuto para responder.

──────────────────────────────────────────────
ENCUESTA CSAT — ID 386641 ("Satisfaccion mensual")
──────────────────────────────────────────────

3. Agregar skip logic (Relevance equation) en 3 preguntas

   Las preguntas sobre resolucion de problemas solo deben aparecer si el
   cliente indico que tuvo un problema (G01Q04 = Si). Para ocultarlas
   cuando no corresponde:

   Editar G01Q05 → campo "Relevance equation" → escribir:
     {G01Q04} == "Y"

   Repetir exactamente lo mismo en G01Q11 y en G01Q06.

   Con esto, si el cliente responde "No" en G01Q04, esas 3 preguntas
   desaparecen automaticamente y va directo a G01Q14.

4. Agregar campos de identificacion del encuestado

   Similar a NPS, conviene activar tokens tambien en esta encuesta o
   agregar 2 preguntas al final:
     - Empresa / Razon social
     - Cargo

   Si prefieres hacerlo via tokens (misma logica que NPS), tambien funciona.

──────────────────────────────────────────────
FRECUENCIAS DE ENVIO (cuando lo configuremos)
──────────────────────────────────────────────

   - NPS:  trimestral (Marzo, Junio, Septiembre, Diciembre)
   - CSAT: mensual (primeros 5 dias de cada mes)

Cualquier duda me avisas. Si quieres lo revisamos juntos en 15 minutos.

Saludos,
Socrates Cabral
Control Management & Mejora Continua
Egakat SPA
"""

mail = outlook.CreateItem(0)
mail.To      = "franco.perez@egakat.cl"
mail.Subject = "LimeSurvey — ajustes encuestas NPS y CSAT"
mail.Body    = CUERPO
mail.Save()

print("Borrador guardado en Outlook.")
print("  Para: franco.perez@egakat.cl")
print("  Asunto: LimeSurvey — ajustes encuestas NPS y CSAT")
