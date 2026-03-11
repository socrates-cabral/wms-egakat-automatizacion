"""
Crea un borrador en Outlook con la respuesta a José Contreras (TI).
Requiere Outlook desktop instalado y cuenta egakat configurada.
"""

import win32com.client
from pathlib import Path

DESTINATARIO = "jcontreras@tinetservices.cl"
ASUNTO = "RE: App Registration Azure AD — documentación e información adicional"
ADJUNTO = str(Path(r"C:\ClaudeWork\Solicitudes_IT\Respuesta_Jose_Contreras_AppRegistration.docx"))

CUERPO = """\
Hola José,

Gracias por revisar el tema y por el feedback, con gusto te paso la información que pediste.

Para el registro de la app y la autenticación sin usuario (client credentials flow), la documentación oficial de Microsoft está acá:

- Registrar una aplicación en Azure AD (Entra ID):
  https://learn.microsoft.com/es-es/entra/identity-platform/quickstart-register-app

- Configurar acceso de aplicación a SharePoint (App-Only):
  https://learn.microsoft.com/es-es/sharepoint/dev/solution-guidance/security-apponly-azureacs

- Flujo OAuth2 client credentials (sin usuario interactivo):
  https://learn.microsoft.com/es-es/azure/active-directory/develop/v2-oauth2-client-creds-grant-flow

- Permiso Sites.Selected (acceso acotado a un sitio específico):
  https://learn.microsoft.com/es-es/graph/permissions-reference#sitesselected


Sobre los permisos — no se necesita admin global de SharePoint

Entiendo que el punto de preocupación es darle perfil de admin de SharePoint a la app. En realidad eso no es necesario. El script usa el permiso Sites.Selected, que es justamente la opción que Microsoft recomienda para este tipo de integraciones: le das acceso únicamente al sitio que necesitas, no a todo el tenant.

Los dos permisos de aplicación requeridos son:
  - Sites.Selected: acceso solo al sitio específico, nada más.
  - Files.ReadWrite: para subir y leer archivos en la librería de documentos del sitio.


El script

Te adjunto el documento con el detalle completo. En resumen: el script se conecta a Azure AD usando client_id y client_secret (los genera Azure al registrar la app) y sube los reportes Excel al sitio https://egakatcom.sharepoint.com/sites/DatosparaDashboard. Las credenciales no están hardcodeadas en el código, las lee desde un archivo .env local en mi equipo.

Lo que necesitaría de TI:
  1. Registrar la app en Azure AD Entra y obtener el client_id y client_secret.
  2. Conceder el consentimiento de administrador para Sites.Selected y Files.ReadWrite en el sitio específico.
  3. Pasarme las credenciales a socrates.cabral@egakat.cl.

Si necesitas que revisemos algo juntos o tienes alguna duda del script, con gusto coordinamos una llamada corta. Quedo atento.

Saludos,
Sócrates Cabral
Control Management & Mejora Continua
Egakat SPA
"""

def crear_borrador():
    import pythoncom
    pythoncom.CoInitialize()
    try:
        outlook = win32com.client.GetActiveObject("Outlook.Application")
    except Exception:
        outlook = win32com.client.Dispatch("Outlook.Application")
    mail = outlook.CreateItem(0)  # 0 = olMailItem

    mail.To = DESTINATARIO
    mail.Subject = ASUNTO
    mail.Body = CUERPO
    mail.SentOnBehalfOfName = "socrates.cabral@egakat.cl"

    # Adjuntar el Word si existe
    adjunto_path = Path(ADJUNTO)
    if adjunto_path.exists():
        mail.Attachments.Add(str(adjunto_path))
        print(f"Adjunto agregado: {adjunto_path.name}")
    else:
        print(f"AVISO: No se encontro el adjunto en {ADJUNTO}")

    mail.Save()  # Guarda como borrador
    print("Borrador guardado en Outlook correctamente.")
    print(f"  Para: {DESTINATARIO}")
    print(f"  Asunto: {ASUNTO}")

if __name__ == "__main__":
    crear_borrador()
