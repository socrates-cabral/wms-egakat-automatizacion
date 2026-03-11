"""
generador.py — Agente Generador de Scripts Egakat
Genera, mejora y documenta scripts Python desde requerimientos en texto.

Uso CLI:
    py AI_Agent/agentes/generador.py nuevo    "descargar reporte devoluciones WMS a OneDrive"
    py AI_Agent/agentes/generador.py mejorar  "wms_descarga.py" "agregar reintentos en caso de timeout"
    py AI_Agent/agentes/generador.py documentar "staging_descarga.py"
    py AI_Agent/agentes/generador.py tarea    "nuevo_script.py" --hora "08:00" --frecuencia diaria
    py AI_Agent/agentes/generador.py revisar  "script.py"

Uso como módulo:
    from agentes.generador import generar_script, mejorar_script
"""
import sys
sys.stdout.reconfigure(encoding="utf-8")

import os
import re
import argparse
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent.parent.parent
load_dotenv(dotenv_path=BASE_DIR / ".env")

MAX_CONTEXT = 4500   # chars de código existente enviados a Claude

# ── Contexto Egakat para el generador ────────────────────────────────────────
CONTEXTO_EGAKAT = """
Eres un experto en automatización Python para Egakat SPA, empresa 3PL chilena.

REGLAS OBLIGATORIAS para todo script generado:
1. Primera línea siempre: import sys / sys.stdout.reconfigure(encoding="utf-8")
2. Credenciales SIEMPRE desde .env con python-dotenv — NUNCA hardcodeadas
3. Usar pathlib.Path para rutas — nunca strings crudos
4. Destino archivos: OneDrive sincronizado local, nunca C:\\ClaudeWork\\Reportes
5. Logs con timestamp — función log() estándar del proyecto
6. Playwright siempre headless=True y con timeout explícito (mínimo 60000ms)
7. Manejo de errores con try/except y log del error
8. Al final del script: bloque if __name__ == "__main__" con resumen de ejecución

STACK DISPONIBLE:
- Playwright (automatización web WMS)
- openpyxl (Excel lectura/escritura)
- pandas (análisis de datos)
- python-dotenv (.env)
- requests (HTTP)
- pdfplumber (PDF)
- pyodbc / sqlite3 (SQL)
- python-docx / python-pptx (documentos)
- anthropic (Claude API)

VARIABLES .env DISPONIBLES (usar os.getenv):
- WMS_USER, WMS_PASSWORD → portal WMS Softland
- LIMESURVEY_USER, LIMESURVEY_PASSWORD, LIMESURVEY_URL → LimeSurvey API
- ANTHROPIC_API_KEY → Claude API
- ONEDRIVE_BASE → ruta base OneDrive

RUTAS ONEDRIVE ESTÁNDAR:
- Stock WMS: OneDrive/Datos para Dashboard - Stock WMS Semanal/{Quilicura|Pudahuel}/
- Posiciones: OneDrive/Datos para Dashboard - Consulta de Posiciones/
- Staging: OneDrive/Datos para Dashboard - Stagin IN- OUT/{Quilicura|Pudahuel}/
- VDR: OneDrive/Reportes VDR/
- NPS: OneDrive/Reportes NPS/

URL WMS: https://egakatwms.cl/sglwms_EGA_prod/hinicio.aspx
Función log() estándar:
def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

PATRÓN LOGIN WMS (Playwright):
browser = playwright.chromium.launch(headless=True)
context = browser.new_context(accept_downloads=True)
page = context.new_page()
page.goto(URL_WMS, timeout=60000)
page.fill("#vUSUARIO", os.getenv("WMS_USER"))
page.fill("#vPASSWORD", os.getenv("WMS_PASSWORD"))
page.click("input[type='submit']")
"""


# ══════════════════════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _buscar_archivo(nombre: str) -> Path | None:
    p = Path(nombre)
    if p.exists():
        return p
    for encontrado in BASE_DIR.rglob(Path(nombre).name):
        return encontrado
    return None


def _leer_codigo(ruta: Path) -> str:
    """Lee código y lo trunca para no saturar contexto."""
    contenido = ruta.read_text(encoding="utf-8", errors="ignore")
    if len(contenido) > MAX_CONTEXT:
        return contenido[:MAX_CONTEXT] + f"\n\n... [truncado — {len(contenido)} chars totales]"
    return contenido


def _sanitizar(texto: str) -> str:
    """Redacta valores sensibles antes de enviar a Claude."""
    return re.sub(
        r'(password|passwd|secret|api_key|token|client_secret)\s*[=:]\s*\S+',
        lambda m: m.group(1) + "=[REDACTED]",
        texto, flags=re.IGNORECASE
    )


def _claude(prompt: str, max_tokens: int = 2500) -> str:
    from anthropic import Anthropic
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        return "ERROR: ANTHROPIC_API_KEY no está en .env"
    client = Anthropic(api_key=api_key)
    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=max_tokens,
        system=CONTEXTO_EGAKAT,
        messages=[{"role": "user", "content": prompt}]
    )
    return resp.content[0].text


def _extraer_codigo(texto: str) -> str:
    """Extrae bloque de código Python de la respuesta de Claude."""
    match = re.search(r"```python\n(.*?)```", texto, re.DOTALL)
    if match:
        return match.group(1).strip()
    # Si no hay bloque, devolver todo
    return texto.strip()


def _guardar_script(codigo: str, nombre: str, carpeta: str = None) -> Path:
    """Guarda el script generado en la carpeta correcta."""
    if carpeta:
        destino = BASE_DIR / carpeta
    else:
        # Inferir carpeta según nombre
        nombre_lower = nombre.lower()
        if any(k in nombre_lower for k in ["wms", "posicion", "staging"]):
            destino = BASE_DIR / "WMS_Automatizacion"
        elif "vdr" in nombre_lower:
            destino = BASE_DIR / "VDR_Comparador"
        elif "nps" in nombre_lower or "csat" in nombre_lower:
            destino = BASE_DIR / "NPS_Encuesta"
        else:
            destino = BASE_DIR / "AI_Agent" / "agentes"

    destino.mkdir(exist_ok=True)
    if not nombre.endswith(".py"):
        nombre += ".py"
    ruta = destino / nombre
    ruta.write_text(codigo, encoding="utf-8")
    return ruta


# ══════════════════════════════════════════════════════════════════════════════
#  FUNCIONES PRINCIPALES
# ══════════════════════════════════════════════════════════════════════════════

def generar_script(requerimiento: str, guardar_como: str = None) -> dict:
    """
    Genera un script Python completo desde un requerimiento en texto.
    Aplica todas las convenciones Egakat automáticamente.
    """
    prompt = (
        f"Genera un script Python completo y funcional para Egakat SPA con este requerimiento:\n\n"
        f"{requerimiento}\n\n"
        f"Requisitos:\n"
        f"- Script completo, listo para ejecutar con `py nombre.py`\n"
        f"- Aplica TODAS las reglas obligatorias del contexto Egakat\n"
        f"- Incluye función log() con timestamp\n"
        f"- Incluye manejo de errores\n"
        f"- Al final, sugiere un nombre de archivo apropiado en formato: nombre_script.py\n"
        f"- Devuelve SOLO el código Python dentro de un bloque ```python```\n"
    )

    respuesta = _claude(prompt, max_tokens=3000)
    codigo    = _extraer_codigo(respuesta)

    # Inferir nombre si no se dio
    if not guardar_como:
        # Buscar sugerencia en la respuesta
        match = re.search(r'#\s*(?:archivo|nombre|file):\s*(\w+\.py)', respuesta, re.IGNORECASE)
        guardar_como = match.group(1) if match else "script_generado.py"

    ruta = _guardar_script(codigo, guardar_como)

    return {
        "script":    codigo,
        "guardado":  str(ruta),
        "nombre":    ruta.name,
        "mensaje":   f"✅ Script generado: {ruta}\n   Ejecutar con: py {ruta.relative_to(BASE_DIR)}",
    }


def mejorar_script(archivo: str, instruccion: str) -> dict:
    """Mejora un script existente según la instrucción dada."""
    ruta = _buscar_archivo(archivo)
    if not ruta:
        return {"error": f"Archivo no encontrado: {archivo}"}

    codigo_actual = _sanitizar(_leer_codigo(ruta))

    prompt = (
        f"Mejora este script Python de Egakat SPA:\n\n"
        f"```python\n{codigo_actual}\n```\n\n"
        f"Instrucción de mejora: {instruccion}\n\n"
        f"Reglas:\n"
        f"- Mantén todas las convenciones Egakat existentes\n"
        f"- Solo modifica lo necesario para cumplir la instrucción\n"
        f"- Devuelve el script COMPLETO mejorado en bloque ```python```\n"
        f"- Después del código, explica brevemente qué cambió\n"
    )

    respuesta = _claude(prompt, max_tokens=3000)
    codigo_nuevo = _extraer_codigo(respuesta)

    # Backup del original
    ts      = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup  = ruta.parent / f"_{ruta.stem}_backup_{ts}{ruta.suffix}"
    backup.write_text(ruta.read_text(encoding="utf-8"), encoding="utf-8")

    # Guardar mejorado
    ruta.write_text(codigo_nuevo, encoding="utf-8")

    # Extraer explicación (texto después del bloque de código)
    explicacion = re.sub(r"```python.*?```", "", respuesta, flags=re.DOTALL).strip()

    return {
        "archivo":     str(ruta),
        "backup":      str(backup),
        "script":      codigo_nuevo,
        "explicacion": explicacion,
        "mensaje":     f"✅ Script mejorado: {ruta.name}\n   Backup guardado: {backup.name}",
    }


def documentar_script(archivo: str) -> dict:
    """Agrega docstrings, comentarios y type hints a un script existente."""
    ruta = _buscar_archivo(archivo)
    if not ruta:
        return {"error": f"Archivo no encontrado: {archivo}"}

    codigo_actual = _sanitizar(_leer_codigo(ruta))

    prompt = (
        f"Documenta este script Python de Egakat SPA agregando:\n"
        f"1. Docstring del módulo con descripción, uso y autor\n"
        f"2. Docstrings en todas las funciones (parámetros, retorno, ejemplo)\n"
        f"3. Comentarios en líneas de lógica compleja\n"
        f"4. Type hints en parámetros y retornos\n\n"
        f"Código:\n```python\n{codigo_actual}\n```\n\n"
        f"Devuelve el script completo documentado en bloque ```python```.\n"
        f"Autor: Sócrates Cabral / Control de Gestión y Mejora Continua / Egakat SPA\n"
    )

    respuesta  = _claude(prompt, max_tokens=3000)
    codigo_doc = _extraer_codigo(respuesta)

    ts     = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = ruta.parent / f"_{ruta.stem}_backup_{ts}{ruta.suffix}"
    backup.write_text(ruta.read_text(encoding="utf-8"), encoding="utf-8")
    ruta.write_text(codigo_doc, encoding="utf-8")

    return {
        "archivo": str(ruta),
        "backup":  str(backup),
        "mensaje": f"✅ Script documentado: {ruta.name}\n   Backup: {backup.name}",
    }


def generar_tarea_scheduler(archivo: str, hora: str = "08:00",
                             frecuencia: str = "diaria", dias: str = "L-V") -> dict:
    """
    Genera el XML para Task Scheduler de Windows para un script dado.
    Sigue el patrón exacto de las tareas existentes en el proyecto.
    """
    ruta = _buscar_archivo(archivo)
    if not ruta:
        return {"error": f"Archivo no encontrado: {archivo}"}

    python_exe = sys.executable
    hora_parts = hora.split(":")
    hora_xml   = f"2026-01-01T{hora_parts[0]:0>2}:{hora_parts[1]:0>2}:00"

    # Mapeo días
    dias_xml = {
        "L-V":  "<DaysOfWeek><Monday/><Tuesday/><Wednesday/><Thursday/><Friday/></DaysOfWeek>",
        "diaria": "<DaysOfWeek><Monday/><Tuesday/><Wednesday/><Thursday/><Friday/></DaysOfWeek>",
        "lunes": "<DaysOfWeek><Monday/></DaysOfWeek>",
    }.get(dias.lower(), "<DaysOfWeek><Monday/><Tuesday/><Wednesday/><Thursday/><Friday/></DaysOfWeek>")

    nombre_tarea = f"Egakat - {ruta.stem.replace('_', ' ').title()}"

    xml = f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>Tarea automatica: {ruta.stem} — Egakat SPA</Description>
    <Author>Socrates Cabral</Author>
  </RegistrationInfo>
  <Triggers>
    <CalendarTrigger>
      <StartBoundary>{hora_xml}</StartBoundary>
      <Enabled>true</Enabled>
      <ScheduleByWeek>
        <WeeksInterval>1</WeeksInterval>
        {dias_xml}
      </ScheduleByWeek>
    </CalendarTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <LogonType>Password</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <WakeToRun>true</WakeToRun>
    <ExecutionTimeLimit>PT2H</ExecutionTimeLimit>
    <Enabled>true</Enabled>
  </Settings>
  <Actions>
    <Exec>
      <Command>{python_exe}</Command>
      <Arguments>"{ruta}"</Arguments>
      <WorkingDirectory>{ruta.parent}</WorkingDirectory>
    </Exec>
  </Actions>
</Task>"""

    xml_path = ruta.parent / f"tarea_{ruta.stem}.xml"
    xml_path.write_text(xml, encoding="utf-16")

    cmd_registro = (
        f'schtasks /create /tn "{nombre_tarea}" '
        f'/xml "{xml_path}" /ru "Socrates Cabral" /rp /f'
    )

    return {
        "xml_path":     str(xml_path),
        "nombre_tarea": nombre_tarea,
        "comando":      cmd_registro,
        "mensaje": (
            f"✅ XML generado: {xml_path.name}\n"
            f"   Tarea: {nombre_tarea}\n"
            f"   Horario: {hora} — {dias}\n\n"
            f"Para registrar en Task Scheduler ejecuta:\n"
            f"   {cmd_registro}"
        ),
    }


def revisar_script(archivo: str) -> dict:
    """Revisión de calidad: bugs, seguridad, convenciones Egakat, mejoras."""
    ruta = _buscar_archivo(archivo)
    if not ruta:
        return {"error": f"Archivo no encontrado: {archivo}"}

    codigo = _sanitizar(_leer_codigo(ruta))

    prompt = (
        f"Revisa este script Python de Egakat SPA y entrega un informe de calidad:\n\n"
        f"```python\n{codigo}\n```\n\n"
        f"Evalúa:\n"
        f"1. Cumplimiento de convenciones Egakat (encoding, headless, .env, logs, rutas)\n"
        f"2. Bugs potenciales o errores de lógica\n"
        f"3. Riesgos de seguridad (credenciales expuestas, etc.)\n"
        f"4. Manejo de errores — ¿es suficiente?\n"
        f"5. Top 3 mejoras prioritarias\n"
        f"Sé conciso y directo. Prioriza problemas reales sobre estilo.\n"
    )

    analisis = _claude(prompt, max_tokens=1500)

    return {
        "archivo": str(ruta),
        "analisis": analisis,
    }


# ══════════════════════════════════════════════════════════════════════════════
#  CLI
# ══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Agente Generador de Scripts Egakat")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_n = sub.add_parser("nuevo",      help="Generar script desde requerimiento")
    p_n.add_argument("requerimiento")
    p_n.add_argument("--nombre", default=None, help="Nombre del archivo .py")

    p_m = sub.add_parser("mejorar",    help="Mejorar script existente")
    p_m.add_argument("archivo")
    p_m.add_argument("instruccion")

    p_d = sub.add_parser("documentar", help="Agregar docstrings y comentarios")
    p_d.add_argument("archivo")

    p_t = sub.add_parser("tarea",      help="Generar XML Task Scheduler")
    p_t.add_argument("archivo")
    p_t.add_argument("--hora",       default="08:00")
    p_t.add_argument("--frecuencia", default="diaria")
    p_t.add_argument("--dias",       default="L-V")

    p_r = sub.add_parser("revisar",    help="Revisión de calidad del script")
    p_r.add_argument("archivo")

    args = parser.parse_args()

    if args.cmd == "nuevo":
        r = generar_script(args.requerimiento, args.nombre)
    elif args.cmd == "mejorar":
        r = mejorar_script(args.archivo, args.instruccion)
    elif args.cmd == "documentar":
        r = documentar_script(args.archivo)
    elif args.cmd == "tarea":
        r = generar_tarea_scheduler(args.archivo, args.hora, args.frecuencia, args.dias)
    elif args.cmd == "revisar":
        r = revisar_script(args.archivo)

    if "error" in r:
        print(f"[ERROR] {r['error']}")
        sys.exit(1)

    print("\n" + "═" * 60)
    print(r.get("mensaje", ""))

    if "explicacion" in r and r["explicacion"]:
        print(f"\n📝 Cambios realizados:\n{r['explicacion']}")

    if "analisis" in r:
        print(f"\n📊 Revisión:\n{r['analisis']}")

    if "script" in r and args.cmd == "nuevo":
        print(f"\n{'─'*60}\nScript generado:\n{'─'*60}\n{r['script'][:800]}...")


if __name__ == "__main__":
    main()
