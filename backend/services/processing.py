# =============================================================================
# backend/services/processing.py
# Limpieza y procesamiento de DataFrames
# =============================================================================
import pandas as pd


def procesar_ventas(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["Cant"]        = pd.to_numeric(df.get("Cant"),        errors="coerce").fillna(0)
    df["Precio Venta"] = pd.to_numeric(df.get("Precio Venta"), errors="coerce").fillna(0)
    df["Fecha"]       = pd.to_datetime(df.get("Fecha"),      errors="coerce")
    df["Ingreso"]     = df["Cant"] * df["Precio Venta"]
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
    return df


def leer_bytes(content: bytes, filename: str) -> pd.DataFrame:
    """Lee un archivo desde bytes (upload). Si es Excel, lee todas las hojas de datos."""
    import io
    if filename.lower().endswith(".csv"):
        return pd.read_csv(io.BytesIO(content))
    
    # Es un archivo Excel (xlsx, xls)
    xls_dict = pd.read_excel(io.BytesIO(content), sheet_name=None)
    
    hojas_validas = []
    for sheet_name, df in xls_dict.items():
        if df.empty:
            continue
            
        # Revisamos si la hoja tiene columnas que parezcan de nuestros datos (Ventas, Compras, Inventario)
        columnas_upper = [str(c).upper() for c in df.columns]
        
        # Criterio: Si tiene "REFERENCIA", "CANT", "TOTAL", "FECHA" o similares clave.
        if "REFERENCIA" in columnas_upper:
            # Agregamos una columna indicando el origen del mes o pestaña (opcional pero útil para debug)
            df_cleaned = df.copy()
            hojas_validas.append(df_cleaned)

    if not hojas_validas:
        return pd.DataFrame()
        
    return pd.concat(hojas_validas, ignore_index=True)

