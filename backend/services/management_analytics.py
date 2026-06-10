from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import json
import numpy as np
import pandas as pd


EXCLUDED_INVENTORY_COLUMNS = {
    "Referencia",
    "Descripcion",
    "ID_Laboratorio",
    "Laboratorio",
    "ID_Nivel",
    "Nivel",
    "Total",
    "Precio Compra",
    "Precio Venta",
    "Stock Minimo",
    "Stock Maximo",
    "Comision",
    "Utilidad",
    "Codigo",
    "IVA",
}


def _records(df: pd.DataFrame, limit: int | None = None) -> list[dict[str, Any]]:
    if df is None or df.empty:
        return []
    out = df.copy()
    if limit:
        out = out.head(limit)
    out = out.replace([np.inf, -np.inf], np.nan)
    return json.loads(out.to_json(orient="records", date_format="iso"))


def _num(series, default=0):
    return pd.to_numeric(series, errors="coerce").fillna(default)


def inventory_sede_columns(inventario: pd.DataFrame) -> list[str]:
    if inventario is None or inventario.empty:
        return []
    cols = []
    for col in inventario.columns:
        if col in EXCLUDED_INVENTORY_COLUMNS:
            continue
        if pd.api.types.is_numeric_dtype(inventario[col]) and _num(inventario[col]).abs().sum() > 0:
            cols.append(col)
    return cols


# ── Detección de Ventas Esporádicas ──────────────────────────────────────────
# Identifica picos de venta atípicos (licitaciones, pedidos institucionales)
# que no representan demanda sostenida y contaminarían los cálculos de rotación,
# sugeridos de compra y traslados.
#
# Se mantienen intactas para Ingresos totales, Rentabilidad y Resumen General.
# Solo se excluyen en: rotación diaria, cobertura, sugeridos de compra/traslado.

SPORADIC_IQR_MULTIPLIER = 3.0   # Qué tan agresivo es el filtro (3 = estándar Tukey)
SPORADIC_MIN_SALE_DAYS = 5      # Mínimo de días con venta para aplicar filtro


def _tag_sporadic(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Analiza un DataFrame de ventas y separa líneas normales de esporádicas.

    Retorna:
        (df_normal, df_sporadic_summary)
        - df_normal: DataFrame con las líneas de venta que representan demanda regular.
        - df_sporadic_summary: DataFrame con Referencia, uds_esporadicas_excluidas,
          dias_esporadicos para informar al usuario.
    """
    if df is None or df.empty or "Fecha" not in df.columns or "Referencia" not in df.columns:
        return df, pd.DataFrame(columns=["Referencia", "uds_esporadicas_excluidas", "dias_esporadicos"])

    work = df.copy()
    work["Fecha"] = pd.to_datetime(work["Fecha"], errors="coerce")
    work["_dia"] = work["Fecha"].dt.normalize()

    # Agrupar cantidad diaria por producto
    daily = work.groupby(["Referencia", "_dia"], as_index=False)["Cant"].sum()

    # Calcular estadísticos por producto
    stats = daily.groupby("Referencia", as_index=False).agg(
        dias_venta=("_dia", "nunique"),
        q1=("Cant", lambda x: x.quantile(0.25)),
        q3=("Cant", lambda x: x.quantile(0.75)),
        mediana=("Cant", "median"),
    )
    stats["iqr"] = stats["q3"] - stats["q1"]
    # Para productos con IQR=0 (siempre venden igual), usar la mediana como referencia
    stats["iqr"] = stats["iqr"].where(stats["iqr"] > 0, stats["mediana"] * 0.5)
    # Umbral: mediana + N * IQR
    stats["umbral"] = stats["mediana"] + SPORADIC_IQR_MULTIPLIER * stats["iqr"]
    # Mínimo umbral de seguridad: al menos 2x la mediana
    stats["umbral"] = np.maximum(stats["umbral"], stats["mediana"] * 2)

    # Solo aplicar a productos con suficiente historial
    stats["aplicar_filtro"] = stats["dias_venta"] >= SPORADIC_MIN_SALE_DAYS

    # Merge para saber el umbral de cada producto-día
    daily_with_threshold = daily.merge(
        stats[["Referencia", "umbral", "aplicar_filtro"]],
        on="Referencia",
        how="left",
    )

    # Marcar días esporádicos
    daily_with_threshold["es_esporadico"] = (
        daily_with_threshold["aplicar_filtro"]
        & (daily_with_threshold["Cant"] > daily_with_threshold["umbral"])
    )

    # Set de (Referencia, día) esporádicos
    sporadic_keys = set(
        zip(
            daily_with_threshold.loc[daily_with_threshold["es_esporadico"], "Referencia"],
            daily_with_threshold.loc[daily_with_threshold["es_esporadico"], "_dia"],
        )
    )

    if not sporadic_keys:
        return df, pd.DataFrame(columns=["Referencia", "uds_esporadicas_excluidas", "dias_esporadicos"])

    # Marcar líneas originales
    work["_es_esporadico"] = list(zip(work["Referencia"], work["_dia"]))
    work["_es_esporadico"] = work["_es_esporadico"].isin(sporadic_keys)

    df_normal = work[~work["_es_esporadico"]].drop(columns=["_dia", "_es_esporadico"])
    df_esporadico = work[work["_es_esporadico"]].copy()

    # Resumen de lo excluido (para mostrar al usuario)
    if not df_esporadico.empty:
        sporadic_summary = df_esporadico.groupby("Referencia", as_index=False).agg(
            uds_esporadicas_excluidas=("Cant", "sum"),
            dias_esporadicos=("_dia", "nunique"),
        )
    else:
        sporadic_summary = pd.DataFrame(columns=["Referencia", "uds_esporadicas_excluidas", "dias_esporadicos"])

    return df_normal, sporadic_summary


def _period_sales(ventas: pd.DataFrame, days: int = 35) -> tuple[pd.DataFrame, int, pd.Timestamp | None]:
    if ventas is None or ventas.empty or "Fecha" not in ventas.columns:
        return pd.DataFrame(), 1, None
    df = ventas.copy()
    df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce")
    df = df[df["Fecha"].notna()]
    if df.empty:
        return df, 1, None
    max_fecha = df["Fecha"].max()
    start = max_fecha - pd.Timedelta(days=days - 1)
    df = df[df["Fecha"] >= start]
    min_fecha = df["Fecha"].min()
    dias = max((max_fecha.normalize() - min_fecha.normalize()).days + 1, 1)
    return df, dias, max_fecha


def _profit_by_product(ventas: pd.DataFrame, compras: pd.DataFrame, inventario: pd.DataFrame, days: int = 35) -> tuple[pd.DataFrame, int]:
    sales, dias, max_fecha = _period_sales(ventas, days)
    if sales.empty or inventario is None or inventario.empty:
        return pd.DataFrame(), dias

    # Filtrar ventas esporádicas para rotación (pero usar sales completo para ingresos)
    sales_filtered, _ = _tag_sporadic(sales)
    if sales_filtered is None or sales_filtered.empty:
        sales_filtered = sales

    # Agrupar con datos filtrados para rotación, pero con datos completos para ingresos
    base_filtered = sales_filtered.groupby("Referencia", as_index=False).agg(
        cant_vend_filtrada=("Cant", "sum"),
    )
    base_full = sales.groupby("Referencia", as_index=False).agg(
        nombre=("Descripcion", "last"),
        cant_vend=("Cant", "sum"),
        ingreso_total=("Ingreso", "sum"),
        lab=("Laboratorio", "last") if "Laboratorio" in sales.columns else ("Referencia", "last"),
        sede=("Punto Venta", "last") if "Punto Venta" in sales.columns else ("Referencia", "last"),
    )
    base = base_full.merge(base_filtered, on="Referencia", how="left")
    base["cant_vend_filtrada"] = base["cant_vend_filtrada"].fillna(0)
    # cant_vend sigue siendo el total real (para ingresos/utilidad)
    # cant_vend_filtrada se usará para rotación diaria
    base = base[base["cant_vend"] > 0].copy()
    if base.empty:
        return pd.DataFrame(), dias

    inv_cols = ["Referencia", "Precio Compra", "Precio Venta", "Total", "Descripcion"]
    inv_cols = [c for c in inv_cols if c in inventario.columns]
    inv = inventario[inv_cols].drop_duplicates("Referencia").copy()
    for col in ["Precio Compra", "Precio Venta", "Total"]:
        if col in inv.columns:
            inv[col] = _num(inv[col])

    base = base.merge(inv, on="Referencia", how="left", suffixes=("", "_inv"))
    
    # 1. Obtener costo transaccional si existe en Ventas
    if "Costo" in sales.columns:
        costo_real = sales.groupby("Referencia", as_index=False).agg(costo_real_total=("Costo", "sum"))
        base = base.merge(costo_real, on="Referencia", how="left")
        base["precio_compra_tx"] = np.where(
            base["cant_vend"] > 0,
            _num(base.get("costo_real_total", 0)) / base["cant_vend"],
            0
        )
        base["precio_compra_tx"] = base["precio_compra_tx"].fillna(0)
    else:
        base["precio_compra_tx"] = 0

    # 2. Calcular costo promedio ponderado usando compras e historiales
    if compras is not None and not compras.empty and {"REFERENCIA", "PRECIO", "CANT"}.issubset(compras.columns):
        comp = compras.copy()
        comp["FECHA"] = pd.to_datetime(comp["FECHA"], errors="coerce")
        comp["PRECIO"] = _num(comp["PRECIO"])
        comp["CANT"] = _num(comp["CANT"])
        
        if "Costo Total" not in comp.columns:
            comp["Costo Total"] = comp["CANT"] * comp["PRECIO"]
        else:
            comp["Costo Total"] = _num(comp["Costo Total"])

        # Compras recientes: ventana de 90 días hacia atrás desde max_fecha de ventas
        if max_fecha is not None:
            start_date = max_fecha - pd.Timedelta(days=90)
            comp_recent = comp[(comp["FECHA"] >= start_date) & (comp["FECHA"] <= max_fecha)]
        else:
            comp_recent = comp

        # Costo Promedio Ponderado de compras recientes
        grp_recent = comp_recent.groupby("REFERENCIA").agg(
            total_spent=("Costo Total", "sum"),
            total_units=("CANT", "sum")
        )
        grp_recent["cpp_recent"] = np.where(
            grp_recent["total_units"] > 0,
            grp_recent["total_spent"] / grp_recent["total_units"],
            np.nan
        )

        # Última compra histórica absoluta (de respaldo si no hay compras en ventana 90d)
        comp_sorted = comp[comp["PRECIO"] > 0].sort_values("FECHA")
        last_purch = comp_sorted.groupby("REFERENCIA").last().reset_index()
        last_purch = last_purch[["REFERENCIA", "PRECIO"]].rename(columns={"PRECIO": "precio_last_compra"})

        base = base.merge(grp_recent[["cpp_recent"]].reset_index().rename(columns={"REFERENCIA": "Referencia"}), on="Referencia", how="left")
        base = base.merge(last_purch.rename(columns={"REFERENCIA": "Referencia"}), on="Referencia", how="left")

        # Cascada de decisión: 1. Transaccional Ventas -> 2. CPP Compras 90d -> 3. Última Compra -> 4. Catálogo Inventario
        base["precio_compra"] = np.where(
            base["precio_compra_tx"] > 0,
            base["precio_compra_tx"],
            base["cpp_recent"].fillna(base["precio_last_compra"]).fillna(_num(base.get("Precio Compra", 0)))
        )
    else:
        base["precio_compra"] = np.where(
            base["precio_compra_tx"] > 0,
            base["precio_compra_tx"],
            _num(base.get("Precio Compra", 0))
        )
    base["precio_venta_config"] = _num(base.get("Precio Venta", 0))
    base["stock_total"] = _num(base.get("Total", 0))
    base["precio_venta_prom"] = base["ingreso_total"] / base["cant_vend"].replace(0, np.nan)
    base["utilidad_unit"] = base["precio_venta_prom"] - base["precio_compra"]
    base["utilidad_total"] = base["utilidad_unit"] * base["cant_vend"]
    base["margen_pct"] = np.where(
        base["precio_venta_prom"] > 0,
        (base["utilidad_unit"] / base["precio_venta_prom"]) * 100,
        0,
    )
    base["rotacion_diaria"] = base["cant_vend_filtrada"] / max(dias, 1)
    base["capital_actual"] = base["stock_total"] * base["precio_compra"]
    base["precio_desviado_pct"] = np.where(
        base["precio_venta_config"] > 0,
        ((base["precio_venta_prom"] / base["precio_venta_config"]) - 1) * 100,
        0,
    )
    return base.replace([np.inf, -np.inf], np.nan).fillna(0), dias


def rentabilidad_gerencial(ventas: pd.DataFrame, compras: pd.DataFrame, inventario: pd.DataFrame) -> dict[str, Any]:
    profit, dias = _profit_by_product(ventas, compras, inventario, 35)
    if profit.empty:
        return {
            "kpis": {"fugas_margen": 0, "vendidos_bajo_costo": 0, "precio_desviado": 0, "sedes_baja_utilidad": 0},
            "bajo_margen_alta_venta": [],
            "vendidos_bajo_costo": [],
            "precio_mal_configurado": [],
            "laboratorios_capital": [],
            "sedes_ingreso_baja_utilidad": [],
        }

    q_alta = max(float(profit["cant_vend"].quantile(0.8)), 5)
    bajo_margen = profit[(profit["cant_vend"] >= q_alta) & (profit["margen_pct"] < 8)].copy()
    bajo_costo = profit[profit["utilidad_unit"] < 0].copy()
    precio_mal = profit[(profit["precio_venta_config"] > 0) & (profit["precio_desviado_pct"].abs() >= 15)].copy()

    lab = profit.groupby("lab", as_index=False).agg(
        ingreso_total=("ingreso_total", "sum"),
        utilidad_total=("utilidad_total", "sum"),
        capital_actual=("capital_actual", "sum"),
        productos=("Referencia", "nunique"),
    )
    lab["margen_pct"] = np.where(lab["ingreso_total"] > 0, lab["utilidad_total"] / lab["ingreso_total"] * 100, 0)
    lab["utilidad_sobre_capital"] = np.where(lab["capital_actual"] > 0, lab["utilidad_total"] / lab["capital_actual"] * 100, 0)

    sede = profit.groupby("sede", as_index=False).agg(
        ingreso_total=("ingreso_total", "sum"),
        utilidad_total=("utilidad_total", "sum"),
        productos=("Referencia", "nunique"),
    )
    sede["margen_pct"] = np.where(sede["ingreso_total"] > 0, sede["utilidad_total"] / sede["ingreso_total"] * 100, 0)
    ingreso_alto = sede["ingreso_total"].quantile(0.6) if len(sede) else 0
    sedes_fuga = sede[(sede["ingreso_total"] >= ingreso_alto) & (sede["margen_pct"] < 12)].copy()

    return {
        "kpis": {
            "fugas_margen": int(len(bajo_margen)),
            "vendidos_bajo_costo": int(len(bajo_costo)),
            "precio_desviado": int(len(precio_mal)),
            "sedes_baja_utilidad": int(len(sedes_fuga)),
            "dias_periodo": int(dias),
        },
        "bajo_margen_alta_venta": _records(bajo_margen.sort_values(["cant_vend", "margen_pct"], ascending=[False, True]), 30),
        "vendidos_bajo_costo": _records(bajo_costo.sort_values("utilidad_total"), 30),
        "precio_mal_configurado": _records(precio_mal.sort_values("precio_desviado_pct", key=lambda s: s.abs(), ascending=False), 30),
        "laboratorios_capital": _records(lab.sort_values("capital_actual", ascending=False), 30),
        "sedes_ingreso_baja_utilidad": _records(sedes_fuga.sort_values("ingreso_total", ascending=False), 20),
    }


def sugerido_traslados(ventas: pd.DataFrame, inventario: pd.DataFrame, min_days: int = 12, target_days: int = 25, max_days: int = 55) -> dict[str, Any]:
    sales, dias, _ = _period_sales(ventas, 35)
    sedes = inventory_sede_columns(inventario)
    if sales.empty or inventario is None or inventario.empty or not sedes:
        return {"kpis": {"sugerencias": 0, "unidades": 0}, "sugerencias": [], "sedes": sedes}

    # Excluir servicios
    if "Descripcion" in inventario.columns:
        es_servicio = (inventario.get("Nivel", "").astype(str).str.upper() == "SERVICIOS") | (inventario["Descripcion"].astype(str).str.contains("DOMICILIO|INYECTOLOGIA|FLETE|TARIFA DE SERVICIO|PERIODICO", case=False, na=False))
        inventario = inventario[~es_servicio].copy()

    # Filtrar ventas esporádicas para demanda de traslados
    sales_filtered, sporadic_summary = _tag_sporadic(sales)
    if sales_filtered is None or sales_filtered.empty:
        sales_filtered = sales

    demand = sales_filtered.groupby(["Referencia", "Punto Venta"], as_index=False)["Cant"].sum()
    demand["venta_diaria"] = demand["Cant"] / max(dias, 1)
    pivot = demand.pivot_table(index="Referencia", columns="Punto Venta", values="venta_diaria", aggfunc="sum", fill_value=0)

    inv = inventario[["Referencia", "Descripcion"] + sedes].copy()
    for col in sedes:
        inv[col] = _num(inv[col])
    rows = []
    for _, row in inv.iterrows():
        ref = row["Referencia"]
        desc = row.get("Descripcion", "")
        if ref not in pivot.index:
            continue
        for destino in sedes:
            venta_dest = float(pivot.loc[ref].get(destino, 0))
            if venta_dest <= 0:
                continue
            stock_dest = float(row.get(destino, 0))
            cobertura_dest = stock_dest / venta_dest
            if cobertura_dest >= min_days:
                continue
            necesidad = max((target_days * venta_dest) - stock_dest, 0)
            if necesidad < 1:
                continue
            for origen in sedes:
                if origen == destino:
                    continue
                venta_origen = float(pivot.loc[ref].get(origen, 0))
                stock_origen = float(row.get(origen, 0))
                cobertura_origen = stock_origen / venta_origen if venta_origen > 0 else 9999
                excedente = stock_origen - (target_days * venta_origen if venta_origen > 0 else 1)
                if stock_origen <= 1 or cobertura_origen <= max_days or excedente < 1:
                    continue
                cantidad = int(max(1, min(round(necesidad), round(excedente))))
                rows.append({
                    "Referencia": ref,
                    "Descripcion": str(desc)[:60],
                    "origen": origen,
                    "destino": destino,
                    "stock_origen": round(stock_origen, 0),
                    "stock_destino": round(stock_dest, 0),
                    "venta_diaria_destino": round(venta_dest, 2),
                    "cobertura_origen": round(cobertura_origen, 1),
                    "cobertura_destino": round(cobertura_dest, 1),
                    "cantidad_sugerida": cantidad,
                    "prioridad": round((min_days - cobertura_dest) * venta_dest, 2),
                })
                break

    out = pd.DataFrame(rows)
    if out.empty:
        return {"kpis": {"sugerencias": 0, "unidades": 0}, "sugerencias": [], "sedes": sedes}
    
    if not sporadic_summary.empty:
        out = out.merge(sporadic_summary[["Referencia", "uds_esporadicas_excluidas"]], on="Referencia", how="left")
        out["uds_esporadicas_excluidas"] = out["uds_esporadicas_excluidas"].fillna(0)
    else:
        out["uds_esporadicas_excluidas"] = 0
        
    out = out.sort_values(["prioridad", "cantidad_sugerida"], ascending=False)
    return {
        "kpis": {"sugerencias": int(len(out)), "unidades": int(out["cantidad_sugerida"].sum()), "dias_demanda": int(dias)},
        "sugerencias": _records(out, 150),
        "sedes": sedes,
    }


def pedido_por_proveedor(ventas: pd.DataFrame, compras: pd.DataFrame, inventario: pd.DataFrame, target_days: int = 5, min_days: int = 5) -> dict[str, Any]:
    sales_raw, dias, max_fecha = _period_sales(ventas, 90)
    if sales_raw.empty or inventario is None or inventario.empty:
        return {"kpis": {"proveedores": 0, "items": 0, "costo_estimado": 0}, "proveedores": [], "items": []}

    # Excluir servicios
    if "Descripcion" in inventario.columns:
        es_servicio = (inventario.get("Nivel", "").astype(str).str.upper() == "SERVICIOS") | (inventario["Descripcion"].astype(str).str.contains("DOMICILIO|INYECTOLOGIA|FLETE|TARIFA DE SERVICIO|PERIODICO", case=False, na=False))
        inventario = inventario[~es_servicio].copy()

    # Filtrar ventas esporádicas para sugeridos de compra
    sales, sporadic_summary = _tag_sporadic(sales_raw)
    if sales is None or sales.empty:
        sales = sales_raw

    rot = sales.groupby("Referencia", as_index=False).agg(uds_vendidas=("Cant", "sum"), ultima_venta=("Fecha", "max"))
    rot["venta_diaria"] = rot["uds_vendidas"] / max(dias, 1)
    inv = inventario.copy()
    for col in ["Total", "Precio Compra"]:
        if col in inv.columns:
            inv[col] = _num(inv[col])
    base = inv[["Referencia", "Descripcion", "Total", "Precio Compra"]].merge(rot, on="Referencia", how="left")
    base["venta_diaria"] = _num(base["venta_diaria"])
    base["cobertura_dias"] = np.where(base["venta_diaria"] > 0, base["Total"] / base["venta_diaria"], 9999)
    base = base[(base["venta_diaria"] > 0) & (base["cobertura_dias"] < min_days)].copy()
    if base.empty:
        return {"kpis": {"proveedores": 0, "items": 0, "costo_estimado": 0}, "proveedores": [], "items": []}

    if compras is not None and not compras.empty and {"REFERENCIA", "PROVEEDOR"}.issubset(compras.columns):
        comp = compras.copy()
        comp["FECHA"] = pd.to_datetime(comp["FECHA"], errors="coerce") if "FECHA" in comp.columns else pd.NaT
        if max_fecha is not None:
            start_date = max_fecha - pd.Timedelta(days=90 - 1)
            comp = comp[comp["FECHA"] >= start_date]
        prov = comp.sort_values("FECHA").groupby("REFERENCIA", as_index=False).agg(proveedor=("PROVEEDOR", "last"))
        base = base.merge(prov.rename(columns={"REFERENCIA": "Referencia"}), on="Referencia", how="left")
    else:
        base["proveedor"] = "Sin proveedor"

    base["proveedor"] = base["proveedor"].fillna("Sin proveedor")
    base["cantidad_sugerida"] = np.ceil((target_days * base["venta_diaria"]) - base["Total"]).clip(lower=1).astype(int)
    base["costo_estimado"] = base["cantidad_sugerida"] * base["Precio Compra"]
    
    if not sporadic_summary.empty:
        base = base.merge(sporadic_summary[["Referencia", "uds_esporadicas_excluidas"]], on="Referencia", how="left")
        base["uds_esporadicas_excluidas"] = base["uds_esporadicas_excluidas"].fillna(0)
    else:
        base["uds_esporadicas_excluidas"] = 0
        
    base = base.sort_values("costo_estimado", ascending=False)
    prov_sum = base.groupby("proveedor", as_index=False).agg(
        items=("Referencia", "nunique"),
        unidades=("cantidad_sugerida", "sum"),
        costo_estimado=("costo_estimado", "sum"),
    ).sort_values("costo_estimado", ascending=False)

    return {
        "kpis": {
            "proveedores": int(len(prov_sum)),
            "items": int(len(base)),
            "unidades": int(base["cantidad_sugerida"].sum()),
            "costo_estimado": round(float(base["costo_estimado"].sum()), 0),
            "dias_demanda": int(dias),
            "target_days": int(target_days),
        },
        "proveedores": _records(prov_sum, 80),
        "items": _records(base, 300),
    }


def detector_anomalias(ventas: pd.DataFrame, compras: pd.DataFrame, inventario: pd.DataFrame, notas: pd.DataFrame) -> dict[str, Any]:
    sales, _, max_fecha = _period_sales(ventas, 45)
    anomalies: list[dict[str, Any]] = []
    if not sales.empty and max_fecha is not None:
        last_day = max_fecha.normalize()
        today_sales = sales[sales["Fecha"].dt.normalize() == last_day]
        prior = sales[sales["Fecha"].dt.normalize() < last_day]
        prod_today = today_sales.groupby(["Referencia", "Descripcion"], as_index=False)["Cant"].sum()
        prod_prior = prior.groupby("Referencia", as_index=False)["Cant"].sum().rename(columns={"Cant": "prior_units"})
        prior_days = max(prior["Fecha"].dt.normalize().nunique(), 1)
        prod = prod_today.merge(prod_prior, on="Referencia", how="left")
        prod["avg"] = _num(prod["prior_units"]) / prior_days
        spike = prod[(prod["Cant"] >= 10) & (prod["Cant"] >= prod["avg"] * 4)].copy()
        for _, r in spike.nlargest(25, "Cant").iterrows():
            anomalies.append({"tipo": "Venta atipica producto", "severidad": "alta", "detalle": r["Descripcion"], "valor": float(r["Cant"]), "referencia": r["Referencia"]})

        sede_today = today_sales.groupby("Punto Venta", as_index=False)["Ingreso"].sum()
        sede_prior = prior.groupby([prior["Fecha"].dt.normalize(), "Punto Venta"])["Ingreso"].sum().reset_index()
        sede_avg = sede_prior.groupby("Punto Venta", as_index=False)["Ingreso"].mean().rename(columns={"Ingreso": "avg"})
        sede = sede_today.merge(sede_avg, on="Punto Venta", how="left")
        sede["drop_pct"] = np.where(sede["avg"] > 0, (1 - sede["Ingreso"] / sede["avg"]) * 100, 0)
        for _, r in sede[sede["drop_pct"] >= 35].iterrows():
            anomalies.append({"tipo": "Caida fuerte por sede", "severidad": "media", "detalle": r["Punto Venta"], "valor": round(float(r["drop_pct"]), 1)})

        if "Factura" in today_sales.columns:
            ticket_today = today_sales.groupby("Factura", as_index=False)["Ingreso"].sum()
            ticket_prior = prior.groupby("Factura", as_index=False)["Ingreso"].sum()
            threshold = ticket_prior["Ingreso"].quantile(0.99) if not ticket_prior.empty else 0
            for _, r in ticket_today[ticket_today["Ingreso"] > threshold].nlargest(20, "Ingreso").iterrows():
                anomalies.append({"tipo": "Ticket atipico", "severidad": "media", "detalle": str(r["Factura"]), "valor": round(float(r["Ingreso"]), 0)})

    if notas is not None and not notas.empty and "Fecha" in notas.columns:
        nc = notas.copy()
        nc["Fecha"] = pd.to_datetime(nc["Fecha"], errors="coerce")
        last_day = nc["Fecha"].max().normalize()
        nc_today = nc[nc["Fecha"].dt.normalize() == last_day]
        vendedor = nc_today.groupby("Creada", as_index=False)["Total Neto"].sum() if "Total Neto" in nc_today.columns else pd.DataFrame()
        for _, r in vendedor.nlargest(10, "Total Neto").iterrows():
            if r["Total Neto"] > 500_000:
                anomalies.append({"tipo": "Devoluciones altas por vendedor", "severidad": "alta", "detalle": str(r["Creada"]).strip(), "valor": round(float(r["Total Neto"]), 0)})

    if inventario is not None and not inventario.empty:
        inv = inventario.copy()
        inv["Total"] = _num(inv.get("Total", 0))
        zero = inv[inv["Total"] <= 0].copy()
        if ventas is not None and not ventas.empty:
            recent_refs = set(_period_sales(ventas, 15)[0]["Referencia"].unique())
            zero = zero[zero["Referencia"].isin(recent_refs)]
        for _, r in zero.head(30).iterrows():
            anomalies.append({"tipo": "Stock cero o negativo con venta reciente", "severidad": "alta", "detalle": r.get("Descripcion", ""), "valor": float(r["Total"]), "referencia": r["Referencia"]})

    if compras is not None and not compras.empty:
        comp = compras.copy()
        comp["FECHA"] = pd.to_datetime(comp["FECHA"], errors="coerce")
        comp["PRECIO"] = _num(comp.get("PRECIO", 0))
        comp = comp.sort_values("FECHA")
        price_change = comp.groupby("REFERENCIA").tail(2)
        for ref, grp in price_change.groupby("REFERENCIA"):
            if len(grp) < 2:
                continue
            old, new = grp.iloc[0], grp.iloc[1]
            if old["PRECIO"] > 0 and (new["PRECIO"] / old["PRECIO"] - 1) >= 0.2:
                anomalies.append({"tipo": "Costo subio mas de 20%", "severidad": "media", "detalle": str(new.get("DESCRIPCION", ""))[:60], "valor": round(float(new["PRECIO"]), 0), "referencia": ref})

        if {"REFERENCIA", "CANT"}.issubset(comp.columns):
            comp["CANT"] = _num(comp["CANT"])
            last_buy_day = comp["FECHA"].max()
            if pd.notna(last_buy_day):
                day_buy = comp[comp["FECHA"].dt.normalize() == last_buy_day.normalize()]
                buy = day_buy.groupby(["REFERENCIA", "DESCRIPCION"], as_index=False).agg(cantidad=("CANT", "sum"), valor=("PRECIO", "sum"))
                sales_60, dias_60, _ = _period_sales(ventas, 60)
                if not sales_60.empty:
                    rot = sales_60.groupby("Referencia", as_index=False).agg(unidades=("Cant", "sum"))
                    rot["venta_diaria"] = rot["unidades"] / max(dias_60, 1)
                    buy = buy.merge(rot.rename(columns={"Referencia": "REFERENCIA"}), on="REFERENCIA", how="left")
                    buy["venta_diaria"] = _num(buy.get("venta_diaria", 0))
                    big_low_rotation = buy[
                        (buy["cantidad"] >= 20)
                        & (buy["venta_diaria"] < 1.5)
                        & (buy["cantidad"] >= np.maximum(20, buy["venta_diaria"] * 45))
                    ]
                    for _, r in big_low_rotation.nlargest(20, "cantidad").iterrows():
                        anomalies.append({
                            "tipo": "Compra grande con baja rotacion",
                            "severidad": "media",
                            "detalle": str(r.get("DESCRIPCION", ""))[:60],
                            "valor": round(float(r["cantidad"]), 0),
                            "referencia": r["REFERENCIA"],
                        })

    sev_order = {"alta": 0, "media": 1, "baja": 2}
    anomalies = sorted(anomalies, key=lambda x: sev_order.get(x.get("severidad"), 9))[:150]
    return {
        "kpis": {
            "total": len(anomalies),
            "altas": sum(1 for a in anomalies if a.get("severidad") == "alta"),
            "medias": sum(1 for a in anomalies if a.get("severidad") == "media"),
        },
        "anomalias": anomalies,
    }


def reporte_diario(ventas: pd.DataFrame, compras: pd.DataFrame, inventario: pd.DataFrame, notas: pd.DataFrame) -> dict[str, Any]:
    sales, _, max_fecha = _period_sales(ventas, 35)
    if sales.empty or max_fecha is None:
        return {"fecha": None, "resumen": {}, "top_sedes": [], "agotados_criticos": [], "devoluciones_anormales": []}
    dia = max_fecha.normalize()
    mes_ini = pd.Timestamp(date(dia.year, dia.month, 1))
    ayer = sales[sales["Fecha"].dt.normalize() == dia]
    mes = sales[sales["Fecha"] >= mes_ini]
    top_sedes = ayer.groupby("Punto Venta", as_index=False).agg(ingreso=("Ingreso", "sum"), unidades=("Cant", "sum")).sort_values("ingreso", ascending=False)
    pedidos = pedido_por_proveedor(ventas, compras, inventario)
    rent = rentabilidad_gerencial(ventas, compras, inventario)
    anom = detector_anomalias(ventas, compras, inventario, notas)
    inv = inventario.copy() if inventario is not None else pd.DataFrame()
    if not inv.empty:
        inv["Total"] = _num(inv.get("Total", 0))
        agotados = inv[inv["Total"] <= 0].head(30)
        capital_inventario = float((_num(inv.get("Total", 0)) * _num(inv.get("Precio Compra", 0))).sum())
        refs_activas = set(_period_sales(ventas, 60)[0]["Referencia"].unique()) if ventas is not None and not ventas.empty else set()
        quieto = inv[(inv["Total"] > 0) & (~inv["Referencia"].isin(refs_activas))].copy() if refs_activas else inv[inv["Total"] > 0].copy()
        capital_quieto = float((_num(quieto.get("Total", 0)) * _num(quieto.get("Precio Compra", 0))).sum())
    else:
        agotados = pd.DataFrame()
        capital_inventario = 0.0
        capital_quieto = 0.0

    return {
        "fecha": dia.strftime("%Y-%m-%d"),
        "resumen": {
            "ventas_ayer": round(float(ayer["Ingreso"].sum()), 0),
            "ventas_mes_actual": round(float(mes["Ingreso"].sum()), 0),
            "facturas_ayer": int(ayer["Factura"].nunique()) if "Factura" in ayer.columns else 0,
            "compra_sugerida_dia": pedidos["kpis"].get("costo_estimado", 0),
            "anomalias": anom["kpis"]["total"],
            "capital_inventario": round(capital_inventario, 0),
            "capital_quieto": round(capital_quieto, 0),
            "fugas_margen": rent["kpis"].get("fugas_margen", 0),
        },
        "top_sedes": _records(top_sedes, 10),
        "agotados_criticos": _records(agotados[["Referencia", "Descripcion", "Total"]] if not agotados.empty else agotados, 30),
        "compra_sugerida": pedidos["proveedores"][:10],
        "devoluciones_anormales": [a for a in anom["anomalias"] if "Devoluciones" in a["tipo"]][:15],
        "anomalias": anom["anomalias"][:20],
    }
