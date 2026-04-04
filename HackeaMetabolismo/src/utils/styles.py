"""
styles.py — Sistema de estilos global para Hackea tu Metabolismo con IA
Inyectar con: from src.utils.styles import inject_styles; inject_styles()
"""
import streamlit as st

# ── Paleta ────────────────────────────────────────────────────
BG          = "#0a1628"
BG_SIDEBAR  = "#071020"
BG_CARD     = "#0d1f3c"
BG_INPUT    = "#0d1f3c"
BORDER      = "#1e3a5f"
BORDER_FOCUS= "#0f9d7a"
TEAL        = "#0f9d7a"
TEAL_LIGHT  = "#14c49b"
VIOLET      = "#7f77dd"
CORAL       = "#e55c2f"
TEXT_PRIMARY= "#e2e8f0"
TEXT_SEC    = "#94a3b8"
TEXT_MUTED  = "#64748b"


def inject_styles():
    """Inyecta el CSS global de la aplicación en la página actual."""
    st.markdown(f"""
<style>
/* ── Reset base ──────────────────────────────────────────── */
.stApp {{
    background-color: {BG};
    color: {TEXT_PRIMARY};
}}
section[data-testid="stSidebar"] {{
    background-color: {BG_SIDEBAR};
    border-right: 1px solid {BORDER};
}}

/* ── Tipografía global ───────────────────────────────────── */
html, body, [class*="css"] {{
    color: {TEXT_PRIMARY};
    font-family: 'Inter', 'Segoe UI', sans-serif;
}}
h1, h2, h3 {{ color: {TEAL}; font-weight: 700; letter-spacing: -0.5px; }}
h4, h5, h6 {{ color: {TEXT_PRIMARY}; font-weight: 600; }}
p, span, label, div {{ color: {TEXT_PRIMARY}; }}

/* ── Sidebar ─────────────────────────────────────────────── */
section[data-testid="stSidebar"] * {{
    color: {TEXT_PRIMARY} !important;
}}
section[data-testid="stSidebar"] a {{
    color: {TEXT_SEC} !important;
    font-size: 0.875rem;
    padding: 4px 0;
    display: block;
    transition: color 0.2s;
}}
section[data-testid="stSidebar"] a:hover {{
    color: {TEAL} !important;
}}
section[data-testid="stSidebar"] [data-testid="stSidebarNavLink"] {{
    color: {TEXT_SEC} !important;
    border-radius: 6px;
    margin: 2px 0;
    padding: 6px 12px !important;
    transition: all 0.2s;
}}
section[data-testid="stSidebar"] [data-testid="stSidebarNavLink"]:hover {{
    background: {BG_CARD} !important;
    color: {TEAL} !important;
}}
section[data-testid="stSidebar"] [aria-current="page"] {{
    background: {BG_CARD} !important;
    color: {TEAL} !important;
    border-left: 3px solid {TEAL} !important;
}}

/* ── Inputs (text, email, password, number) ──────────────── */
.stTextInput > div > div > input,
.stNumberInput > div > div > input,
.stTextArea > div > div > textarea,
input[type="text"],
input[type="email"],
input[type="password"],
input[type="number"] {{
    background-color: {BG_INPUT} !important;
    color: {TEXT_PRIMARY} !important;
    border: 1px solid {BORDER} !important;
    border-radius: 8px !important;
    padding: 10px 14px !important;
    font-size: 0.9rem !important;
    transition: border-color 0.2s, box-shadow 0.2s !important;
}}
.stTextInput > div > div > input:focus,
.stNumberInput > div > div > input:focus,
.stTextArea > div > div > textarea:focus {{
    border-color: {BORDER_FOCUS} !important;
    box-shadow: 0 0 0 2px rgba(15,157,122,0.20) !important;
    outline: none !important;
}}
.stTextInput > div > div > input::placeholder,
.stTextArea > div > div > textarea::placeholder {{
    color: {TEXT_MUTED} !important;
}}

/* ── Selectbox ───────────────────────────────────────────── */
.stSelectbox > div > div,
.stSelectbox > div > div > div {{
    background-color: {BG_INPUT} !important;
    color: {TEXT_PRIMARY} !important;
    border: 1px solid {BORDER} !important;
    border-radius: 8px !important;
}}
.stSelectbox > div > div:focus-within {{
    border-color: {BORDER_FOCUS} !important;
    box-shadow: 0 0 0 2px rgba(15,157,122,0.20) !important;
}}
[data-baseweb="select"] {{
    background-color: {BG_INPUT} !important;
}}
[data-baseweb="select"] > div {{
    background-color: {BG_INPUT} !important;
    border-color: {BORDER} !important;
    color: {TEXT_PRIMARY} !important;
    border-radius: 8px !important;
}}
[data-baseweb="popover"] {{
    background-color: {BG_CARD} !important;
    border: 1px solid {BORDER} !important;
    border-radius: 8px !important;
}}
[data-baseweb="menu"] {{
    background-color: {BG_CARD} !important;
}}
[role="option"] {{
    background-color: {BG_CARD} !important;
    color: {TEXT_PRIMARY} !important;
}}
[role="option"]:hover {{
    background-color: {BORDER} !important;
}}

/* ── Date input ──────────────────────────────────────────── */
.stDateInput > div > div > input,
[data-baseweb="input"] input {{
    background-color: {BG_INPUT} !important;
    color: {TEXT_PRIMARY} !important;
    border: 1px solid {BORDER} !important;
    border-radius: 8px !important;
}}
[data-baseweb="base-input"] {{
    background-color: {BG_INPUT} !important;
    border-color: {BORDER} !important;
}}

/* ── Time input ──────────────────────────────────────────── */
.stTimeInput > div > div > input {{
    background-color: {BG_INPUT} !important;
    color: {TEXT_PRIMARY} !important;
    border: 1px solid {BORDER} !important;
    border-radius: 8px !important;
}}

/* ── Slider ──────────────────────────────────────────────── */
.stSlider [data-baseweb="slider"] {{
    background-color: {BORDER} !important;
}}
.stSlider [data-testid="stThumbValue"] {{
    color: {TEXT_PRIMARY} !important;
}}

/* ── Select slider ───────────────────────────────────────── */
[data-testid="stSelectSlider"] {{
    background-color: transparent !important;
}}

/* ── Date picker calendar popup ──────────────────────────── */
[data-baseweb="calendar"] {{
    background-color: {BG_CARD} !important;
    border: 1px solid {BORDER} !important;
    border-radius: 12px !important;
    box-shadow: 0 8px 32px rgba(0,0,0,0.5) !important;
}}
[data-baseweb="calendar"] * {{
    background-color: transparent !important;
    color: {TEXT_PRIMARY} !important;
}}
[data-baseweb="calendar"] [aria-label] {{
    color: {TEXT_PRIMARY} !important;
}}
/* Días del mes */
[data-baseweb="calendar"] [role="gridcell"] button {{
    color: {TEXT_PRIMARY} !important;
    border-radius: 6px !important;
    font-size: 0.85rem !important;
    transition: background 0.15s !important;
}}
[data-baseweb="calendar"] [role="gridcell"] button:hover {{
    background-color: {BORDER} !important;
}}
/* Día seleccionado */
[data-baseweb="calendar"] [aria-selected="true"] button,
[data-baseweb="calendar"] [data-selected="true"] button {{
    background-color: {TEAL} !important;
    color: #ffffff !important;
    font-weight: 700 !important;
}}
/* Cabecera (mes/año) */
[data-baseweb="calendar"] [data-baseweb="typography"] {{
    color: {TEXT_PRIMARY} !important;
    font-weight: 600 !important;
}}
/* Flechas navegación */
[data-baseweb="calendar"] button[aria-label*="previous"],
[data-baseweb="calendar"] button[aria-label*="next"],
[data-baseweb="calendar"] button[aria-label*="anterior"],
[data-baseweb="calendar"] button[aria-label*="siguiente"] {{
    color: {TEAL} !important;
    background: transparent !important;
}}
[data-baseweb="calendar"] button[aria-label*="previous"]:hover,
[data-baseweb="calendar"] button[aria-label*="next"]:hover {{
    background-color: {BORDER} !important;
    border-radius: 6px !important;
}}
/* Días de semana (Lu, Ma, Mi...) */
[data-baseweb="calendar"] [role="columnheader"] {{
    color: {TEXT_SEC} !important;
    font-size: 0.75rem !important;
    text-transform: uppercase !important;
    letter-spacing: 0.5px !important;
}}
/* Días fuera del mes actual */
[data-baseweb="calendar"] [data-outside-month="true"] button {{
    color: {TEXT_MUTED} !important;
    opacity: 0.5 !important;
}}
/* Select mes/año dropdown dentro del calendar */
[data-baseweb="calendar"] select {{
    background-color: {BG_INPUT} !important;
    color: {TEXT_PRIMARY} !important;
    border: 1px solid {BORDER} !important;
    border-radius: 6px !important;
}}

/* ── Buttons ─────────────────────────────────────────────── */
.stButton > button {{
    background: linear-gradient(135deg, {TEAL} 0%, #0d7a5f 100%) !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: 8px !important;
    padding: 10px 20px !important;
    font-weight: 600 !important;
    font-size: 0.9rem !important;
    letter-spacing: 0.3px !important;
    transition: all 0.2s !important;
    box-shadow: 0 4px 12px rgba(15,157,122,0.30) !important;
}}
.stButton > button:hover {{
    background: linear-gradient(135deg, {TEAL_LIGHT} 0%, {TEAL} 100%) !important;
    box-shadow: 0 6px 16px rgba(15,157,122,0.45) !important;
    transform: translateY(-1px) !important;
}}
.stButton > button:active {{
    transform: translateY(0) !important;
}}
/* Botón eliminar (🗑️) — pequeño, sin fondo llamativo */
.stButton > button[kind="secondary"],
button[data-testid*="del_"] {{
    background: transparent !important;
    color: {CORAL} !important;
    border: 1px solid {CORAL} !important;
    box-shadow: none !important;
    padding: 4px 8px !important;
    font-size: 0.8rem !important;
}}

/* ── Form submit button ──────────────────────────────────── */
.stFormSubmitButton > button {{
    background: linear-gradient(135deg, {TEAL} 0%, #0d7a5f 100%) !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: 8px !important;
    padding: 12px 24px !important;
    font-weight: 700 !important;
    font-size: 1rem !important;
    width: 100% !important;
    box-shadow: 0 4px 16px rgba(15,157,122,0.35) !important;
    transition: all 0.2s !important;
}}
.stFormSubmitButton > button:hover {{
    background: linear-gradient(135deg, {TEAL_LIGHT} 0%, {TEAL} 100%) !important;
    box-shadow: 0 6px 20px rgba(15,157,122,0.50) !important;
    transform: translateY(-1px) !important;
}}

/* ── Forms ───────────────────────────────────────────────── */
[data-testid="stForm"] {{
    background-color: {BG_CARD} !important;
    border: 1px solid {BORDER} !important;
    border-radius: 12px !important;
    padding: 24px !important;
}}

/* ── Tabs ────────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {{
    background-color: {BG_CARD} !important;
    border-radius: 10px !important;
    padding: 4px !important;
    gap: 4px !important;
    border: 1px solid {BORDER} !important;
}}
.stTabs [data-baseweb="tab"] {{
    background-color: transparent !important;
    color: {TEXT_SEC} !important;
    border-radius: 7px !important;
    padding: 8px 16px !important;
    font-weight: 500 !important;
    border: none !important;
    transition: all 0.2s !important;
}}
.stTabs [aria-selected="true"] {{
    background-color: {TEAL} !important;
    color: #ffffff !important;
    font-weight: 700 !important;
}}
.stTabs [data-baseweb="tab-panel"] {{
    background-color: transparent !important;
    padding-top: 16px !important;
}}

/* ── Métricas ────────────────────────────────────────────── */
[data-testid="stMetric"] {{
    background-color: {BG_CARD} !important;
    border: 1px solid {BORDER} !important;
    border-radius: 10px !important;
    padding: 14px 16px !important;
}}
[data-testid="stMetricLabel"] {{
    color: {TEXT_SEC} !important;
    font-size: 0.78rem !important;
    font-weight: 500 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.5px !important;
}}
[data-testid="stMetricValue"] {{
    color: {TEXT_PRIMARY} !important;
    font-size: 1.6rem !important;
    font-weight: 700 !important;
}}
[data-testid="stMetricDelta"] {{
    font-size: 0.82rem !important;
    font-weight: 600 !important;
}}

/* ── Alertas / Info / Warning / Error ────────────────────── */
[data-testid="stAlert"] {{
    border-radius: 10px !important;
    border-left-width: 4px !important;
    font-weight: 500 !important;
}}
div[data-testid="stAlert"] > div {{
    color: {TEXT_PRIMARY} !important;
}}

/* ── Expander ────────────────────────────────────────────── */
[data-testid="stExpander"] {{
    background-color: {BG_CARD} !important;
    border: 1px solid {BORDER} !important;
    border-radius: 10px !important;
}}
[data-testid="stExpander"] summary {{
    color: {TEXT_PRIMARY} !important;
    font-weight: 600 !important;
}}

/* ── Dataframe / tabla ───────────────────────────────────── */
[data-testid="stDataFrame"] {{
    background-color: {BG_CARD} !important;
    border: 1px solid {BORDER} !important;
    border-radius: 10px !important;
}}

/* ── Divider ─────────────────────────────────────────────── */
hr {{
    border-color: {BORDER} !important;
    margin: 20px 0 !important;
}}

/* ── Caption / footnote ──────────────────────────────────── */
[data-testid="stCaptionContainer"] {{
    color: {TEXT_MUTED} !important;
    font-size: 0.78rem !important;
}}

/* ── Download button ─────────────────────────────────────── */
[data-testid="stDownloadButton"] > button {{
    background: linear-gradient(135deg, {VIOLET} 0%, #5c56b8 100%) !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    box-shadow: 0 4px 12px rgba(127,119,221,0.35) !important;
}}

/* ── File uploader ───────────────────────────────────────── */
[data-testid="stFileUploader"] {{
    background-color: {BG_CARD} !important;
    border: 2px dashed {BORDER} !important;
    border-radius: 10px !important;
    transition: border-color 0.2s !important;
}}
[data-testid="stFileUploader"]:hover {{
    border-color: {TEAL} !important;
}}
[data-testid="stFileUploader"] * {{
    color: {TEXT_SEC} !important;
}}

/* ── Checkbox ────────────────────────────────────────────── */
.stCheckbox label {{
    color: {TEXT_PRIMARY} !important;
}}

/* ── Scrollbar ───────────────────────────────────────────── */
::-webkit-scrollbar {{ width: 6px; height: 6px; }}
::-webkit-scrollbar-track {{ background: {BG}; }}
::-webkit-scrollbar-thumb {{ background: {BORDER}; border-radius: 3px; }}
::-webkit-scrollbar-thumb:hover {{ background: {TEAL}; }}

/* ── Spinner ─────────────────────────────────────────────── */
[data-testid="stSpinner"] {{ color: {TEAL} !important; }}

/* ── Top bar oculta (Deploy button area) ─────────────────── */
header[data-testid="stHeader"] {{
    background-color: {BG} !important;
    border-bottom: 1px solid {BORDER} !important;
}}
</style>
""", unsafe_allow_html=True)
