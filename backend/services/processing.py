# =============================================================================
# backend/services/processing.py
# Limpieza y procesamiento de DataFrames
# =============================================================================
import pandas as pd

from config import EXCLUDED_INVENTORY_COLUMNS


def procesar_ventas(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    aliases = {
        "REFERENCIA": "Referencia",
        "DESCRIPCION": "Descripcion",
        "CANT": "Cant",
        "PRECIO": "Precio Venta",
        "Precio": "Precio Venta",
        "LABORATORIO": "Laboratorio",
        "NIVEL": "Nivel",
        "FACTURA": "Factura",
        "FECHA": "Fecha",
        "SEDE": "Punto Venta",
    }
    df = df.rename(columns={src: dst for src, dst in aliases.items() if src in df.columns and dst not in df.columns})

    df["Cant"] = pd.to_numeric(df.get("Cant"), errors="coerce").fillna(0)
    df["Precio Venta"] = pd.to_numeric(df.get("Precio Venta"), errors="coerce").fillna(0)
    df["Fecha"] = pd.to_datetime(df.get("Fecha"), errors="coerce")

    ingreso_origen = pd.to_numeric(df.get("Ingreso"), errors="coerce") if "Ingreso" in df.columns else None
    ingreso_calc = df["Cant"] * df["Precio Venta"]
    df["Ingreso"] = ingreso_origen.fillna(ingreso_calc) if ingreso_origen is not None else ingreso_calc
    return df


def procesar_compras(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["CANT"]        = pd.to_numeric(df.get("CANT"),   errors="coerce").fillna(0)
    df["PRECIO"]      = pd.to_numeric(df.get("PRECIO"), errors="coerce").fillna(0)
    df["FECHA"]       = pd.to_datetime(df.get("FECHA"), errors="coerce")
    df["Costo Total"] = df["CANT"] * df["PRECIO"]
    return df


def procesar_inventario(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for col in ["Total", "Stock Minimo", "Stock Maximo", "Precio Compra", "Precio Venta"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    for col in df.columns:
        if col not in EXCLUDED_INVENTORY_COLUMNS:
            numeric = pd.to_numeric(df[col], errors="coerce")
            if numeric.notna().any():
                df[col] = numeric.fillna(0)
    if "Total" not in df.columns:
        sede_cols = [
            c for c in df.columns
            if c not in EXCLUDED_INVENTORY_COLUMNS and pd.api.types.is_numeric_dtype(df[c])
        ]
        df["Total"] = df[sede_cols].sum(axis=1) if sede_cols else 0
    return df


# ── Palabras clave para categorizar motivos de devolución ────────────────────
_MOTIVO_RULES = [
    ("Error de Facturación",   ["error de facturaci", "error factur"]),
    ("Error del Vendedor",     ["error del vendedor", "error vendedor"]),
    ("Solicitud del Cliente",  ["error del cliente", "error cliente", "cliente pide",
                                "cliente no", "cliente realiza", "cliente hizo", "cliente quiere"]),
    ("Cambio de Producto",     ["cambio", "cambi"]),
    ("Problema de Entrega",    ["domicilio", "entrega", "demora"]),
]

def _categorizar_motivo(obs: str) -> str:
    if not isinstance(obs, str) or not obs.strip():
        return "Sin observación"
    obs_l = obs.lower()
    for categoria, keywords in _MOTIVO_RULES:
        if any(k in obs_l for k in keywords):
            return categoria
    return "Otro"


def procesar_notas_credito(df: pd.DataFrame) -> pd.DataFrame:
    """Limpia y enriquece el DataFrame de Notas Crédito."""
    df = df.copy()
    df["Fecha"]    = pd.to_datetime(df.get("Fecha"),    errors="coerce")
    df["Total"]    = pd.to_numeric(df.get("Total"),     errors="coerce").fillna(0)
    df["SubTotal"] = pd.to_numeric(df.get("SubTotal"),  errors="coerce").fillna(0)
    df["IVA"]      = pd.to_numeric(df.get("IVA"),       errors="coerce").fillna(0)
    df["Saldo"]    = pd.to_numeric(df.get("Saldo"),     errors="coerce").fillna(0)
    df["Total Neto"] = df["Total"] - df["IVA"]
    if "Observaciones" in df.columns:
        df["Motivo"] = df["Observaciones"].apply(_categorizar_motivo)
    else:
        df["Motivo"] = "Sin observación"
    # Normalizar nombre de columna de sede para que coincida con Ventas
    if "PuntoVenta" in df.columns and "Punto Venta" not in df.columns:
        df = df.rename(columns={"PuntoVenta": "Punto Venta"})
    return df


def leer_bytes(content: bytes, filename: str, tipo: str = "auto") -> pd.DataFrame:
    """Lee un archivo desde bytes (upload). Si es Excel, lee todas las hojas de datos."""
    import io
    if filename.lower().endswith(".csv"):
        return pd.read_csv(io.BytesIO(content))

    # Es un archivo Excel (xlsx, xls)
    xls_dict = pd.read_excel(io.BytesIO(content), sheet_name=None)

    # ── Notas Crédito: identificar por columna NotaCredito ───────────────────
    if tipo == "notas_credito":
        hojas_validas = []
        for sheet_name, df in xls_dict.items():
            if df.empty:
                continue
            columnas_upper = [str(c).upper() for c in df.columns]
            if "NOTACREDITO" in columnas_upper or "NOTA CREDITO" in columnas_upper:
                hojas_validas.append(df.copy())
        if not hojas_validas:
            # Si no encontró por NotaCredito, intentar por columnas clave
            for sheet_name, df in xls_dict.items():
                if not df.empty and "Total" in df.columns and "Fecha" in df.columns:
                    hojas_validas.append(df.copy())
        if not hojas_validas:
            return pd.DataFrame()
        return pd.concat(hojas_validas, ignore_index=True)

    # ── Ventas / Compras / Inventario: identificar por columna Referencia ────
    hojas_validas = []
    for sheet_name, df in xls_dict.items():
        if df.empty:
            continue
        # Excluir hojas de resumen/reporte para evitar mezclar periodos.
        sheet_norm = str(sheet_name).strip().lower()
        if sheet_norm in {"reporte", "reportes"}:
            continue
        columnas_upper = [str(c).upper() for c in df.columns]
        if "REFERENCIA" in columnas_upper:
            hojas_validas.append(df.copy())

    if not hojas_validas:
        return pd.DataFrame()

    return pd.concat(hojas_validas, ignore_index=True)
