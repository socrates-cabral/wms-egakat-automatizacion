from pathlib import Path
from datetime import datetime, timedelta


ONEDRIVE = Path(r"C:\Users\Socrates Cabral\OneDrive - EGA KAT LOGISTICA SPA")

RUTA_STOCK = ONEDRIVE / "Datos para Dashboard - Stock WMS Semanal"
RUTA_POSICIONES = ONEDRIVE / "Datos para Dashboard - Consulta de Posiciones"
RUTA_STAGING = ONEDRIVE / "Datos para Dashboard - Stagin IN- OUT"
RUTA_CLIENTES_EK = ONEDRIVE / "Datos para Dashboard - Clientes EK"


def periodo_actual_clientes_ek(now: datetime | None = None) -> tuple[str, str]:
    now = now or datetime.now()
    ayer = now - timedelta(days=1)
    meses = {
        1: "01 Enero", 2: "02 Febrero", 3: "03 Marzo", 4: "04 Abril",
        5: "05 Mayo", 6: "06 Junio", 7: "07 Julio", 8: "08 Agosto",
        9: "09 Septiembre", 10: "10 Octubre", 11: "11 Noviembre", 12: "12 Diciembre",
    }
    return str(ayer.year), meses[ayer.month]


def build_validation_rules(now: datetime | None = None):
    ano, mes = periodo_actual_clientes_ek(now)

    rules = [
        # M1 - Stock WMS: archivos dinámicos por carpeta, validados por patrón del nombre.
        {
            "modulo": "Modulo 1 - Stock WMS Semanal",
            "submodulo": "Quilicura",
            "folder_mode": True,
            "carpeta": str(RUTA_STOCK / "Quilicura"),
            "tipo": "excel",
            "filename_contains": "Reporte_de_Ubicacion_de_Contenedor_QUILICURA",
            "must_be_today": True,
            "min_filas": 1,
        },
        {
            "modulo": "Modulo 1 - Stock WMS Semanal",
            "submodulo": "Pudahuel",
            "folder_mode": True,
            "carpeta": str(RUTA_STOCK / "Pudahuel"),
            "tipo": "excel",
            "filename_contains": "Reporte_de_Ubicacion_de_Contenedor_PUDAHUEL",
            "must_be_today": True,
            "min_filas": 1,
        },
        {
            "modulo": "Modulo 1 - Stock WMS Semanal",
            "submodulo": "Pudahuel Unitario",
            "folder_mode": True,
            "carpeta": str(RUTA_STOCK / "Pudahuel"),
            "tipo": "excel",
            "filename_contains": "Reporte_de_Ubicacion_de_Contenedor_PUDAHUEL_UNITARIO",
            "must_be_today": True,
            "min_filas": 1,
        },

        # M2 - Consulta de Posiciones: nombres fijos.
        {
            "modulo": "Modulo 3 - Consulta de Posiciones",
            "submodulo": "Quilicura Ocupadas",
            "archivo": str(RUTA_POSICIONES / "Quilicura" / "Posiciones Ocupadas.xlsx"),
            "tipo": "excel",
            "must_be_today": True,
            "min_filas": 1,
        },
        {
            "modulo": "Modulo 3 - Consulta de Posiciones",
            "submodulo": "Quilicura Libres",
            "archivo": str(RUTA_POSICIONES / "Quilicura" / "Posiciones Libres.xlsx"),
            "tipo": "excel",
            "must_be_today": True,
            "min_filas": 1,
        },
        {
            "modulo": "Modulo 3 - Consulta de Posiciones",
            "submodulo": "Pudahuel Ocupadas Moderno",
            "archivo": str(RUTA_POSICIONES / "Pudahuel" / "Posiciones Ocupadas Moderno.xlsx"),
            "tipo": "excel",
            "must_be_today": True,
            "min_filas": 1,
        },
        {
            "modulo": "Modulo 3 - Consulta de Posiciones",
            "submodulo": "Pudahuel Libres Moderno",
            "archivo": str(RUTA_POSICIONES / "Pudahuel" / "Posiciones Libres Moderno.xlsx"),
            "tipo": "excel",
            "must_be_today": True,
            "min_filas": 1,
        },
        {
            "modulo": "Modulo 3 - Consulta de Posiciones",
            "submodulo": "Pudahuel Unitario Ocupadas",
            "archivo": str(RUTA_POSICIONES / "Pudahuel" / "Posiciones Ocupadas Unitario.xlsx"),
            "tipo": "excel",
            "must_be_today": True,
            "min_filas": 1,
        },
        {
            "modulo": "Modulo 3 - Consulta de Posiciones",
            "submodulo": "Pudahuel Unitario Libres",
            "archivo": str(RUTA_POSICIONES / "Pudahuel" / "Posiciones Libres Unitario.xlsx"),
            "tipo": "excel",
            "must_be_today": True,
            "min_filas": 1,
        },
        {
            "modulo": "Modulo 3 - Consulta de Posiciones",
            "submodulo": "Pudahuel Refrigerado Ocupadas",
            "archivo": str(RUTA_POSICIONES / "Pudahuel" / "Posiciones Ocupadas Refrigerado.xlsx"),
            "tipo": "excel",
            "must_be_today": True,
            "min_filas": 1,
        },
        {
            "modulo": "Modulo 3 - Consulta de Posiciones",
            "submodulo": "Pudahuel Refrigerado Libres",
            "archivo": str(RUTA_POSICIONES / "Pudahuel" / "Posiciones Libres Refrigerado.xlsx"),
            "tipo": "excel",
            "must_be_today": True,
            "min_filas": 1,
        },
    ]

    # M3 - Staging IN/OUT: último CSV por carpeta. NATIVO con warning conocido.
    staging_clientes = [
        ("QUILICURA", "ABINBEV", "ABINBEV", False),
        ("QUILICURA", "DAIKIN", "DAIKIN", False),
        ("QUILICURA", "DAIKIN CLIENTES", "DAIKIN CLIENTES", False),
        ("QUILICURA", "DERCO", "DERCO", False),
        ("QUILICURA", "MASCOTAS LATINAS", "MASCOTAS LATINAS", False),
        ("QUILICURA", "POCHTECA", "POCHTECA", False),
        ("PUDAHUEL", "BARENTZ", "BARENTZ", False),
        ("PUDAHUEL", "BURASCHI", "BURASCHI", False),
        ("PUDAHUEL", "CEPAS CHILE", "CEPAS CHILE", False),
        ("PUDAHUEL", "COLLICO", "COLLICO", False),
        ("PUDAHUEL", "DELIBEST", "DELIBEST", False),
        ("PUDAHUEL", "INTIME", "INTIME", False),
        ("PUDAHUEL", "NATIVO DRINKS SPA", "NATIVOS DRINK", True),
        ("PUDAHUEL", "TRES MONTES", "TRES MONTE", False),
        ("PUDAHUEL", "UNILEVER", "UNILEVER", False),
        ("PUDAHUEL UNITARIO", "RUNO SPA", "RUNO", False),
    ]
    for deposito, submodulo, carpeta, es_nativo in staging_clientes:
        rule = {
            "modulo": "Modulo 2 - Staging IN/OUT",
            "submodulo": f"{deposito} | {submodulo}",
            "folder_mode": True,
            "carpeta": str(RUTA_STAGING / ("Quilicura" if deposito == "QUILICURA" else "Pudahuel") / carpeta),
            "tipo": "csv",
            "must_be_today": True,
            "min_filas": 0,
            "allow_header_only": True,
        }
        if es_nativo:
            rule["warning_on_missing"] = True
            rule["warning_conocido"] = "Cliente con comportamiento conocido: el WMS puede devolver 0 bytes o no generar archivo util."
            rule["warning_on_zero_bytes"] = True
        rules.append(rule)

    # M6 - SharePoint copy: validar que existan las carpetas base de destino local.
    for cliente in ["ABINBEV", "DAIKIN", "DERCO", "MASCOTAS LATINAS", "POCHTECA"]:
        rules.append({
            "modulo": "Modulo 6 - SharePoint Copy Clientes",
            "submodulo": cliente,
            "folder_exists_only": True,
            "carpeta": str(RUTA_CLIENTES_EK / cliente / "Inventario"),
        })

    # M7 - Pedidos Preparados: archivo fijo del mes actual de trabajo.
    for cliente in ["ABINBEV", "DAIKIN", "MASCOTAS LATINAS", "POCHTECA", "DERCO"]:
        rules.append({
            "modulo": "Modulo 7 - Pedidos Preparados",
            "submodulo": cliente,
            "archivo": str(RUTA_CLIENTES_EK / cliente / "Preparación" / ano / mes / "Pedidos Preparados.xlsx"),
            "tipo": "excel",
            "must_be_today": True,
            "min_filas": 0,
            "allow_header_only": True,
        })

    # M8 - Recepciones Recibidas: archivo fijo del mes actual de trabajo.
    for cliente in ["ABINBEV", "DAIKIN", "MASCOTAS LATINAS", "POCHTECA", "DERCO"]:
        rules.append({
            "modulo": "Modulo 8 - Recepciones Recibidas",
            "submodulo": cliente,
            "archivo": str(RUTA_CLIENTES_EK / cliente / "Recepciones" / ano / mes / "Recepciones Recibidas.xlsx"),
            "tipo": "excel",
            "must_be_today": True,
            "min_filas": 0,
            "allow_header_only": True,
        })

    return rules
