# =============================================================================
# tab_sedes.py — Tab 6: Rendimiento por Sede
# =============================================================================
import streamlit as st
import plotly.express as px
from config import PLOTLY_LAYOUT, ACCENT, SEDE_PALETTE, SEDES_INVENTARIO
from components import render_kpi_row, render_section_header, render_divider
from utils import fmt_cop


def render(df_v, df_c, df_i):
    """Renderiza la pestaña de Rendimiento por Sede."""
    if df_v is None:
        st.warning("Sube archivos de **ventas** para ver el rendimiento por sede.")
        return

    # ── Tabla comparativa ────────────────────────────────────────────────
    render_section_header("🏪", "Comparativo entre Puntos de Venta")
    sede_comp = df_v.groupby("Punto Venta").agg(
        Ingresos=("Ingreso", "sum"), Unidades=("Cant", "sum"),
        Facturas=("Factura", "nunique"),
        Productos_Unicos=("Referencia", "nunique"),
    ).reset_index()
    sede_comp["Ticket Prom."] = (sede_comp["Ingresos"] / sede_comp["Facturas"]).round(0)
    sede_comp["Uds/Factura"] = (sede_comp["Unidades"] / sede_comp["Facturas"]).round(1)
    sede_comp = sede_comp.sort_values("Ingresos", ascending=False)

    # ── KPIs de sedes ────────────────────────────────────────────────
    n_sedes      = len(sede_comp)
    top_sede     = sede_comp.iloc[0]["Punto Venta"] if n_sedes > 0 else "—"
    top_sede_ing = sede_comp.iloc[0]["Ingresos"]    if n_sedes > 0 else 0
    top_ticket   = sede_comp["Ticket Prom."].max()  if n_sedes > 0 else 0
    top_ticket_sede = (
        sede_comp.loc[sede_comp["Ticket Prom."].idxmax(), "Punto Venta"]
        if n_sedes > 0 else "—"
    )
    total_uds    = int(sede_comp["Unidades"].sum())
    total_ing    = sede_comp["Ingresos"].sum()

    render_kpi_row([
        {"icon": "🏪", "value": f"{n_sedes}",                  "label": "Puntos de Venta"},
        {"icon": "🏆", "value": str(top_sede)[:18],          "label": "Top Sede (Ingresos)"},
        {"icon": "💵", "value": fmt_cop(top_sede_ing),         "label": "Ingresos Top Sede"},
        {"icon": "🎫", "value": fmt_cop(top_ticket),          "label": f"Mejor Ticket ({str(top_ticket_sede)[:12]})"},
        {"icon": "📦", "value": f"{total_uds:,}",             "label": "Unidades Totales"},
        {"icon": "📊", "value": fmt_cop(total_ing),            "label": "Ingresos Totales"},
    ])
    render_divider()

    st.dataframe(sede_comp, width="stretch", hide_index=True,
                 column_config={
                     "Punto Venta": "Sede",
                     "Ingresos": st.column_config.NumberColumn(format="$%d"),
                     "Unidades": st.column_config.NumberColumn(format="%d"),
                     "Ticket Prom.": st.column_config.NumberColumn(format="$%d"),
                 })

    render_divider()
    s1, s2 = st.columns(2)

    with s1:
        render_section_header("💵", "Ingresos por Sede")
        fig = px.bar(sede_comp.sort_values("Ingresos", ascending=True),
                     x="Ingresos", y="Punto Venta", orientation="h",
                     color="Punto Venta", color_discrete_sequence=SEDE_PALETTE)
        fig.update_layout(**PLOTLY_LAYOUT, height=320, showlegend=False)
        st.plotly_chart(fig, width="stretch")

    with s2:
        render_section_header("📦", "Unidades por Sede")
        fig = px.bar(sede_comp.sort_values("Unidades", ascending=True),
                     x="Unidades", y="Punto Venta", orientation="h",
                     color="Punto Venta", color_discrete_sequence=SEDE_PALETTE)
        fig.update_layout(**PLOTLY_LAYOUT, height=320, showlegend=False)
        st.plotly_chart(fig, width="stretch")

    # ── Top 5 por sede ───────────────────────────────────────────────────
    render_section_header("🏆", "Top 5 Productos por Sede")
    sede_sel = st.selectbox(
        "Selecciona una sede:",
        sorted(df_v["Punto Venta"].dropna().unique().tolist()),
        key="sede_top5",
    )
    df_sede = df_v[df_v["Punto Venta"] == sede_sel]
    top5 = (df_sede.groupby(["Referencia", "Descripcion"], as_index=False)["Cant"]
            .sum().nlargest(5, "Cant").sort_values("Cant", ascending=True))
    top5["Nombre"] = top5["Descripcion"].str[:35]
    fig = px.bar(top5, x="Cant", y="Nombre", orientation="h",
                 color_discrete_sequence=[ACCENT],
                 labels={"Cant": "Unidades", "Nombre": ""})
    fig.update_layout(**PLOTLY_LAYOUT, height=280, showlegend=False)
    st.plotly_chart(fig, width="stretch")

    # ── Stock por sede (inventario) ──────────────────────────────────────
    if df_i is not None:
        sedes_ex = [c for c in SEDES_INVENTARIO if c in df_i.columns]
        if sedes_ex:
            render_section_header("📦", "Stock Actual por Sede (Inventario)")
            stock_s = df_i[sedes_ex].sum().reset_index()
            stock_s.columns = ["Sede", "Unidades"]
            fig = px.bar(stock_s, x="Sede", y="Unidades", color="Sede",
                         color_discrete_sequence=SEDE_PALETTE)
            fig.update_layout(**PLOTLY_LAYOUT, height=300, showlegend=False)
            st.plotly_chart(fig, width="stretch")
