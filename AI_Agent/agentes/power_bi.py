"""
power_bi.py — Agente Power BI Egakat
Genera DAX, Power Query M, modelos de datos y estructura de reportes.

Uso CLI:
    py AI_Agent/agentes/power_bi.py dax     "total unidades bloqueadas por subrubro"
    py AI_Agent/agentes/power_bi.py query   "limpiar columnas y quitar filas vacías del stock WMS"
    py AI_Agent/agentes/power_bi.py modelo  "stock WMS + staging + posiciones"
    py AI_Agent/agentes/power_bi.py revisar "medida.dax"
    py AI_Agent/agentes/power_bi.py informe "dashboard operaciones logísticas"
    py AI_Agent/agentes/power_bi.py kpis    "stock"

Uso como módulo:
    from agentes.power_bi import generar_dax, generar_query_m
"""
import sys
sys.stdout.reconfigure(encoding="utf-8")

import os
import argparse
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent.parent.parent
load_dotenv(dotenv_path=BASE_DIR / ".env")

SALIDA_DIR = BASE_DIR / "AI_Agent" / "powerbi_output"
SALIDA_DIR.mkdir(exist_ok=True)

# ── Contexto Power BI Egakat ──────────────────────────────────────────────────
CONTEXTO_PBI = """
Eres un experto en Power BI especializado en logística 3PL para Egakat SPA, Chile.

CONTEXTO DEL MODELO DE DATOS:
Las fuentes de datos provienen de archivos Excel/CSV en OneDrive sincronizado con SharePoint.

TABLAS DISPONIBLES Y SUS COLUMNAS CLAVE:

1. Stock_WMS (fuente: Reporte_de_Ubicacion_de_Contenedor.xlsx)
   - Material_WMS, Material_SAP, Articulo_descripcion
   - Rubro, Subrubro
   - Pallet, Lote, Bloqueado (N/S)
   - Codigo_Estado, Descripcion_Estado
   - Cantidad, Unidad, Bultos, Litros, Kgs
   - Lugar, Ubicacion
   - Fecha_Alta, Fecha_Vencimiento

2. Staging_INOUT (fuente: VISTA_CONSULTA_Pallets_*.csv)
   - Empresa (cliente), Sucursal
   - Columnas de cantidad de pallets/bultos
   - Fechas de movimiento

3. Posiciones (fuente: Posiciones Ocupadas/Libres.xlsx)
   - Sucursal (Quilicura / Pudahuel)
   - Posiciones_Ocupadas, Posiciones_Libres, Posiciones_Parciales
   - Total_Posiciones

4. NPS_Respuestas (fuente: NPS_Egakat_YYYYMMDD.xlsx)
   - Score (0-10), Criterios, Comentario
   - Contacto, Via, Fecha

5. VDR_Diferencias (fuente: Reporte VDR comparativo)
   - Codigo_Parte, Descripcion
   - Cantidad_Sistema, Cantidad_VDR, Diferencia

TABLA CALENDARIO (siempre necesaria):
   Calendario = CALENDAR(DATE(2025,1,1), DATE(2026,12,31))

CONVENCIONES DAX EGAKAT:
- Medidas siempre con prefijo del área: [Stock_], [Ops_], [NPS_], [VDR_]
- Usar DIVIDE() en vez de / para evitar errores de división por cero
- Variables con VAR para legibilidad
- Comentarios en español explicando la lógica de negocio
- Formato: separador decimal punto, miles con coma (estándar Chile)

REGLAS Power Query M:
- Siempre definir tipos de datos explícitamente
- Eliminar columnas innecesarias temprano en la query
- Nombres de pasos en español descriptivos
- Reemplazar errores con null, no con 0 (salvo indicación contraria)
- Primer paso siempre: origen del archivo desde parámetro o ruta relativa

KPIs LOGÍSTICOS CLAVE para Egakat:
- % Stock Bloqueado = Bloqueado S / Total * 100
- Tasa Ocupación = Posiciones Ocupadas / Total Posiciones * 100
- Rotación Staging = Movimientos / Período
- NPS Score = (Promotores - Detractores) / Total * 100
- Diferencia VDR = ABS(Cantidad_Sistema - Cantidad_VDR)
"""


def _claude(prompt: str, max_tokens: int = 2000) -> str:
    from anthropic import Anthropic
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        return "ERROR: ANTHROPIC_API_KEY no está en .env"
    client = Anthropic(api_key=api_key)
    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=max_tokens,
        system=CONTEXTO_PBI,
        messages=[{"role": "user", "content": prompt}]
    )
    return resp.content[0].text


def _guardar(contenido: str, nombre: str, extension: str = "txt") -> Path:
    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    ruta = SALIDA_DIR / f"{nombre}_{ts}.{extension}"
    ruta.write_text(contenido, encoding="utf-8")
    return ruta


# ══════════════════════════════════════════════════════════════════════════════
#  FUNCIONES PRINCIPALES
# ══════════════════════════════════════════════════════════════════════════════

def generar_dax(descripcion: str) -> dict:
    """Genera medidas DAX desde una descripción en lenguaje natural."""
    prompt = (
        f"Genera las medidas DAX necesarias para Egakat SPA con este requerimiento:\n\n"
        f"{descripcion}\n\n"
        f"Entrega:\n"
        f"1. Todas las medidas DAX necesarias (con comentarios explicativos)\n"
        f"2. Tabla donde debe crearse cada medida\n"
        f"3. Formato sugerido (número, porcentaje, etc.)\n"
        f"4. Si necesita relaciones adicionales en el modelo, indicarlo\n"
        f"5. Ejemplo de uso en una tarjeta o visual\n"
    )
    respuesta = _claude(prompt)
    ruta      = _guardar(respuesta, "dax", "txt")
    return {"resultado": respuesta, "guardado": str(ruta),
            "mensaje": f"✅ DAX generado y guardado en: {ruta.name}"}


def generar_query_m(descripcion: str, tabla: str = None) -> dict:
    """Genera código Power Query M desde una descripción."""
    contexto_tabla = f"Tabla de referencia: {tabla}\n\n" if tabla else ""
    prompt = (
        f"Genera el código Power Query M para Egakat SPA:\n\n"
        f"{contexto_tabla}"
        f"Requerimiento: {descripcion}\n\n"
        f"Entrega:\n"
        f"1. Código M completo listo para pegar en Editor Avanzado de Power BI\n"
        f"2. Explicación de cada paso en español\n"
        f"3. Tipos de datos aplicados a cada columna\n"
        f"4. Si hay transformaciones condicionales, explica la lógica\n"
    )
    respuesta = _claude(prompt)
    ruta      = _guardar(respuesta, "query_m", "txt")
    return {"resultado": respuesta, "guardado": str(ruta),
            "mensaje": f"✅ Query M generado y guardado en: {ruta.name}"}


def generar_modelo(fuentes: str) -> dict:
    """Propone un modelo de datos estrella/copo de nieve para las fuentes dadas."""
    prompt = (
        f"Diseña el modelo de datos Power BI para Egakat SPA con estas fuentes:\n\n"
        f"{fuentes}\n\n"
        f"Entrega:\n"
        f"1. Diagrama del modelo en texto (tablas y relaciones)\n"
        f"2. Tabla de hechos principal y tablas de dimensión\n"
        f"3. Relaciones: cardinalidad y dirección de filtro\n"
        f"4. Tabla Calendario y cómo conectarla\n"
        f"5. Columnas calculadas recomendadas en cada tabla\n"
        f"6. Jerarquías sugeridas (fecha, geografía, producto)\n"
        f"7. Código DAX para tabla Calendario completa\n"
    )
    respuesta = _claude(prompt, max_tokens=2500)
    ruta      = _guardar(respuesta, "modelo", "txt")
    return {"resultado": respuesta, "guardado": str(ruta),
            "mensaje": f"✅ Modelo de datos generado: {ruta.name}"}


def revisar_dax(archivo: str) -> dict:
    """Revisa y optimiza código DAX o M existente."""
    ruta = Path(archivo)
    if not ruta.exists():
        for encontrado in BASE_DIR.rglob(ruta.name):
            ruta = encontrado
            break
    if not ruta.exists():
        return {"error": f"Archivo no encontrado: {archivo}"}

    codigo = ruta.read_text(encoding="utf-8", errors="ignore")[:4000]
    prompt = (
        f"Revisa y optimiza este código DAX/M de Egakat SPA:\n\n"
        f"```\n{codigo}\n```\n\n"
        f"Evalúa:\n"
        f"1. Rendimiento: ¿hay cálculos que se pueden optimizar?\n"
        f"2. Errores lógicos o de contexto de filtro\n"
        f"3. Convenciones de nomenclatura Egakat\n"
        f"4. Versión mejorada del código\n"
        f"5. Explicación de cada mejora\n"
    )
    respuesta = _claude(prompt)
    ruta_out  = _guardar(respuesta, "revision_dax", "txt")
    return {"resultado": respuesta, "guardado": str(ruta_out),
            "mensaje": f"✅ Revisión completada: {ruta_out.name}"}


def generar_estructura_informe(descripcion: str) -> dict:
    """Propone la estructura completa de un reporte Power BI."""
    prompt = (
        f"Diseña la estructura completa de un reporte Power BI para Egakat SPA:\n\n"
        f"Descripción: {descripcion}\n\n"
        f"Entrega:\n"
        f"1. Páginas del reporte (nombre y propósito de cada una)\n"
        f"2. Visualizaciones recomendadas por página (tipo + datos + filtros)\n"
        f"3. Segmentadores globales (slicers) sugeridos\n"
        f"4. KPIs principales en tarjetas\n"
        f"5. Medidas DAX necesarias para los visuales más importantes\n"
        f"6. Paleta de colores (alineada con logística: semáforos, alertas)\n"
        f"7. Filtros de seguridad por rol (si aplica)\n"
    )
    respuesta = _claude(prompt, max_tokens=2500)
    ruta      = _guardar(respuesta, "estructura_informe", "txt")
    return {"resultado": respuesta, "guardado": str(ruta),
            "mensaje": f"✅ Estructura de informe generada: {ruta.name}"}


def generar_kpis(area: str) -> dict:
    """Genera el set completo de KPIs DAX para un área operativa."""
    areas = {
        "stock":     "inventario y stock WMS — bloqueados, disponibles, rotación, por subrubro",
        "staging":   "staging IN/OUT — pallets por cliente, flujo entrada/salida, pendientes",
        "posiciones":"ocupación de bodega — tasa ocupación, libres, parciales por sucursal",
        "nps":       "satisfacción de clientes — NPS score, promotores, detractores, tendencia",
        "vdr":       "diferencias de inventario VDR — cantidad, valor, por código de parte",
        "general":   "dashboard ejecutivo 3PL — todos los módulos consolidados",
    }
    descripcion_area = areas.get(area.lower(), area)

    prompt = (
        f"Genera el set COMPLETO de medidas DAX para el área '{area}' de Egakat SPA:\n"
        f"Contexto del área: {descripcion_area}\n\n"
        f"Para cada KPI entrega:\n"
        f"- Nombre con prefijo correcto\n"
        f"- Código DAX completo con comentarios\n"
        f"- Formato de número\n"
        f"- Umbral de alerta (si aplica: verde/amarillo/rojo)\n\n"
        f"Incluye también:\n"
        f"- Medidas de comparación vs período anterior (MoM, WoW)\n"
        f"- Medidas de tendencia (promedio móvil 4 semanas)\n"
        f"- KPI de variación absoluta y porcentual\n"
    )
    respuesta = _claude(prompt, max_tokens=2500)
    ruta      = _guardar(respuesta, f"kpis_{area}", "txt")
    return {"resultado": respuesta, "guardado": str(ruta),
            "mensaje": f"✅ KPIs '{area}' generados: {ruta.name}"}


# ══════════════════════════════════════════════════════════════════════════════
#  CLI
# ══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Agente Power BI Egakat")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_d = sub.add_parser("dax",     help="Generar medidas DAX")
    p_d.add_argument("descripcion")

    p_q = sub.add_parser("query",   help="Generar código Power Query M")
    p_q.add_argument("descripcion")
    p_q.add_argument("--tabla", default=None)

    p_m = sub.add_parser("modelo",  help="Diseñar modelo de datos")
    p_m.add_argument("fuentes")

    p_r = sub.add_parser("revisar", help="Revisar DAX/M existente")
    p_r.add_argument("archivo")

    p_i = sub.add_parser("informe", help="Estructura de reporte Power BI")
    p_i.add_argument("descripcion")

    p_k = sub.add_parser("kpis",    help="Set completo de KPIs por área")
    p_k.add_argument("area",
        choices=["stock", "staging", "posiciones", "nps", "vdr", "general"])

    args = parser.parse_args()

    if args.cmd == "dax":
        r = generar_dax(args.descripcion)
    elif args.cmd == "query":
        r = generar_query_m(args.descripcion, args.tabla)
    elif args.cmd == "modelo":
        r = generar_modelo(args.fuentes)
    elif args.cmd == "revisar":
        r = revisar_dax(args.archivo)
    elif args.cmd == "informe":
        r = generar_estructura_informe(args.descripcion)
    elif args.cmd == "kpis":
        r = generar_kpis(args.area)

    if "error" in r:
        print(f"[ERROR] {r['error']}")
        sys.exit(1)

    print("\n" + "═" * 60)
    print(r["mensaje"])
    print("\n" + "─" * 60)
    print(r["resultado"])


if __name__ == "__main__":
    main()
