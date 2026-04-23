# =============================================================================
# utils.py — Funciones de carga, validación y procesamiento de datos
# =============================================================================
import streamlit as st
import pandas as pd


def leer_archivo(archivo):
    """Lee un archivo CSV o Excel y retorna un DataFrame.

    Args:
        archivo: Objeto UploadedFile de Streamlit.

    Returns:
        DataFrame o None si hay error.
    """
    nombre = archivo.name.lower()
    try:
        if nombre.endswith(".csv"):
            return pd.read_csv(archivo)
        elif nombre.endswith((".xlsx", ".xls")):
            return pd.read_excel(archivo)
    except Exception as e:
        st.error(f"❌ Error leyendo **{archivo.name}**: {e}")
    return None


def concatenar(archivos):
    """Concatena múltiples archivos del mismo tipo en un solo DataFrame.

    Útil cuando el usuario sube varios meses de ventas o compras.

    Args:
        archivos: Lista de UploadedFile.

    Returns:
        DataFrame concatenado o None.
    """
    dfs = [leer_archivo(f) for f in archivos]
    dfs = [d for d in dfs if d is not None]
    return pd.concat(dfs, ignore_index=True) if dfs else None


def validar_columnas(df, columnas_requeridas, nombre_tipo):
    """Verifica que el DataFrame tenga las columnas necesarias.

    Args:
        df: DataFrame a validar.
        columnas_requeridas: Lista de nombres de columna esperados.
        nombre_tipo: Nombre legible del tipo ("Ventas", "Compras", etc.)

    Returns:
        True si todas las columnas existen, False si faltan.
    """
    faltantes = [c for c in columnas_requeridas if c not in df.columns]
    if faltantes:
        st.error(f"⚠️ **{nombre_tipo}** — faltan columnas: `{faltantes}`")
        return False
    return True


def procesar_ventas(df):
    """Limpia y prepara el DataFrame de ventas.

    - Convierte columnas numéricas
    - Parsea fechas
    - Calcula columna de ingreso (Cant × Precio Venta)
    """
    df["Cant"] = pd.to_numeric(df["Cant"], errors="coerce").fillna(0)
    df["Precio Venta"] = pd.to_numeric(df["Precio Venta"], errors="coerce").fillna(0)
    df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce")
    df["Ingreso"] = df["Cant"] * df["Precio Venta"]
    return df


def procesar_compras(df):
    """Limpia y prepara el DataFrame de compras."""
    df["CANT"] = pd.to_numeric(df["CANT"], errors="coerce").fillna(0)
    df["PRECIO"] = pd.to_numeric(df["PRECIO"], errors="coerce").fillna(0)
    df["FECHA"] = pd.to_datetime(df["FECHA"], errors="coerce")
    df["Costo Total"] = df["CANT"] * df["PRECIO"]
    return df


def procesar_inventario(df):
    """Limpia y prepara el DataFrame de inventario."""
    cols_numericas = ["Total", "Stock Minimo", "Stock Maximo", "Precio Compra", "Precio Venta"]
    for col in cols_numericas:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return df


def fmt_cop(n):
    """Formatea un número como pesos colombianos abreviados.

    Ejemplos:
        1_500_000 → "$1.5M"
        55_000    → "$55K"
        800       → "$800"
    """
    if abs(n) >= 1_000_000:
        return f"${n / 1_000_000:,.1f}M"
    if abs(n) >= 1_000:
        return f"${n / 1_000:,.0f}K"
    return f"${n:,.0f}"
