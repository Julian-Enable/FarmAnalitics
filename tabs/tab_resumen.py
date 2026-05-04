# =============================================================================
# tab_resumen.py — Tab 1: Resumen General (Overview ejecutivo)
# =============================================================================
import streamlit as st
import plotly.express as px
from config import PLOTLY_LAYOUT, ACCENT, SEDE_PALETTE
from components import render_kpi_row, render_section_header, render_divider
from utils import fmt_cop


def render(df_v, df_c, df_i):
    """Renderiza la pestaña de Resumen General."""
    if df_v is None:
        st.warning("Sube archivos de **ventas** para ver el resumen.")
        return

    # ── Calcular KPIs ────────────────────────────────────────────────────
    total_ing = df_v["Ingreso"].sum()
    total_und = int(df_v["Cant"].sum())
    n_fact = df_v["Factura"].nunique() if "Factura" in df_v.columns else 0
    ticket_prom = total_ing / n_fact if n_fact > 0 else 0

    # Utilidad bruta (si hay inventario con precio de compra)
    kpis = [
        {"icon": "💵", "value": fmt_cop(total_ing), "label": "Ingresos Totales"},
        {"icon": "📦", "value": f"{total_und:,}", "label": "Unidades Vendidas"},
        {"icon": "🧾", "value": f"{n_fact:,}", "label": "Facturas"},
        {"icon": "🎫", "value": fmt_cop(ticket_prom), "label": "Ticket Promedio"},
    ]

    if df_i is not None and "Precio Compra" in df_i.columns:
        v_agg = df_v.groupby("Referencia", as_index=False).agg(
            Cant=("Cant", "sum"), Ingreso=("Ingreso", "sum")
        )
        inv_cost = df_i[["Referencia", "Precio Compra"]].groupby("Referencia", as_index=False).first()
        merged = v_agg.merge(inv_cost, on="Referencia", how="inner")
        merged["Util"] = merged["Ingreso"] - (merged["Precio Compra"] * merged["Cant"])
        util_bruta = merged["Util"].sum()
        margen_prom = (util_bruta / total_ing * 100) if total_ing > 0 else 0
        kpis.append({"icon": "💰", "value": fmt_cop(util_bruta), "label": "Utilidad Bruta"})
        kpis.append({"icon": "📊", "value": f"{margen_prom:.1f}%", "label": "Margen Promedio"})

    render_kpi_row(kpis)
    render_divider()

    # ── Gráficos ─────────────────────────────────────────────────────────
    c1, c2 = st.columns(2)

    with c1:
        render_section_header("📅", "Tendencia Semanal de Ingresos")
        if df_v["Fecha"].notna().any():
            semanal = df_v.set_index("Fecha").resample("W")["Ingreso"].sum().reset_index()
            fig = px.area(semanal, x="Fecha", y="Ingreso",
                          color_discrete_sequence=[ACCENT])
            fig.update_traces(line=dict(width=2), fillcolor="rgba(94,106,210,0.15)")
            fig.update_layout(**PLOTLY_LAYOUT, height=320, showlegend=False)
            st.plotly_chart(fig, width="stretch")

    with c2:
        render_section_header("🏪", "Ingresos por Punto de Venta")
        sede_ing = df_v.groupby("Punto Venta", as_index=False)["Ingreso"].sum()
        fig = px.pie(sede_ing, names="Punto Venta", values="Ingreso",
                     hole=0.55, color_discrete_sequence=SEDE_PALETTE)
        fig.update_traces(textinfo="percent+label", textfont_size=11)
        fig.update_layout(**PLOTLY_LAYOUT, height=320)
        st.plotly_chart(fig, width="stretch")

    # ── Tabla resumen por sede ───────────────────────────────────────────
    render_section_header("📋", "Rendimiento por Punto de Venta")
    resumen = df_v.groupby("Punto Venta").agg(
        Ingresos=("Ingreso", "sum"), Unidades=("Cant", "sum"),
        Facturas=("Factura", "nunique") if "Factura" in df_v.columns else ("Cant", "count"),
    ).reset_index()
    resumen["Ticket Prom."] = (resumen["Ingresos"] / resumen["Facturas"]).round(0)
    resumen = resumen.sort_values("Ingresos", ascending=False)
    st.dataframe(resumen, width="stretch", hide_index=True,
                 column_config={
                     "Ingresos": st.column_config.NumberColumn(format="$%d"),
                     "Unidades": st.column_config.NumberColumn(format="%d"),
                     "Ticket Prom.": st.column_config.NumberColumn(format="$%d"),
                 })
