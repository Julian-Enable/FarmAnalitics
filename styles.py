# =============================================================================
# styles.py — Modo Claro Premium
# =============================================================================

def get_css():
    return """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

html, body, * {
    font-family: 'Inter', system-ui, sans-serif !important;
}

/* ── Fondo principal ─────────────────────────────────────────────────────── */
.stApp {
    background-color: #F7F8FC !important;
}

/* Ocultar barra de deploy innecesaria */
[data-testid="stToolbar"]     { display: none !important; }
[data-testid="stDecoration"]  { display: none !important; }

/* ── Sidebar ─────────────────────────────────────────────────────────────── */
section[data-testid="stSidebar"] {
    background-color: #FFFFFF !important;
    border-right: 1px solid #E5E7EB !important;
}
section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] span,
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] div {
    color: #111827 !important;
}
section[data-testid="stSidebar"] small,
section[data-testid="stSidebar"] [data-testid="stCaption"] p {
    color: #6B7280 !important;
}
section[data-testid="stSidebar"] hr {
    border-color: #E5E7EB !important;
}

/* File uploader dropzone */
[data-testid="stFileUploaderDropzone"] {
    background-color: #F3F4F8 !important;
    border: 1.5px dashed #A5AEDD !important;
    border-radius: 10px !important;
}
[data-testid="stFileUploaderDropzone"] * {
    background-color: transparent !important;
    color: #6B7280 !important;
}
[data-testid="stFileUploaderDropzone"] button {
    background-color: #5E6AD2 !important;
    color: #FFFFFF !important;
    border: none !important;
    border-radius: 8px !important;
    font-size: 0.82rem !important;
    font-weight: 600 !important;
    padding: 7px 16px !important;
}
[data-testid="stFileUploaderDropzone"] button:hover {
    background-color: #4A56C0 !important;
}

/* ── Tabs ────────────────────────────────────────────────────────────────── */
[data-testid="stTabs"] > div:first-child {
    background: #FFFFFF !important;
    border: 1px solid #E5E7EB !important;
    border-radius: 11px !important;
    padding: 4px !important;
    box-shadow: 0 1px 4px rgba(0,0,0,0.06) !important;
}
button[data-baseweb="tab"] {
    color: #6B7280 !important;
    background: transparent !important;
    border-radius: 8px !important;
    font-size: 0.83rem !important;
    font-weight: 500 !important;
    padding: 7px 14px !important;
    border: none !important;
    transition: all 0.15s ease !important;
}
button[data-baseweb="tab"]:hover {
    color: #111827 !important;
    background: #F3F4F8 !important;
}
button[aria-selected="true"][data-baseweb="tab"] {
    color: #5E6AD2 !important;
    background: #EEF0FB !important;
    font-weight: 600 !important;
    box-shadow: inset 0 0 0 1px rgba(94,106,210,0.30) !important;
}
[data-baseweb="tab-highlight"],
[data-baseweb="tab-border"] { display: none !important; }

/* ── Métricas ────────────────────────────────────────────────────────────── */
[data-testid="metric-container"] {
    background: #FFFFFF !important;
    border: 1px solid #E5E7EB !important;
    border-top: 3px solid #5E6AD2 !important;
    border-radius: 12px !important;
    padding: 18px 20px !important;
    box-shadow: 0 1px 6px rgba(0,0,0,0.06) !important;
    transition: box-shadow 0.2s ease, transform 0.2s ease !important;
}
[data-testid="metric-container"]:hover {
    box-shadow: 0 4px 18px rgba(94,106,210,0.15) !important;
    transform: translateY(-2px) !important;
}
[data-testid="stMetricLabel"] p,
[data-testid="stMetricLabel"] label {
    color: #6B7280 !important;
    font-size: 0.78rem !important;
    font-weight: 500 !important;
}
[data-testid="stMetricValue"] > div,
[data-testid="stMetricValue"] {
    color: #111827 !important;
    font-size: 1.5rem !important;
    font-weight: 700 !important;
}

/* ── DataFrames ──────────────────────────────────────────────────────────── */
[data-testid="stDataFrame"] {
    border: 1px solid #E5E7EB !important;
    border-radius: 12px !important;
    overflow: hidden !important;
    box-shadow: 0 1px 4px rgba(0,0,0,0.05) !important;
}

/* ── Selectbox / MultiSelect ─────────────────────────────────────────────── */
[data-baseweb="select"] > div:first-child {
    background: #FFFFFF !important;
    border-color: #D1D5DB !important;
    border-radius: 9px !important;
    color: #111827 !important;
}
[data-baseweb="select"] span,
[data-baseweb="select"] div { color: #111827 !important; }
[data-testid="stSelectbox"] label p,
[data-testid="stMultiSelect"] label p,
[data-testid="stDateInput"] label p {
    color: #374151 !important;
    font-size: 0.83rem !important;
    font-weight: 500 !important;
}

/* ── Alerts ──────────────────────────────────────────────────────────────── */
[data-testid="stAlert"] {
    background: #EEF0FB !important;
    border: 1px solid #C7CBF0 !important;
    border-radius: 11px !important;
}
[data-testid="stAlert"] p,
[data-testid="stAlert"] span { color: #374151 !important; }

/* ── Caption ─────────────────────────────────────────────────────────────── */
[data-testid="stCaption"] p { color: #9CA3AF !important; }

/* ── KPI Cards custom ────────────────────────────────────────────────────── */
.kpi-card {
    background: #FFFFFF;
    border: 1px solid #E5E7EB;
    border-top: 3px solid #5E6AD2;
    border-radius: 12px;
    padding: 18px 18px 14px;
    box-shadow: 0 1px 6px rgba(0,0,0,0.06);
    transition: box-shadow 0.2s ease, transform 0.2s ease;
}
.kpi-card:hover {
    box-shadow: 0 4px 18px rgba(94,106,210,0.15);
    transform: translateY(-2px);
}
.kpi-card .kpi-icon  { font-size: 1.2rem; margin-bottom: 8px; display: block; }
.kpi-card .kpi-value {
    font-size: 1.45rem; font-weight: 700; color: #111827;
    letter-spacing: -0.02em; line-height: 1.2; margin-bottom: 4px;
    font-family: 'Inter', system-ui, sans-serif;
}
.kpi-card .kpi-label {
    font-size: 0.76rem; font-weight: 500; color: #6B7280;
    font-family: 'Inter', system-ui, sans-serif;
}
</style>
"""
