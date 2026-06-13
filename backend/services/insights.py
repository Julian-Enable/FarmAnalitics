"""
Análisis avanzados que aportan valor directo al negocio:
1. Mermas y ajustes de inventario (pérdida real vs correcciones).
2. Fuga de margen por descuentos.
3. Clientes crónicos con listados de llamadas (recuperación y proactivo).
"""
from __future__ import annotations

import json
import re
from typing import Any

import numpy as np
import pandas as pd


def _records(df: pd.DataFrame, limit: int | None = None) -> list[dict[str, Any]]:
    if df is None or df.empty:
        return []
    out = df.head(limit) if limit else df
    out = out.replace([np.inf, -np.inf], np.nan)
    return json.loads(out.to_json(orient="records", date_format="iso"))


_SERVICIO_RE = re.compile(r"DOMICILIO|INYECTOLOGIA|FLETE|TARIFA DE SERVICIO|PERIODICO|SERVICIO", re.I)


def _es_servicio(desc: pd.Series, nivel: pd.Series | None = None) -> pd.Series:
    mask = desc.astype(str).str.contains(_SERVICIO_RE, na=False)
    if nivel is not None:
        mask = mask | (nivel.astype(str).str.upper() == "SERVICIOS")
    return mask


# ── 1. MERMAS ────────────────────────────────────────────────────────────────
# El motivo del ajuste viene como texto libre en Documento. Se clasifica para
# separar la PÉRDIDA REAL (avería, vencimiento, faltante de conteo, consumo) de
# las CORRECCIONES que no son pérdida (cambios de unidad de medida, trocados,
# traslados, ajustes de cargue).

def categorizar_merma(doc: str) -> tuple[str, bool]:
    t = str(doc).upper()
    if "AVERIA" in t or "AVERÍA" in t or "DAÑO" in t or "DANO" in t:
        return "Avería/Daño", True
    if "VENCIM" in t or "VENCID" in t:
        return "Vencimiento", True
    if ("TROCADO" in t or "UMV" in t or "UNIDAD DE MEDIDA" in t or "DESGLOSE" in t
            or "MAL CARGUE" in t or "ERROR DE CARGUE" in t or "MAL CARGADA" in t or "CARGUE" in t):
        return "Corrección de cargue/UMV", False
    if "TRASLADO" in t or "DISTRIBUCION" in t or "DISTRIBUCIÓN" in t:
        return "Traslado/Distribución", False
    if "FALTANTE" in t or "SOBRANTE" in t or "INV GEN" in t or "INVENTARIO GENERAL" in t or "CICLICO" in t or "CÍCLICO" in t or "CONTEO" in t:
        return "Faltante de conteo", True
    if "CONSUMO INTERNO" in t:
        return "Consumo interno", True
    if "INVENTARIO INICIAL" in t:
        return "Ajuste inicial/otro", False
    return "Otro", True


def analisis_mermas(df: pd.DataFrame) -> dict[str, Any]:
    if df is None or df.empty:
        return {"kpis": {}, "por_categoria": [], "por_sede": [], "por_producto": [], "por_usuario": [], "tabla": []}

    d = df.copy()
    d["Cantidad"] = pd.to_numeric(d.get("Cantidad", 0), errors="coerce").fillna(0)
    d["ValorCosto"] = pd.to_numeric(d.get("ValorCosto", 0), errors="coerce").fillna(0)
    # Solo ajustes negativos (salida de inventario)
    d = d[d["Cantidad"] < 0].copy()
    if d.empty:
        return {"kpis": {}, "por_categoria": [], "por_sede": [], "por_producto": [], "por_usuario": [], "tabla": []}

    cat = d["Motivo"].apply(categorizar_merma)
    d["categoria"] = cat.apply(lambda x: x[0])
    d["es_merma"] = cat.apply(lambda x: x[1])
    d["uds"] = -d["Cantidad"]
    d["valor"] = -d["ValorCosto"]
    # Usuario que registró: primeras palabras del Documento (antes del primer '-')
    d["usuario"] = d["Motivo"].astype(str).str.split(" - ").str[0].str.strip().str[:30]

    merma = d[d["es_merma"]]

    por_categoria = (d.groupby(["categoria", "es_merma"], as_index=False)
                     .agg(uds=("uds", "sum"), valor=("valor", "sum"), n=("uds", "count"))
                     .sort_values("valor", ascending=False))

    por_sede = (merma.groupby("Punto Venta", as_index=False)
                .agg(uds=("uds", "sum"), valor=("valor", "sum"))
                .sort_values("valor", ascending=False)) if "Punto Venta" in merma.columns else pd.DataFrame()

    por_producto = (merma.groupby(["Referencia", "Descripcion"], as_index=False)
                    .agg(uds=("uds", "sum"), valor=("valor", "sum"))
                    .sort_values("valor", ascending=False)
                    .head(60))
    if not por_producto.empty:
        por_producto["nombre"] = por_producto["Descripcion"].astype(str).str[:40]

    por_usuario = (merma.groupby("usuario", as_index=False)
                   .agg(uds=("uds", "sum"), valor=("valor", "sum"), n=("uds", "count"))
                   .sort_values("valor", ascending=False)
                   .head(30))

    cols = [c for c in ["Fecha", "Punto Venta", "Referencia", "Descripcion", "categoria", "uds", "valor", "usuario", "Motivo"] if c in merma.columns]
    tabla = _records(merma[cols].sort_values("valor", ascending=False), 500)

    return {
        "kpis": {
            "merma_total": round(float(merma["valor"].sum()), 0),
            "merma_unidades": int(merma["uds"].sum()),
            "correcciones_total": round(float(d[~d["es_merma"]]["valor"].sum()), 0),
            "n_ajustes": int(len(merma)),
            "productos_afectados": int(merma["Referencia"].nunique()),
        },
        "por_categoria": _records(por_categoria),
        "por_sede": _records(por_sede),
        "por_producto": _records(por_producto),
        "por_usuario": _records(por_usuario),
        "tabla": tabla,
    }


# ── 2. DESCUENTOS ────────────────────────────────────────────────────────────

def analisis_descuentos(df: pd.DataFrame) -> dict[str, Any]:
    if df is None or df.empty:
        return {"kpis": {}, "por_plan": [], "por_sede": [], "por_cajero": [], "por_producto": [], "outliers": [], "tendencia": []}

    d = df.copy()
    d["Valor"] = pd.to_numeric(d.get("Valor", 0), errors="coerce").fillna(0)
    d = d[d["Valor"] > 0].copy()
    if d.empty:
        return {"kpis": {}, "por_plan": [], "por_sede": [], "por_cajero": [], "por_producto": [], "outliers": [], "tendencia": []}

    por_plan = (d.groupby("Plan", as_index=False)
                .agg(total=("Valor", "sum"), n=("Valor", "count"))
                .sort_values("total", ascending=False).head(30)) if "Plan" in d.columns else pd.DataFrame()
    por_sede = (d.groupby("Punto Venta", as_index=False)
                .agg(total=("Valor", "sum"), n=("Valor", "count"))
                .sort_values("total", ascending=False)) if "Punto Venta" in d.columns else pd.DataFrame()

    por_cajero = pd.DataFrame()
    outliers = pd.DataFrame()
    if "Cajero" in d.columns:
        por_cajero = (d.groupby("Cajero", as_index=False)
                      .agg(total=("Valor", "sum"), n=("Valor", "count"))
                      .sort_values("total", ascending=False))
        # Outliers: cajeros con descuento total muy por encima de la mediana (robusto)
        if len(por_cajero) >= 5:
            med = por_cajero["total"].median()
            mad = (por_cajero["total"] - med).abs().median() or 1
            por_cajero["score"] = ((por_cajero["total"] - med) / (1.4826 * mad)).round(1)
            outliers = por_cajero[por_cajero["score"] >= 3.5].copy()

    por_producto = (d.groupby(["Referencia", "Descripcion"], as_index=False)
                    .agg(total=("Valor", "sum"), n=("Valor", "count"))
                    .sort_values("total", ascending=False).head(60))
    if not por_producto.empty:
        por_producto["nombre"] = por_producto["Descripcion"].astype(str).str[:40]

    tendencia = []
    if "Fecha" in d.columns and d["Fecha"].notna().any():
        s = d.copy()
        s["Fecha"] = pd.to_datetime(s["Fecha"], errors="coerce")
        s = s.set_index("Fecha").resample("ME")["Valor"].sum().reset_index()
        tendencia = [{"mes": r["Fecha"].strftime("%b %Y"), "total": round(float(r["Valor"]), 0)} for _, r in s.iterrows() if pd.notna(r["Fecha"])]

    return {
        "kpis": {
            "total_descontado": round(float(d["Valor"].sum()), 0),
            "n_lineas": int(len(d)),
            "descuento_promedio": round(float(d["Valor"].mean()), 0),
            "n_cajeros": int(d["Cajero"].nunique()) if "Cajero" in d.columns else 0,
        },
        "por_plan": _records(por_plan),
        "por_sede": _records(por_sede),
        "por_cajero": _records(por_cajero.head(30)),
        "por_producto": _records(por_producto),
        "outliers": _records(outliers),
        "tendencia": tendencia,
    }


# ── 3. CLIENTES CRÓNICOS ─────────────────────────────────────────────────────

def analisis_cronicos(ventas: pd.DataFrame, clientes: pd.DataFrame,
                      fecha_ini: str | None = None, fecha_fin: str | None = None,
                      min_compras: int = 3, meses_min: int = 3,
                      intervalo_min: int = 15, intervalo_max: int = 75,
                      vencidos_max: int = 180, proximos_dias: int = 7) -> dict[str, Any]:
    if ventas is None or ventas.empty:
        return {"kpis": {}, "recuperar": [], "proximos": []}

    v = ventas.copy()
    v["ID_Cliente"] = v["ID_Cliente"].astype(str)
    v = v[v["ID_Cliente"].ne("0") & v["ID_Cliente"].ne("nan")]
    if v.empty or "Fecha" not in v.columns:
        return {"kpis": {}, "recuperar": [], "proximos": []}

    v["Fecha"] = pd.to_datetime(v["Fecha"], errors="coerce")
    v = v[v["Fecha"].notna()]
    # Ventana de ventas a considerar: fecha_ini limita desde cuándo se mira el
    # historial; fecha_fin define el corte ("hoy") para evaluar si ya se le acabó.
    if fecha_ini:
        v = v[v["Fecha"] >= pd.Timestamp(fecha_ini)]
    if fecha_fin:
        v = v[v["Fecha"] < pd.Timestamp(fecha_fin) + pd.Timedelta(days=1)]
    # Excluir servicios/domicilios (no son medicamentos)
    nivel = v["Nivel"] if "Nivel" in v.columns else None
    v = v[~_es_servicio(v["Descripcion"], nivel)]
    if v.empty:
        return {"kpis": {}, "recuperar": [], "proximos": []}

    hoy = pd.Timestamp(fecha_fin).normalize() if fecha_fin else v["Fecha"].max().normalize()
    v["dia"] = v["Fecha"].dt.normalize()
    diario = v.groupby(["ID_Cliente", "Referencia", "dia"], as_index=False).agg(
        desc=("Descripcion", "last"))
    diario = diario.sort_values("dia")

    # Intervalo mediano y meses distintos por cliente-producto.
    # "meses" exige que el hábito esté SOSTENIDO en el tiempo (al menos 3 meses
    # distintos con compra), no 3 compras juntas en pocos días.
    grp = diario.groupby(["ID_Cliente", "Referencia"])
    base = grp.agg(
        compras=("dia", "nunique"),
        meses=("dia", lambda s: s.dt.to_period("M").nunique()),
        ultima=("dia", "max"),
        primera=("dia", "min"),
        desc=("desc", "last"),
    ).reset_index()
    intervalo = grp["dia"].apply(lambda s: s.diff().dt.days.median()).reset_index(name="intervalo")
    base = base.merge(intervalo, on=["ID_Cliente", "Referencia"], how="left")

    cron = base[(base["compras"] >= min_compras)
                & (base["meses"] >= meses_min)
                & (base["intervalo"] >= intervalo_min)
                & (base["intervalo"] <= intervalo_max)].copy()
    if cron.empty:
        return {"kpis": {"clientes_cronicos": 0}, "recuperar": [], "proximos": []}

    cron["fecha_esperada"] = cron["ultima"] + pd.to_timedelta(cron["intervalo"], unit="D")
    cron["dias_vs_esperada"] = (hoy - cron["fecha_esperada"]).dt.days
    cron["medicamento"] = cron["desc"].astype(str).str[:45]

    # Datos de contacto
    if clientes is not None and not clientes.empty:
        cli = clientes.copy()
        cli["ID"] = cli["ID"].astype(str)
        col_tel = "Movil" if "Movil" in cli.columns else None
        keep = ["ID", "Nombre"] + ([col_tel] if col_tel else [])
        cron = cron.merge(cli[keep], left_on="ID_Cliente", right_on="ID", how="left")
        cron = cron.rename(columns={col_tel: "telefono"}) if col_tel else cron.assign(telefono="")
    else:
        cron["Nombre"] = ""
        cron["telefono"] = ""

    cron["Nombre"] = cron["Nombre"].fillna("").astype(str).str.strip()
    cron["telefono"] = cron["telefono"].fillna("").astype(str).str.strip()
    cron = cron[cron["Nombre"].ne("") & cron["Nombre"].str.upper().ne("CLIENTE MOSTRADOR")]

    out_cols = ["Nombre", "telefono", "medicamento", "intervalo", "ultima", "fecha_esperada", "dias_vs_esperada", "compras", "ID_Cliente"]

    # Corte claro en 0 (su fecha esperada de recompra):
    #  - dias_vs_esperada < 0  -> AÚN tiene medicamento, se le acaba pronto -> PROACTIVO.
    #  - dias_vs_esperada > 0   -> YA pasó su fecha y no volvió -> ABANDONÓ (recuperar).

    # Lista A: ABANDONARON (vencidos entre 1 y vencidos_max días = abandono reciente del año)
    recuperar = cron[(cron["dias_vs_esperada"] >= 1) & (cron["dias_vs_esperada"] <= vencidos_max)].copy()
    recuperar = recuperar.sort_values("dias_vs_esperada")[out_cols]

    # Lista B: RECURRENTES ACTIVOS por agotarse (se les acaba en los próximos N días)
    proximos = cron[(cron["dias_vs_esperada"] >= -proximos_dias) & (cron["dias_vs_esperada"] <= 0)].copy()
    proximos["dias_para_acabar"] = (-proximos["dias_vs_esperada"]).clip(lower=0)
    proximos = proximos.sort_values("dias_vs_esperada", ascending=False)[out_cols + ["dias_para_acabar"]]

    return {
        "kpis": {
            "clientes_cronicos": int(cron["ID_Cliente"].nunique()),
            "n_recuperar": int(recuperar["ID_Cliente"].nunique()),
            "n_proximos": int(proximos["ID_Cliente"].nunique()),
            "fecha_corte": hoy.strftime("%Y-%m-%d"),
        },
        "recuperar": _records(recuperar, 8000),
        "proximos": _records(proximos, 8000),
    }
