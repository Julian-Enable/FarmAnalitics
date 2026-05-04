# =============================================================================
# tab_rentabilidad.py — Tab 3: Rentabilidad y Márgenes
# =============================================================================
import streamlit as st
import plotly.express as px
from config import PLOTLY_LAYOUT, GREEN, ACCENT
from components import render_kpi_row, render_section_header, render_divider
from utils import fmt_cop


def render(df_v, df_c, df_i):
    """Renderiza la pestaña de Rentabilidad."""
    if df_v is None or df_i is None:
        st.warning("Sube archivos de **ventas** e **inventario** para ver la rentabilidad.")
        return
    if "Precio Compra" not in df_i.columns:
        st.warning("El inventario no tiene la columna **Precio Compra**.")
        return

    # ── Cruzar ventas con precios del inventario ─────────────────────────
    v_agg = df_v.groupby("Referencia", as_index=False).agg(
        Cant_Vend=("Cant", "sum"), Descripcion=("Descripcion", "first"),
        Laboratorio=("Laboratorio", "first"), Ingreso_Total=("Ingreso", "sum"),
    )
    cols_inv = ["Referencia", "Precio Compra", "Precio Venta"]
    if "Nivel" in df_i.columns:
        cols_inv.append("Nivel")
    inv_prices = df_i[cols_inv].groupby("Referencia", as_index=False).first()
    rent = v_agg.merge(inv_prices, on="Referencia", how="inner")
    rent["Costo_Total"] = rent["Precio Compra"] * rent["Cant_Vend"]
    rent["Utilidad_Total"] = rent["Ingreso_Total"] - rent["Costo_Total"]
    rent["Precio_Venta_Prom"] = rent["Ingreso_Total"] / rent["Cant_Vend"].where(rent["Cant_Vend"] != 0)
    rent["Margen_Unit"] = rent["Precio_Venta_Prom"] - rent["Precio Compra"]
    rent["Margen_Pct"] = ((rent["Utilidad_Total"] / rent["Ingreso_Total"]) * 100).round(2)
    rent["Margen_Pct"] = rent["Margen_Pct"].replace([float("inf"), float("-inf")], 0).fillna(0)

    util_total = rent["Utilidad_Total"].sum()
    ing_total = rent["Ingreso_Total"].sum()
    margen_global = (util_total / ing_total * 100) if ing_total > 0 else 0

    # ── KPIs ─────────────────────────────────────────────────────────────
    render_kpi_row([
        {"icon": "💰", "value": fmt_cop(util_total), "label": "Utilidad Bruta Total"},
        {"icon": "📊", "value": f"{margen_global:.1f}%", "label": "Margen Global"},
        {"icon": "📈", "value": fmt_cop(ing_total), "label": "Ingreso Total"},
        {"icon": "🔢", "value": f"{len(rent):,}", "label": "Productos Cruzados"},
    ])
    render_divider()

    # ── Gráficos ─────────────────────────────────────────────────────────
    r1, r2 = st.columns(2)

    with r1:
        render_section_header("🥇", "Top 15 Productos Más Rentables")
        top_r = rent.nlargest(15, "Utilidad_Total").sort_values("Utilidad_Total", ascending=True)
        top_r["Nombre"] = top_r["Descripcion"].str[:30]
        fig = px.bar(top_r, x="Utilidad_Total", y="Nombre", orientation="h",
                     color="Utilidad_Total", color_continuous_scale="Greens",
                     labels={"Utilidad_Total": "Utilidad ($)", "Nombre": ""})
        fig.update_layout(**PLOTLY_LAYOUT, height=450,
                          coloraxis_showscale=False, showlegend=False)
        st.plotly_chart(fig, width="stretch")

    with r2:
        render_section_header("⚠️", "Top 15 Menor Margen %")
        bajo = (rent[rent["Cant_Vend"] >= 5]
                .nsmallest(15, "Margen_Pct")
                .sort_values("Margen_Pct", ascending=False))
        bajo["Nombre"] = bajo["Descripcion"].str[:30]
        fig = px.bar(bajo, x="Margen_Pct", y="Nombre", orientation="h",
                     color="Margen_Pct", color_continuous_scale="RdYlGn",
                     labels={"Margen_Pct": "Margen %", "Nombre": ""})
        fig.update_layout(**PLOTLY_LAYOUT, height=450,
                          coloraxis_showscale=False, showlegend=False)
        st.plotly_chart(fig, width="stretch")

    r3, r4 = st.columns(2)

    with r3:
        render_section_header("📂", "Utilidad por Categoría")
        cat_u = (rent.groupby("Nivel", as_index=False)["Utilidad_Total"]
                 .sum().sort_values("Utilidad_Total", ascending=True))
        fig = px.bar(cat_u, x="Utilidad_Total", y="Nivel", orientation="h",
                     color_discrete_sequence=[GREEN])
        fig.update_layout(**PLOTLY_LAYOUT, height=400, showlegend=False)
        st.plotly_chart(fig, width="stretch")

    with r4:
        render_section_header("🏭", "Utilidad por Laboratorio (Top 10)")
        lab_u = (rent.groupby("Laboratorio", as_index=False)["Utilidad_Total"]
                 .sum().nlargest(10, "Utilidad_Total")
                 .sort_values("Utilidad_Total", ascending=True))
        lab_u["Lab"] = lab_u["Laboratorio"].str[:25]
        fig = px.bar(lab_u, x="Utilidad_Total", y="Lab", orientation="h",
                     color_discrete_sequence=[ACCENT])
        fig.update_layout(**PLOTLY_LAYOUT, height=400, showlegend=False)
        st.plotly_chart(fig, width="stretch")
