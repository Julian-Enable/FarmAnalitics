# =============================================================================
# config.py - Design tokens y constantes compartidas
# =============================================================================

# Paleta de colores
BG_DEEP = "#020203"
BG_BASE = "#050506"
BG_ELEVATED = "#0a0a0c"
SURFACE = "rgba(255,255,255,0.05)"
SURFACE_HOVER = "rgba(255,255,255,0.08)"
FG = "#EDEDEF"
FG_MUTED = "#8A8F98"
FG_SUBTLE = "rgba(255,255,255,0.60)"
ACCENT = "#5E6AD2"
ACCENT_BRIGHT = "#6872D9"
ACCENT_GLOW = "rgba(94,106,210,0.3)"
BORDER = "rgba(255,255,255,0.06)"
BORDER_HOVER = "rgba(255,255,255,0.10)"
BORDER_ACCENT = "rgba(94,106,210,0.30)"
GREEN = "#48bb78"
RED = "#fc8181"
AMBER = "#f6ad55"
CYAN = "#4fd1c5"
PINK = "#f687b3"

CHART_PALETTE = [ACCENT, CYAN, GREEN, AMBER, RED, PINK, ACCENT_BRIGHT]
SEDE_PALETTE = [ACCENT, GREEN, AMBER, RED, CYAN, PINK]

PLOTLY_LAYOUT = dict(
    template="plotly_dark",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter, system-ui, sans-serif", color=FG, size=12),
    margin=dict(l=10, r=10, t=30, b=10),
    xaxis=dict(gridcolor="rgba(255,255,255,0.04)", zerolinecolor="rgba(255,255,255,0.06)"),
    yaxis=dict(gridcolor="rgba(255,255,255,0.04)", zerolinecolor="rgba(255,255,255,0.06)"),
)

# Columnas requeridas por tipo de archivo
COL_VENTAS = [
    "Referencia", "Descripcion", "Cant", "Precio Venta",
    "Laboratorio", "Fecha", "Punto Venta",
]
COL_COMPRAS = [
    "FECHA", "PROVEEDOR", "REFERENCIA", "DESCRIPCION",
    "LABORATORIO", "PRECIO", "CANT", "SEDE",
]
COL_INVENTARIO = ["Referencia", "Descripcion", "Laboratorio"]
COL_NOTAS_CREDITO = ["Fecha", "NotaCredito", "PuntoVenta", "Total"]

REQUIRED_COLUMNS = {
    "ventas": COL_VENTAS,
    "compras": COL_COMPRAS,
    "inventario": COL_INVENTARIO,
    "notas_credito": COL_NOTAS_CREDITO,
}

SEDES_INVENTARIO = ["PRINCIPAL", "SUCURSAL", "MORATO", "VARDI", "CEDI", "OFICINA 805"]

EXCLUDED_INVENTORY_COLUMNS = {
    "Referencia", "Descripcion", "Laboratorio", "Nivel", "Precio Compra", "Precio Venta",
    "Comision", "Utilidad", "Stock Maximo", "Stock Minimo", "Total", "IVA", "Codigo",
}

MAX_UPLOAD_SIZE = 50 * 1024 * 1024
ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls"}
INV_MIN_DIAS = 25
INV_MAX_DIAS = 40
LOW_MARGIN_PCT = 5.0
HIGH_ROTATION_QUANTILE = 0.80
HIGH_ROTATION_MIN_UNITS = 5
QUIETO_DIAS_DEFAULT = 60
