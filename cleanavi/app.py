import sys
sys.stdout.reconfigure(encoding="utf-8")

import os
import hashlib
import time
from pathlib import Path
from datetime import datetime, timedelta
import streamlit as st
import pandas as pd
import send2trash

# ── Configuración ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="CleanAvi",
    page_icon="🧹",
    layout="wide",
    initial_sidebar_state="expanded",
)

EXTENSIONES_TEMP = {
    ".tmp", ".temp", ".log", ".bak", ".old", ".cache", ".dmp",
    ".chk", ".gid", ".fts", ".ftg", ".nch", ".db-shm", ".db-wal",
}
CARPETAS_TEMP = {"__pycache__", ".cache", "cache", "temp", "tmp", "Temp"}
DIAS_ANTIGUO = 180  # 6 meses sin uso = "antiguo"
MB = 1024 * 1024

# ── Helpers ───────────────────────────────────────────────────────────────────
def formato_size(bytes_val):
    if bytes_val >= 1024 ** 3:
        return f"{bytes_val / 1024**3:.1f} GB"
    elif bytes_val >= 1024 ** 2:
        return f"{bytes_val / 1024**2:.1f} MB"
    elif bytes_val >= 1024:
        return f"{bytes_val / 1024:.1f} KB"
    return f"{bytes_val} B"

def hash_archivo(path, block=65536):
    h = hashlib.md5()
    try:
        with open(path, "rb") as f:
            while chunk := f.read(block):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return None

def es_temporal(path: Path):
    if path.suffix.lower() in EXTENSIONES_TEMP:
        return True
    for parte in path.parts:
        if parte in CARPETAS_TEMP:
            return True
    return False

def escanear(carpeta: str, progress_bar):
    archivos = []
    carpeta_path = Path(carpeta)
    todos = list(carpeta_path.rglob("*"))
    total = len(todos)
    ahora = time.time()
    limite_antiguo = ahora - DIAS_ANTIGUO * 86400

    for i, p in enumerate(todos):
        if i % 200 == 0:
            progress_bar.progress(min(i / max(total, 1), 0.95), text=f"Escaneando... {i}/{total}")
        try:
            if not p.is_file():
                continue
            stat = p.stat()
            size = stat.st_size
            mtime = stat.st_mtime
            atime = stat.st_atime
            ultimo_acceso = max(mtime, atime)
            archivos.append({
                "ruta": str(p),
                "nombre": p.name,
                "extension": p.suffix.lower(),
                "carpeta": str(p.parent),
                "size_bytes": size,
                "size_fmt": formato_size(size),
                "modificado": datetime.fromtimestamp(mtime).strftime("%Y-%m-%d"),
                "ultimo_acceso_ts": ultimo_acceso,
                "es_temporal": es_temporal(p),
                "es_antiguo": ultimo_acceso < limite_antiguo and size > MB,
                "hash": None,  # se calcula solo para duplicados
            })
        except (PermissionError, OSError):
            continue

    progress_bar.progress(1.0, text="Escaneo completado ✅")
    return archivos

def detectar_duplicados(archivos: list):
    # Solo calcular hash en archivos con mismo tamaño (optimización)
    from collections import defaultdict
    por_size = defaultdict(list)
    for a in archivos:
        if a["size_bytes"] > 0:
            por_size[a["size_bytes"]].append(a)

    grupos_dup = defaultdict(list)
    for size, grupo in por_size.items():
        if len(grupo) < 2:
            continue
        for a in grupo:
            h = hash_archivo(a["ruta"])
            if h:
                a["hash"] = h
                grupos_dup[h].append(a["ruta"])

    # Marcar duplicados (conservar el más reciente, sugerir borrar el resto)
    rutas_dup = set()
    for h, rutas in grupos_dup.items():
        if len(rutas) > 1:
            rutas_ordenadas = sorted(rutas, key=lambda r: os.path.getmtime(r), reverse=True)
            for r in rutas_ordenadas[1:]:  # el primero (más nuevo) se conserva
                rutas_dup.add(r)

    for a in archivos:
        a["es_duplicado"] = a["ruta"] in rutas_dup

    return archivos

# ── UI ────────────────────────────────────────────────────────────────────────
st.title("🧹 CleanAvi")
st.caption("Limpiador inteligente de archivos — solo sugiere, nunca borra sin confirmación")

# Sidebar
with st.sidebar:
    st.header("📁 Carpeta a analizar")
    carpeta_input = st.text_input("Ruta", value=str(Path.home()), placeholder="C:\\Users\\...")
    buscar_dup = st.checkbox("Detectar duplicados (más lento)", value=False)
    st.divider()
    st.header("🔍 Filtros")
    mostrar = st.multiselect(
        "Mostrar",
        ["Todos", "Grandes (>50 MB)", "Duplicados", "Temporales/Basura", "Antiguos (>6 meses)"],
        default=["Todos"],
    )
    st.divider()
    st.caption("v1.0 | ClaudeWork")

# Botón escanear
if st.button("🔍 Escanear carpeta", type="primary", use_container_width=True):
    if not Path(carpeta_input).exists():
        st.error("La carpeta no existe.")
    else:
        with st.spinner("Iniciando escaneo..."):
            pb = st.progress(0, text="Iniciando...")
            archivos = escanear(carpeta_input, pb)
            if buscar_dup:
                with st.spinner("Calculando hashes para detectar duplicados..."):
                    archivos = detectar_duplicados(archivos)
            else:
                for a in archivos:
                    a["es_duplicado"] = False
            st.session_state["archivos"] = archivos
            st.session_state["carpeta"] = carpeta_input

# ── Resultados ────────────────────────────────────────────────────────────────
if "archivos" in st.session_state:
    archivos = st.session_state["archivos"]
    df = pd.DataFrame(archivos)

    # KPIs
    total_size = df["size_bytes"].sum()
    n_temp = df["es_temporal"].sum()
    n_dup = df["es_duplicado"].sum()
    n_ant = df["es_antiguo"].sum()
    size_temp = df[df["es_temporal"]]["size_bytes"].sum()
    size_dup = df[df["es_duplicado"]]["size_bytes"].sum()
    size_ant = df[df["es_antiguo"]]["size_bytes"].sum()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total archivos", f"{len(df):,}", f"{formato_size(total_size)}")
    c2.metric("🗑️ Temporales", f"{n_temp:,}", f"{formato_size(size_temp)} recuperables")
    c3.metric("👯 Duplicados", f"{n_dup:,}", f"{formato_size(size_dup)} recuperables")
    c4.metric("🕰️ Antiguos", f"{n_ant:,}", f"{formato_size(size_ant)} recuperables")

    # Top carpetas
    with st.expander("📊 Carpetas que más espacio ocupan", expanded=False):
        top_carpetas = (
            df.groupby("carpeta")["size_bytes"]
            .sum()
            .sort_values(ascending=False)
            .head(15)
            .reset_index()
        )
        top_carpetas["size_fmt"] = top_carpetas["size_bytes"].apply(formato_size)
        top_carpetas["barra"] = top_carpetas["size_bytes"] / top_carpetas["size_bytes"].max()
        st.dataframe(
            top_carpetas[["carpeta", "size_fmt", "barra"]].rename(
                columns={"carpeta": "Carpeta", "size_fmt": "Tamaño", "barra": "% relativo"}
            ),
            column_config={"% relativo": st.column_config.ProgressColumn(min_value=0, max_value=1)},
            use_container_width=True,
            hide_index=True,
        )

    # Filtrar según selección
    df_filtrado = pd.DataFrame()
    if "Todos" in mostrar or not mostrar:
        df_filtrado = df.copy()
    else:
        masks = []
        if "Grandes (>50 MB)" in mostrar:
            masks.append(df["size_bytes"] > 50 * MB)
        if "Duplicados" in mostrar:
            masks.append(df["es_duplicado"])
        if "Temporales/Basura" in mostrar:
            masks.append(df["es_temporal"])
        if "Antiguos (>6 meses)" in mostrar:
            masks.append(df["es_antiguo"])
        if masks:
            mask_final = masks[0]
            for m in masks[1:]:
                mask_final = mask_final | m
            df_filtrado = df[mask_final].copy()

    if df_filtrado.empty:
        st.info("No hay archivos que coincidan con el filtro seleccionado.")
    else:
        df_filtrado = df_filtrado.sort_values("size_bytes", ascending=False).reset_index(drop=True)

        # Columnas a mostrar
        cols_mostrar = ["nombre", "size_fmt", "modificado", "es_temporal", "es_duplicado", "es_antiguo", "carpeta"]
        df_display = df_filtrado[cols_mostrar].rename(columns={
            "nombre": "Archivo",
            "size_fmt": "Tamaño",
            "modificado": "Modificado",
            "es_temporal": "Temporal",
            "es_duplicado": "Duplicado",
            "es_antiguo": "Antiguo",
            "carpeta": "Carpeta",
        })

        # Añadir columna de selección
        df_display.insert(0, "✅ Seleccionar", False)

        st.subheader(f"📋 {len(df_filtrado):,} archivos — {formato_size(df_filtrado['size_bytes'].sum())} total")

        edited = st.data_editor(
            df_display,
            use_container_width=True,
            hide_index=True,
            column_config={
                "✅ Seleccionar": st.column_config.CheckboxColumn("Seleccionar"),
                "Temporal": st.column_config.CheckboxColumn("Temp"),
                "Duplicado": st.column_config.CheckboxColumn("Dup"),
                "Antiguo": st.column_config.CheckboxColumn("Antiguo"),
                "Tamaño": st.column_config.TextColumn("Tamaño"),
            },
            num_rows="fixed",
        )

        # Archivos seleccionados
        seleccionados_idx = edited[edited["✅ Seleccionar"]].index.tolist()
        seleccionados_rutas = df_filtrado.loc[seleccionados_idx, "ruta"].tolist()
        size_sel = df_filtrado.loc[seleccionados_idx, "size_bytes"].sum()

        if seleccionados_rutas:
            st.info(f"**{len(seleccionados_rutas)} archivos seleccionados** — {formato_size(size_sel)} recuperables")
            col_btn1, col_btn2 = st.columns([1, 4])
            with col_btn1:
                if st.button("🗑️ Enviar a papelera", type="primary"):
                    errores = []
                    ok = 0
                    for ruta in seleccionados_rutas:
                        try:
                            send2trash.send2trash(ruta)
                            ok += 1
                        except Exception as e:
                            errores.append(f"{ruta}: {e}")
                    if ok:
                        st.success(f"✅ {ok} archivos enviados a la papelera. Espacio recuperado: {formato_size(size_sel)}")
                    if errores:
                        st.warning(f"⚠️ {len(errores)} errores:\n" + "\n".join(errores[:5]))
                    # Refrescar estado
                    del st.session_state["archivos"]
                    st.rerun()
        else:
            st.caption("Selecciona archivos en la tabla para enviarlos a la papelera.")
