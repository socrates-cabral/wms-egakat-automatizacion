"""
history_viewer.py — Módulo 13: Visor del historial de análisis guardados.
"""

import streamlit as st
from utils.history import load_history, delete_entry
from utils.pdf_exporter import export_analysis_to_pdf


def render():
    st.subheader("Historial de Análisis")
    st.caption("Todos los análisis que guardaste en sesiones anteriores.")

    entries = load_history()

    if not entries:
        st.info("No hay análisis guardados aún. Usa el botón '💾 Guardar' en cualquier módulo para guardar un análisis.")
        return

    st.caption(f"{len(entries)} análisis guardados")

    # Botón exportar todo a PDF
    if st.button("Exportar todo a PDF", key="history_export_all"):
        try:
            combined = "\n\n" + "="*60 + "\n\n".join(
                f"MÓDULO: {e['modulo']}\nTÍTULO: {e['titulo']}\nFECHA: {e['fecha']}\n\n{e['texto_completo']}"
                for e in entries
            )
            pdf_bytes = export_analysis_to_pdf("Historial Completo", "Historial", combined)
            st.download_button(
                "Descargar historial completo (PDF)",
                data=pdf_bytes,
                file_name="historial_inversiones_ia.pdf",
                mime="application/pdf",
                key="history_pdf_all",
            )
        except Exception as e:
            st.error(f"Error generando PDF: {str(e)}")

    st.divider()

    # Listar entradas
    to_delete = None
    for entry in entries:
        entry_id = entry.get("id", "")
        fecha = entry.get("fecha", "")
        modulo = entry.get("modulo", "")
        titulo = entry.get("titulo", "")
        resumen = entry.get("resumen", "")

        col_main, col_del = st.columns([10, 1])
        with col_main:
            with st.expander(f"**{titulo}** — {modulo} | {fecha}"):
                st.caption(f"Resumen: {resumen}...")
                st.markdown(entry.get("texto_completo", ""))

                col1, col2 = st.columns(2)
                with col1:
                    st.download_button(
                        "Descargar .txt",
                        data=entry.get("texto_completo", ""),
                        file_name=f"{titulo}_{fecha[:10]}.txt".replace(" ", "_"),
                        mime="text/plain",
                        key=f"hist_txt_{entry_id}",
                    )
                with col2:
                    try:
                        pdf_bytes = export_analysis_to_pdf(titulo, modulo, entry.get("texto_completo", ""))
                        st.download_button(
                            "📄 PDF",
                            data=pdf_bytes,
                            file_name=f"{titulo}_{fecha[:10]}.pdf".replace(" ", "_"),
                            mime="application/pdf",
                            key=f"hist_pdf_{entry_id}",
                        )
                    except Exception:
                        pass

        with col_del:
            if st.button("🗑️", key=f"del_{entry_id}", help="Eliminar este análisis"):
                to_delete = entry_id

    if to_delete:
        delete_entry(to_delete)
        st.success("Análisis eliminado")
        st.rerun()
