# =============================================================================
# config.py — Design Tokens y Constantes
# Basado en el Design System Linear/Modern
# =============================================================================

# ── Paleta de Colores ────────────────────────────────────────────────────────
# Backgrounds: near-blacks (nunca #000000 puro)
BG_DEEP = "#020203"
BG_BASE = "#050506"
BG_ELEVATED = "#0a0a0c"

# Surfaces: translúcidas para efecto de profundidad
SURFACE = "rgba(255,255,255,0.05)"
SURFACE_HOVER = "rgba(255,255,255,0.08)"

# Foreground: textos legibles (nunca blanco puro)
FG = "#EDEDEF"
FG_MUTED = "#8A8F98"
FG_SUBTLE = "rgba(255,255,255,0.60)"

# Accent: indigo como color principal interactivo
ACCENT = "#5E6AD2"
ACCENT_BRIGHT = "#6872D9"
ACCENT_GLOW = "rgba(94,106,210,0.3)"

# Borders: sutiles, casi invisibles
BORDER = "rgba(255,255,255,0.06)"
BORDER_HOVER = "rgba(255,255,255,0.10)"
BORDER_ACCENT = "rgba(94,106,210,0.30)"

# Semánticos
GREEN = "#48bb78"
RED = "#fc8181"
AMBER = "#f6ad55"
CYAN = "#4fd1c5"
PINK = "#f687b3"

# Paletas para gráficos Plotly
CHART_PALETTE = [ACCENT, CYAN, GREEN, AMBER, RED, PINK, ACCENT_BRIGHT]
SEDE_PALETTE = [ACCENT, GREEN, AMBER, RED, CYAN, PINK]

# ── Layout Plotly base ───────────────────────────────────────────────────────
PLOTLY_LAYOUT = dict(
    template="plotly_dark",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter, system-ui, sans-serif", color=FG, size=12),
    margin=dict(l=10, r=10, t=30, b=10),
    xaxis=dict(gridcolor="rgba(255,255,255,0.04)", zerolinecolor="rgba(255,255,255,0.06)"),
    yaxis=dict(gridcolor="rgba(255,255,255,0.04)", zerolinecolor="rgba(255,255,255,0.06)"),
)

# ── Columnas requeridas por tipo de archivo ─────────────────────────────────
COL_VENTAS = [
    "Referencia", "Descripcion", "Cant", "Precio Venta",
    "Laboratorio", "Fecha", "Punto Venta",
]
COL_COMPRAS = [
    "FECHA", "PROVEEDOR", "REFERENCIA", "DESCRIPCION",
    "LABORATORIO", "PRECIO", "CANT", "SEDE",
]
COL_INVENTARIO = [
    "Referencia", "Descripcion", "Laboratorio",
    "Total", "Stock Minimo", "Stock Maximo",
]

# Columnas de sedes en el inventario
SEDES_INVENTARIO = ["PRINCIPAL", "SUCURSAL", "MORATO", "VARDI", "CEDI"]
