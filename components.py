# =============================================================================
# components.py — Componentes UI modo claro
# =============================================================================
import streamlit as st


def render_main_header():
    """Encabezado principal modo claro."""
    st.markdown("""
        <div style="padding:0.5rem 0 1.5rem;">
            <div style="font-family:'Inter',system-ui,sans-serif;
                        font-size:1.75rem;font-weight:700;color:#111827;
                        letter-spacing:-0.025em;line-height:1.2;margin-bottom:4px;">
                📊 Dashboard Farmacéutico
            </div>
            <div style="font-family:'Inter',system-ui,sans-serif;
                        font-size:0.9rem;color:#6B7280;margin-bottom:12px;">
                Análisis integral de Ventas, Compras e Inventario del POS
            </div>
            <div style="height:3px;width:180px;border-radius:3px;
                        background:#5E6AD2;opacity:0.85;"></div>
        </div>
    """, unsafe_allow_html=True)


def render_section_header(icon, title):
    """Encabezado de sección modo claro."""
    st.markdown(
        f'<div style="font-family:\'Inter\',system-ui,sans-serif;'
        f'font-size:1rem;font-weight:600;color:#111827;'
        f'letter-spacing:-0.01em;margin:0.2rem 0 0.65rem;">'
        f'{icon}&nbsp; {title}</div>',
        unsafe_allow_html=True,
    )


def render_divider():
    """Línea divisora."""
    st.markdown(
        '<div style="height:1px;background:#E5E7EB;margin:1.2rem 0;"></div>',
        unsafe_allow_html=True,
    )


def render_kpi_row(metrics):
    """Fila de KPI cards modo claro."""
    n = len(metrics)
    cols = 3 if n <= 3 else (4 if n <= 4 else 6)

    cards = ""
    for m in metrics:
        cards += (
            f'<div style="background:#FFFFFF;border:1px solid #E5E7EB;'
            f'border-top:3px solid #5E6AD2;border-radius:12px;'
            f'padding:18px 18px 14px;box-shadow:0 1px 6px rgba(0,0,0,0.06);">'
            f'  <div style="font-size:1.15rem;margin-bottom:8px;">{m["icon"]}</div>'
            f'  <div style="font-family:\'Inter\',system-ui,sans-serif;font-size:1.4rem;'
            f'font-weight:700;color:#111827;letter-spacing:-0.02em;'
            f'line-height:1.2;margin-bottom:4px;">{m["value"]}</div>'
            f'  <div style="font-family:\'Inter\',system-ui,sans-serif;font-size:0.76rem;'
            f'font-weight:500;color:#6B7280;">{m["label"]}</div>'
            f'</div>'
        )

    st.markdown(
        f'<div style="display:grid;grid-template-columns:repeat({cols},1fr);'
        f'gap:14px;margin-bottom:1.4rem;">{cards}</div>',
        unsafe_allow_html=True,
    )
