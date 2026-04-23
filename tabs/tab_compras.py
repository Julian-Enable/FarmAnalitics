# =============================================================================
# tab_compras.py — Tab 5: Compras vs. Ventas
# =============================================================================
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from config import PLOTLY_LAYOUT, ACCENT, CYAN, GREEN, RED
from components import render_kpi_row, render_section_header, render_divider


def render(df_v, df_c, df_i):
    """Renderiza la pestaña de Compras vs Ventas."""
    if df_c is None or df_v is None:
        st.warning("Sube archivos de **ventas** y **compras** para ver este análisis.")
        return

    # ── Agrupar por laboratorio ──────────────────────────────────────────
    comp_lab = (df_c.groupby("LABORATORIO", as_index=False)["CANT"]
                .sum().rename(columns={"LABORATORIO": "Laboratorio", "CANT": "Comprado"}))
    vent_lab = (df_v.groupby("Laboratorio", as_index=False)["Cant"]
                .sum().rename(columns={"Cant": "Vendido"}))
    comp = comp_lab.merge(vent_lab, on="Laboratorio", how="outer").fillna(0)
    comp["Diferencia"] = comp["Comprado"] - comp["Vendido"]
    comp["Estado"] = comp["Diferencia"].apply(
        lambda d: "Sobre-compra" if d > 0 else ("Desabastecimiento" if d < 0 else "Equilibrio"))

    n_sobre = len(comp[comp["Estado"] == "Sobre-compra"])
    n_desab = len(comp[comp["Estado"] == "Desabastecimiento"])

    # ── KPIs ─────────────────────────────────────────────────────────────
    render_kpi_row([
        {"icon": "📦", "value": f"{int(comp['Comprado'].sum()):,}", "label": "Total Comprado (uds)"},
        {"icon": "🛒", "value": f"{int(comp['Vendido'].sum()):,}", "label": "Total Vendido (uds)"},
        {"icon": "📈", "value": f"{n_sobre}", "label": "Labs Sobre-compra"},
        {"icon": "📉", "value": f"{n_desab}", "label": "Labs Desabastecimiento"},
    ])
    render_divider()

    # ── Gráfico comparativo ──────────────────────────────────────────────
    render_section_header("⚖️", "Comprado vs Vendido por Laboratorio (Top 15)")
    comp["Volumen"] = comp["Comprado"] + comp["Vendido"]
    top15 = comp.nlargest(15, "Volumen").sort_values("Volumen", ascending=True)

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=top15["Laboratorio"].str[:28], x=top15["Comprado"],
        name="Comprado", orientation="h", marker_color=ACCENT))
    fig.add_trace(go.Bar(
        y=top15["Laboratorio"].str[:28], x=top15["Vendido"],
        name="Vendido", orientation="h", marker_color=CYAN))
    fig.update_layout(**PLOTLY_LAYOUT, barmode="group", height=480,
                      legend=dict(orientation="h", y=1.06, x=0.5, xanchor="center"))
    st.plotly_chart(fig, width="stretch")

    # ── Gráfico de diferencia ────────────────────────────────────────────
    render_section_header("📊", "Diferencia (Comprado − Vendido)")
    top15_d = comp.nlargest(15, "Volumen").sort_values("Diferencia", ascending=True)
    colores = [RED if d < 0 else GREEN for d in top15_d["Diferencia"]]
    fig = go.Figure(go.Bar(
        y=top15_d["Laboratorio"].str[:28], x=top15_d["Diferencia"],
        orientation="h", marker_color=colores))
    fig.update_layout(**PLOTLY_LAYOUT, height=430, xaxis_title="Diferencia (uds)")
    fig.add_vline(x=0, line_dash="dash", line_color="rgba(255,255,255,0.3)")
    st.plotly_chart(fig, width="stretch")

    # ── Top proveedores ──────────────────────────────────────────────────
    render_section_header("🏢", "Top 10 Proveedores por Volumen de Compra")
    top_prov = (df_c.groupby("PROVEEDOR", as_index=False)
                .agg(Unidades=("CANT", "sum"), Costo_Total=("Costo Total", "sum"))
                .nlargest(10, "Unidades"))
    st.dataframe(top_prov, width="stretch", hide_index=True,
                 column_config={
                     "PROVEEDOR": "Proveedor",
                     "Unidades": st.column_config.NumberColumn(format="%d"),
                     "Costo_Total": st.column_config.NumberColumn("Costo Total", format="$%d"),
                 })

    # ── Tabla filtrable ──────────────────────────────────────────────────
    render_section_header("📋", "Tabla Comparativa por Laboratorio")
    filtro_est = st.multiselect("Filtrar por estado:",
        ["Sobre-compra", "Desabastecimiento", "Equilibrio"],
        default=["Sobre-compra", "Desabastecimiento"], key="cv_filtro")
    tabla_f = comp[comp["Estado"].isin(filtro_est)].sort_values("Diferencia")
    st.dataframe(
        tabla_f[["Laboratorio", "Comprado", "Vendido", "Diferencia", "Estado"]],
        width="stretch", height=380, hide_index=True,
        column_config={
            "Comprado": st.column_config.NumberColumn(format="%d"),
            "Vendido": st.column_config.NumberColumn(format="%d"),
            "Diferencia": st.column_config.NumberColumn(format="%d"),
        })
