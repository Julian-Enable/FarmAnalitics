# =============================================================================
# tab_inventario.py — Tab 4: Alertas de Inventario
# =============================================================================
import streamlit as st
import plotly.express as px
from config import PLOTLY_LAYOUT, SEDE_PALETTE, SEDES_INVENTARIO
from components import render_kpi_row, render_section_header, render_divider


def render(df_v, df_c, df_i):
    """Renderiza la pestaña de Alertas de Inventario."""
    if df_i is None:
        st.warning("Sube el archivo de **inventario** para ver las alertas.")
        return

    # ── Cruzar con ventas si existen ─────────────────────────────────────
    if df_v is not None:
        v_agr = (df_v.groupby("Referencia", as_index=False)["Cant"]
                 .sum().rename(columns={"Cant": "Uds Vendidas"}))
        df_a = df_i.merge(v_agr, on="Referencia", how="left")
        df_a["Uds Vendidas"] = df_a["Uds Vendidas"].fillna(0)
        df_a["Rotacion"] = df_a.apply(
            lambda r: round(r["Uds Vendidas"] / r["Total"], 2) if r["Total"] > 0 else 0,
            axis=1,
        )
    else:
        df_a = df_i.copy()
        df_a["Uds Vendidas"] = 0
        df_a["Rotacion"] = 0

    # Productos bajo stock mínimo
    bajo = df_a[(df_a["Stock Minimo"] > 0) & (df_a["Total"] < df_a["Stock Minimo"])].copy()
    # Productos sin stock pero con ventas (urgentes)
    sin_stock = df_a[(df_a["Total"] == 0) & (df_a["Uds Vendidas"] > 0)]
    total_con_min = len(df_a[df_a["Stock Minimo"] > 0])
    pct = round(len(bajo) / total_con_min * 100, 1) if total_con_min > 0 else 0

    # ── KPIs ─────────────────────────────────────────────────────────────
    render_kpi_row([
        {"icon": "🚨", "value": f"{len(bajo):,}", "label": "Bajo Stock Mínimo"},
        {"icon": "📊", "value": f"{pct}%", "label": "% en Alerta"},
        {"icon": "❌", "value": f"{len(sin_stock):,}", "label": "Sin Stock (con ventas)"},
        {"icon": "📦", "value": f"{int(df_i['Total'].sum()):,}", "label": "Stock Total (uds)"},
    ])
    render_divider()

    # ── Tabla de alertas ─────────────────────────────────────────────────
    if bajo.empty:
        st.success("✅ No hay productos por debajo de su stock mínimo.")
    else:
        bajo["Deficit"] = bajo["Stock Minimo"] - bajo["Total"]
        bajo = bajo.sort_values("Deficit", ascending=False)

        render_section_header("📋", "Productos Bajo Stock Mínimo")
        cols_show = ["Referencia", "Descripcion", "Laboratorio", "Total",
                     "Stock Minimo", "Stock Maximo", "Deficit", "Uds Vendidas", "Rotacion"]
        cols_exist = [c for c in cols_show if c in bajo.columns]
        st.dataframe(
            bajo[cols_exist].reset_index(drop=True),
            width="stretch", height=420, hide_index=True,
            column_config={
                "Referencia": st.column_config.NumberColumn(format="%d"),
                "Total": st.column_config.NumberColumn("Stock Actual", format="%d"),
                "Deficit": st.column_config.NumberColumn("Déficit", format="%d"),
                "Rotacion": st.column_config.NumberColumn("Rotación", format="%.2f"),
            },
        )

        # Gráfico top 15 déficit
        render_section_header("📉", "Top 15 — Mayor Déficit de Stock")
        top_d = bajo.nlargest(15, "Deficit").sort_values("Deficit", ascending=True)
        top_d["Nombre"] = top_d["Descripcion"].str[:30]
        fig = px.bar(top_d, x="Deficit", y="Nombre", orientation="h",
                     color="Deficit", color_continuous_scale="Reds",
                     labels={"Deficit": "Uds faltantes", "Nombre": ""})
        fig.update_layout(**PLOTLY_LAYOUT, height=430,
                          coloraxis_showscale=False, showlegend=False)
        st.plotly_chart(fig, width="stretch")

    # ── Stock por sede ───────────────────────────────────────────────────
    sedes_exist = [c for c in SEDES_INVENTARIO if c in df_i.columns]
    if sedes_exist:
        render_section_header("🏪", "Stock Actual por Sede")
        stock_s = df_i[sedes_exist].sum().reset_index()
        stock_s.columns = ["Sede", "Unidades"]
        fig = px.bar(stock_s, x="Sede", y="Unidades", color="Sede",
                     color_discrete_sequence=SEDE_PALETTE)
        fig.update_layout(**PLOTLY_LAYOUT, height=320, showlegend=False)
        st.plotly_chart(fig, width="stretch")
