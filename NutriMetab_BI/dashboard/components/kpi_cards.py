"""
kpi_cards.py — Componentes KPI reutilizables para el dashboard
"""
import streamlit as st


def kpi_card(label: str, value: str | int | float, delta: str = "", color: str = "#14b8a6"):
    st.markdown(
        f"""
        <div style="background:#0f1e30;border:1px solid {color};border-radius:8px;
                    padding:16px;text-align:center;margin-bottom:8px;">
            <div style="font-size:1.8em;font-weight:bold;color:{color};">{value}</div>
            <div style="font-size:0.85em;color:#94a3b8;">{label}</div>
            {"" if not delta else f'<div style="font-size:0.8em;color:#64748b;">{delta}</div>'}
        </div>
        """,
        unsafe_allow_html=True,
    )


def badge_riesgo(nivel: str) -> str:
    COLORES = {
        "Bajo":     ("#166534", "#bbf7d0"),
        "Moderado": ("#713f12", "#fef08a"),
        "Alto":     ("#7f1d1d", "#fca5a5"),
        "Muy alto": ("#450a0a", "#ff8080"),
    }
    bg, fg = COLORES.get(nivel, ("#1e293b", "#e2e8f0"))
    return (
        f'<span style="background:{bg};color:{fg};padding:3px 10px;'
        f'border-radius:12px;font-size:0.85em;font-weight:bold;">{nivel}</span>'
    )


def alerta_box(mensaje: str, severidad: str = "warning"):
    ICONOS = {"info": "ℹ️", "warning": "⚠️", "danger": "🚨", "success": "✅"}
    COLORES_BG = {
        "info":    "#0f2a3f", "warning": "#2d1f00",
        "danger":  "#2d0000", "success": "#0a2d1a",
    }
    COLORES_BD = {
        "info":    "#38bdf8", "warning": "#f59e0b",
        "danger":  "#ef4444", "success": "#22c55e",
    }
    icono = ICONOS.get(severidad, "ℹ️")
    bg    = COLORES_BG.get(severidad, "#0f1e30")
    bd    = COLORES_BD.get(severidad, "#14b8a6")
    st.markdown(
        f"""
        <div style="background:{bg};border-left:4px solid {bd};
                    border-radius:4px;padding:12px 16px;margin:8px 0;">
            {icono} {mensaje}
        </div>
        """,
        unsafe_allow_html=True,
    )
