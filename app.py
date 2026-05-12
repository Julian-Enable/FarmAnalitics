# =============================================================================
# app.py - dashboard Streamlit legado
# =============================================================================
import streamlit as st
from styles import get_css
from components import render_main_header
from config import COL_VENTAS, COL_COMPRAS, COL_INVENTARIO
from utils import (
    concatenar, leer_archivo,
    validar_columnas, procesar_ventas, procesar_compras, procesar_inventario,
)
from tabs import tab_resumen, tab_ventas, tab_rentabilidad
from tabs import tab_inventario, tab_compras, tab_sedes

st.set_page_config(page_title="Dashboard Farmaceutico (Legado)", page_icon="??", layout="wide")
st.markdown(get_css(), unsafe_allow_html=True)

with st.sidebar:
    st.markdown("## ?? Dashboard Farma")
    st.caption("Modo legado local. El despliegue activo usa FastAPI + Vue.")
    st.divider()

    st.markdown("#### ?? Ventas")
    arch_ventas = st.file_uploader(
        "Uno o varios archivos de ventas",
        type=["csv", "xlsx", "xls"],
        accept_multiple_files=True,
        key="ventas",
    )

    st.markdown("#### ?? Compras")
    arch_compras = st.file_uploader(
        "Uno o varios archivos de compras",
        type=["csv", "xlsx", "xls"],
        accept_multiple_files=True,
        key="compras",
    )

    st.markdown("#### ?? Inventario")
    arch_inv = st.file_uploader(
        "Archivo maestro de inventario",
        type=["csv", "xlsx", "xls"],
        key="inv",
    )

df_v = df_c = df_i = None

if arch_ventas:
    df_v = concatenar(arch_ventas)
    if df_v is not None and validar_columnas(df_v, COL_VENTAS, "Ventas"):
        df_v = procesar_ventas(df_v)
    else:
        df_v = None

if arch_compras:
    df_c = concatenar(arch_compras)
    if df_c is not None and validar_columnas(df_c, COL_COMPRAS, "Compras"):
        df_c = procesar_compras(df_c)
    else:
        df_c = None

if arch_inv:
    df_i = leer_archivo(arch_inv)
    if df_i is not None and validar_columnas(df_i, COL_INVENTARIO, "Inventario"):
        df_i = procesar_inventario(df_i)
    else:
        df_i = None

render_main_header()
st.warning("Esta interfaz Streamlit queda solo como referencia local. Para el producto activo usa el frontend Vue.")

if df_v is None and df_c is None and df_i is None:
    st.info("Usa el panel lateral para subir tus archivos y activar el analisis.")
    st.stop()

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "Resumen General",
    "Analisis de Ventas",
    "Rentabilidad",
    "Alertas Inventario",
    "Compras vs Ventas",
    "Rendimiento Sedes",
])

with tab1:
    tab_resumen.render(df_v, df_c, df_i)
with tab2:
    tab_ventas.render(df_v, df_c, df_i)
with tab3:
    tab_rentabilidad.render(df_v, df_c, df_i)
with tab4:
    tab_inventario.render(df_v, df_c, df_i)
with tab5:
    tab_compras.render(df_v, df_c, df_i)
with tab6:
    tab_sedes.render(df_v, df_c, df_i)

st.markdown('<div class="gradient-divider"></div>', unsafe_allow_html=True)
st.caption("Dashboard Farmaceutico Streamlit - modo legado local")
