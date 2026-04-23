# =============================================================================
# tab_ventas.py — Tab 2: Análisis de Ventas (con filtros interactivos)
# =============================================================================
import streamlit as st
import plotly.express as px
from config import PLOTLY_LAYOUT, ACCENT, CYAN
from components import render_section_header, render_divider


def render(df_v, df_c, df_i):
    """Renderiza la pestaña de Análisis de Ventas."""
    if df_v is None:
        st.warning("Sube archivos de **ventas** para ver este análisis.")
        return

    # ── Filtros interactivos ─────────────────────────────────────────────
    f1, f2, f3 = st.columns(3)
    with f1:
        opciones_sede = ["Todas"] + sorted(df_v["Punto Venta"].dropna().unique().tolist())
        filtro_sede = st.selectbox("Punto de Venta", opciones_sede, key="fv_sede")
    with f2:
        if "Nivel" in df_v.columns:
            opciones_nivel = ["Todos"] + sorted(df_v["Nivel"].dropna().unique().tolist())
        else:
            opciones_nivel = ["Todos"]
        filtro_nivel = st.selectbox("Categoría (Nivel)", opciones_nivel, key="fv_nivel")
    with f3:
        rango = None
        if df_v["Fecha"].notna().any():
            f_min, f_max = df_v["Fecha"].min().date(), df_v["Fecha"].max().date()
            rango = st.date_input("Rango de fechas", value=(f_min, f_max),
                                  min_value=f_min, max_value=f_max, key="fv_fecha")

    # Aplicar filtros
    dff = df_v.copy()
    if filtro_sede != "Todas":
        dff = dff[dff["Punto Venta"] == filtro_sede]
    if filtro_nivel != "Todos" and "Nivel" in dff.columns:
        dff = dff[dff["Nivel"] == filtro_nivel]
    if rango and len(rango) == 2:
        dff = dff[(dff["Fecha"].dt.date >= rango[0]) & (dff["Fecha"].dt.date <= rango[1])]

    st.caption(f"Mostrando **{len(dff):,}** registros filtrados")
    render_divider()

    # ── Gráficos principales ─────────────────────────────────────────────
    ca, cb = st.columns(2)

    with ca:
        render_section_header("🏆", "Top 15 Productos Más Vendidos")
        top_p = (dff.groupby(["Referencia", "Descripcion"], as_index=False)["Cant"]
                 .sum().nlargest(15, "Cant").sort_values("Cant", ascending=True))
        top_p["Nombre"] = top_p["Descripcion"].str[:35]
        fig = px.bar(top_p, x="Cant", y="Nombre", orientation="h",
                     color="Cant", color_continuous_scale="Purples",
                     labels={"Cant": "Unidades", "Nombre": ""})
        fig.update_layout(**PLOTLY_LAYOUT, height=450,
                          coloraxis_showscale=False, showlegend=False)
        st.plotly_chart(fig, width="stretch")

    with cb:
        render_section_header("🏭", "Top 10 Laboratorios por Ingresos")
        top_l = (dff.groupby("Laboratorio", as_index=False)["Ingreso"]
                 .sum().nlargest(10, "Ingreso").sort_values("Ingreso", ascending=True))
        top_l["Lab"] = top_l["Laboratorio"].str[:25]
        fig = px.bar(top_l, x="Ingreso", y="Lab", orientation="h",
                     color="Ingreso", color_continuous_scale="Tealgrn",
                     labels={"Ingreso": "Ingresos ($)", "Lab": ""})
        fig.update_layout(**PLOTLY_LAYOUT, height=450,
                          coloraxis_showscale=False, showlegend=False)
        st.plotly_chart(fig, width="stretch")

    cc, cd = st.columns(2)

    with cc:
        if "Nivel" in dff.columns:
            render_section_header("📂", "Ventas por Categoría")
            cat = (dff.groupby("Nivel", as_index=False)["Ingreso"]
                   .sum().sort_values("Ingreso", ascending=True))
            fig = px.bar(cat, x="Ingreso", y="Nivel", orientation="h",
                         color_discrete_sequence=[CYAN])
            fig.update_layout(**PLOTLY_LAYOUT, height=400, showlegend=False)
            st.plotly_chart(fig, width="stretch")

    with cd:
        if "Creada" in dff.columns:
            render_section_header("👤", "Ranking de Vendedores")
            vend = (dff.groupby("Creada").agg(
                Unidades=("Cant", "sum"), Ingresos=("Ingreso", "sum"),
                Facturas=("Factura", "nunique"),
            ).reset_index().sort_values("Ingresos", ascending=False).head(10))
            st.dataframe(vend, width="stretch", hide_index=True,
                         column_config={
                             "Creada": "Vendedor",
                             "Ingresos": st.column_config.NumberColumn(format="$%d"),
                             "Unidades": st.column_config.NumberColumn(format="%d"),
                         })
