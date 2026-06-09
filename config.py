# =============================================================================
# config.py - Constantes de negocio compartidas por backend y sincronizacion
# =============================================================================

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
