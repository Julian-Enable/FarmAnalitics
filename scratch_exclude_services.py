import os
import re

path_analytics = r'c:\Users\FarmazionSAS\Documents\Dev\Proyectos Varios\Pruebas\backend\routers\analytics.py'

with open(path_analytics, 'r', encoding='utf-8') as f:
    content_analytics = f.read()

# Add service exclusion logic to Inventario
old_inv = """    df_a = _inventory_with_total(df_i)

    # ── Filtrar ventas esporádicas para rotación ──"""

new_inv = """    df_a = _inventory_with_total(df_i)

    # Excluir servicios (domicilios, inyectología, fletes)
    es_servicio = (df_a["Nivel"].astype(str).str.upper() == "SERVICIOS") | (df_a["Descripcion"].astype(str).str.contains("DOMICILIO|INYECTOLOGIA|FLETE|TARIFA DE SERVICIO", case=False, na=False))
    df_a = df_a[~es_servicio].copy()

    # ── Filtrar ventas esporádicas para rotación ──"""

# Also exclude from sugerido_traslados and pedido_por_proveedor inside management_analytics.py
path_mgmt = r'c:\Users\FarmazionSAS\Documents\Dev\Proyectos Varios\Pruebas\backend\services\management_analytics.py'

with open(path_mgmt, 'r', encoding='utf-8') as f:
    content_mgmt = f.read()

old_traslados = """def sugerido_traslados(ventas: pd.DataFrame, inventario: pd.DataFrame, min_days: int = 12, target_days: int = 25, max_days: int = 55) -> dict[str, Any]:
    sales, dias, _ = _period_sales(ventas, 35)
    sedes = inventory_sede_columns(inventario)
    if sales.empty or inventario is None or inventario.empty or not sedes:
        return {"kpis": {"sugerencias": 0, "unidades": 0}, "sugerencias": [], "sedes": sedes}

    # Filtrar ventas esporádicas para demanda de traslados"""

new_traslados = """def sugerido_traslados(ventas: pd.DataFrame, inventario: pd.DataFrame, min_days: int = 12, target_days: int = 25, max_days: int = 55) -> dict[str, Any]:
    sales, dias, _ = _period_sales(ventas, 35)
    sedes = inventory_sede_columns(inventario)
    if sales.empty or inventario is None or inventario.empty or not sedes:
        return {"kpis": {"sugerencias": 0, "unidades": 0}, "sugerencias": [], "sedes": sedes}

    # Excluir servicios
    if "Descripcion" in inventario.columns:
        es_servicio = (inventario.get("Nivel", "").astype(str).str.upper() == "SERVICIOS") | (inventario["Descripcion"].astype(str).str.contains("DOMICILIO|INYECTOLOGIA|FLETE|TARIFA DE SERVICIO", case=False, na=False))
        inventario = inventario[~es_servicio].copy()

    # Filtrar ventas esporádicas para demanda de traslados"""

old_pedidos = """def pedido_por_proveedor(ventas: pd.DataFrame, compras: pd.DataFrame, inventario: pd.DataFrame, target_days: int = 35, min_days: int = 15) -> dict[str, Any]:
    sales_raw, dias, _ = _period_sales(ventas, 35)
    if sales_raw.empty or inventario is None or inventario.empty:
        return {"kpis": {"proveedores": 0, "items": 0, "costo_estimado": 0}, "proveedores": [], "items": []}

    # Filtrar ventas esporádicas para sugeridos de compra"""

new_pedidos = """def pedido_por_proveedor(ventas: pd.DataFrame, compras: pd.DataFrame, inventario: pd.DataFrame, target_days: int = 35, min_days: int = 15) -> dict[str, Any]:
    sales_raw, dias, _ = _period_sales(ventas, 35)
    if sales_raw.empty or inventario is None or inventario.empty:
        return {"kpis": {"proveedores": 0, "items": 0, "costo_estimado": 0}, "proveedores": [], "items": []}

    # Excluir servicios
    if "Descripcion" in inventario.columns:
        es_servicio = (inventario.get("Nivel", "").astype(str).str.upper() == "SERVICIOS") | (inventario["Descripcion"].astype(str).str.contains("DOMICILIO|INYECTOLOGIA|FLETE|TARIFA DE SERVICIO", case=False, na=False))
        inventario = inventario[~es_servicio].copy()

    # Filtrar ventas esporádicas para sugeridos de compra"""

content_analytics = content_analytics.replace('\r\n', '\n')
old_inv = old_inv.replace('\r\n', '\n')

content_mgmt = content_mgmt.replace('\r\n', '\n')
old_traslados = old_traslados.replace('\r\n', '\n')
old_pedidos = old_pedidos.replace('\r\n', '\n')

if old_inv in content_analytics and old_traslados in content_mgmt and old_pedidos in content_mgmt:
    content_analytics = content_analytics.replace(old_inv, new_inv)
    with open(path_analytics, 'w', encoding='utf-8') as f:
        f.write(content_analytics)
    
    content_mgmt = content_mgmt.replace(old_traslados, new_traslados)
    content_mgmt = content_mgmt.replace(old_pedidos, new_pedidos)
    with open(path_mgmt, 'w', encoding='utf-8') as f:
        f.write(content_mgmt)
        
    print("SUCCESS: Excluded services from inventory logic.")
else:
    print("FAILED TO FIND TARGET BLOCKS")
    print(f"inv: {old_inv in content_analytics}")
    print(f"tras: {old_traslados in content_mgmt}")
    print(f"ped: {old_pedidos in content_mgmt}")
