# =============================================================================
# backend/routers/analytics.py  — Todos los endpoints de análisis
# =============================================================================
from fastapi import APIRouter, UploadFile, File, HTTPException, Header
from typing import Optional, Union
import pandas as pd
import json
import calendar
import holidays
from datetime import datetime, timedelta, date

from backend.services.data_store import get_df, set_df, get_status, clear_all
from backend.services.processing import (
    leer_bytes, procesar_ventas, procesar_compras, procesar_inventario, procesar_notas_credito,
)

router = APIRouter(prefix="/api")

SEDES = ["PRINCIPAL", "SUCURSAL", "MORATO", "VARDI", "CEDI", "OFICINA 805"]
MAX_UPLOAD_SIZE = 50 * 1024 * 1024
ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls"}
EXCLUDED_INVENTORY_COLUMNS = {
    "Referencia", "Descripcion", "Laboratorio", "Nivel", "Precio Compra", "Precio Venta",
    "Comision", "Utilidad", "Stock Maximo", "Stock Minimo", "Total", "IVA", "Codigo",
}
REQUIRED_COLUMNS = {
    "ventas":        ["Referencia", "Descripcion", "Cant", "Precio Venta", "Laboratorio", "Fecha", "Punto Venta"],
    "compras":       ["FECHA", "PROVEEDOR", "REFERENCIA", "DESCRIPCION", "LABORATORIO", "PRECIO", "CANT", "SEDE"],
    "inventario":    ["Referencia", "Descripcion", "Laboratorio"],
    "notas_credito": ["Fecha", "NotaCredito", "PuntoVenta", "Total"],
}

# ── Reglas de negocio de inventario ─────────────────────────────────────────
INV_MIN_DIAS = 25   # Mínimo de días saludables de cobertura
INV_MAX_DIAS = 40   # Máximo de días saludables de cobertura (sobre esto = sobrestock)
LOW_MARGIN_PCT = 5.0
HIGH_ROTATION_QUANTILE = 0.80
HIGH_ROTATION_MIN_UNITS = 5

# ── Helpers ──────────────────────────────────────────────────────────────────

def _safe(val):
    """Convierte NaN/Inf a None para JSON."""
    import math
    if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
        return None
    return val


def _df_to_records(df: pd.DataFrame, max_rows: int = 200) -> list[dict]:
    df = df.head(max_rows).copy()
    # Usar json.loads(to_json()) para manejar correctamente NaN/Inf a null
    return json.loads(df.to_json(orient="records"))


def _inclusive_days(min_fecha, max_fecha, default: int = 1) -> int:
    """Dias calendario del periodo, incluyendo fecha inicial y final."""
    if pd.isna(min_fecha) or pd.isna(max_fecha):
        return default
    return max((max_fecha - min_fecha).days + 1, 1)


def _inventory_with_total(df_i: pd.DataFrame) -> pd.DataFrame:
    """Devuelve inventario con Total numerico; si falta, suma columnas numericas de sedes."""
    df = df_i.copy()
    if "Total" in df.columns:
        df["Total"] = pd.to_numeric(df["Total"], errors="coerce").fillna(0)
        return df

    posibles_sedes = [
        c for c in df.columns
        if c not in EXCLUDED_INVENTORY_COLUMNS and pd.api.types.is_numeric_dtype(df[c])
    ]
    df["Total"] = df[posibles_sedes].sum(axis=1) if posibles_sedes else 0
    return df


def _inventory_price_lookup(df_i: pd.DataFrame, extra_cols: list[str] | None = None) -> pd.DataFrame:
    cols = ["Referencia", "Precio Compra", "Precio Venta"] + (extra_cols or [])
    cols = [c for c in cols if c in df_i.columns]
    inv = df_i[cols].copy()
    inv["Precio Compra"] = pd.to_numeric(inv.get("Precio Compra"), errors="coerce").fillna(0)
    if "Precio Venta" in inv.columns:
        inv["Precio Venta"] = pd.to_numeric(inv["Precio Venta"], errors="coerce").fillna(0)
    agg = {c: "first" for c in cols if c != "Referencia"}
    return inv.groupby("Referencia", as_index=False).agg(agg)


def _sales_profit_frame(df_v: pd.DataFrame, df_i: pd.DataFrame) -> pd.DataFrame:
    """Rentabilidad por referencia usando ingreso real de ventas y costo de inventario."""
    v = df_v.groupby("Referencia", as_index=False).agg(
        cant_vend=("Cant", "sum"),
        ingreso_total=("Ingreso", "sum"),
        descripcion=("Descripcion", "first"),
        laboratorio=("Laboratorio", "first"),
    )
    extra = ["Nivel"] if "Nivel" in df_i.columns else []
    r = v.merge(_inventory_price_lookup(df_i, extra), on="Referencia", how="inner")
    r["costo_total"] = r["Precio Compra"] * r["cant_vend"]
    r["utilidad_total"] = r["ingreso_total"] - r["costo_total"]
    r["precio_venta_prom"] = r["ingreso_total"] / r["cant_vend"].where(r["cant_vend"] != 0)
    r["margen_unit"] = r["precio_venta_prom"] - r["Precio Compra"]
    r["margen_pct"] = ((r["utilidad_total"] / r["ingreso_total"]) * 100).round(2)
    r["margen_pct"] = r["margen_pct"].replace([float("inf"), float("-inf")], 0).fillna(0)
    return r


def _high_rotation_threshold(r: pd.DataFrame) -> float:
    positive_units = r.loc[r["cant_vend"] > 0, "cant_vend"]
    if positive_units.empty:
        return HIGH_ROTATION_MIN_UNITS
    threshold = float(positive_units.quantile(HIGH_ROTATION_QUANTILE))
    return max(float(HIGH_ROTATION_MIN_UNITS), threshold)


def _column_diagnostic(kind: str, df: pd.DataFrame) -> dict:
    required = REQUIRED_COLUMNS[kind]
    columns = [str(c) for c in df.columns]
    missing = [c for c in required if c not in columns]
    return {
        "tipo": kind,
        "filas": int(len(df)),
        "columnas": columns,
        "requeridas": required,
        "faltantes": missing,
        "ok": not missing,
    }


def _ensure_required_columns(kind: str, df: pd.DataFrame) -> dict:
    diagnostic = _column_diagnostic(kind, df)
    if diagnostic["faltantes"]:
        missing = ", ".join(diagnostic["faltantes"])
        raise HTTPException(400, f"{kind.capitalize()} sin columnas requeridas: {missing}")
    return diagnostic


async def _read_upload(file: UploadFile) -> bytes:
    """Valida extensión y tamaño antes de leer el archivo en memoria."""
    from pathlib import Path

    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"Formato no soportado: {file.filename}")

    content = await file.read()
    if not content:
        raise HTTPException(400, f"Archivo vacío: {file.filename}")
    if len(content) > MAX_UPLOAD_SIZE:
        max_mb = MAX_UPLOAD_SIZE // (1024 * 1024)
        raise HTTPException(413, f"Archivo demasiado grande: {file.filename}. Máximo {max_mb} MB")

    return content


# ── Upload ────────────────────────────────────────────────────────────────────

@router.post("/upload")
async def upload_files(
    ventas:         Optional[Union[list[UploadFile], UploadFile]] = File(default=None),
    compras:        Optional[Union[list[UploadFile], UploadFile]] = File(default=None),
    inventario:     Optional[UploadFile]                          = File(default=None),
    notas_credito:  Optional[UploadFile]                          = File(default=None),
    x_session_id:   str = Header(default="default-session")
):
    """Recibe archivos, los procesa y los almacena en memoria."""
    resultados = {}
    diagnostico = {}
    pending_data = {}

    # Normalizar: si llega un solo archivo, convertirlo a lista
    if ventas and not isinstance(ventas, list):
        ventas = [ventas]
    if compras and not isinstance(compras, list):
        compras = [compras]

    # Ventas (puede ser múltiples archivos)
    if ventas:
        dfs = []
        for f in ventas:
            content = await _read_upload(f)
            df = leer_bytes(content, f.filename)
            if not df.empty:
                dfs.append(df)
        if not dfs:
            raise HTTPException(400, "No se encontraron datos válidos en los archivos de ventas")
        df_raw = pd.concat(dfs, ignore_index=True)
        diagnostico["ventas"] = _ensure_required_columns("ventas", df_raw)
        df_v = procesar_ventas(df_raw)
        pending_data["ventas"] = df_v
        resultados["ventas"] = len(df_v)

    # Compras
    if compras:
        dfs = []
        for f in compras:
            content = await _read_upload(f)
            df = leer_bytes(content, f.filename)
            if not df.empty:
                dfs.append(df)
        if not dfs:
            raise HTTPException(400, "No se encontraron datos válidos en los archivos de compras")
        df_raw = pd.concat(dfs, ignore_index=True)
        diagnostico["compras"] = _ensure_required_columns("compras", df_raw)
        df_c = procesar_compras(df_raw)
        pending_data["compras"] = df_c
        resultados["compras"] = len(df_c)

    # Inventario
    if inventario:
        content = await _read_upload(inventario)
        df_i = procesar_inventario(leer_bytes(content, inventario.filename))
        if df_i.empty:
            raise HTTPException(400, "No se encontraron datos válidos en el archivo de inventario")
        diagnostico["inventario"] = _ensure_required_columns("inventario", df_i)
        pending_data["inventario"] = df_i
        resultados["inventario"] = len(df_i)

    # Notas Crédito
    if notas_credito:
        content = await _read_upload(notas_credito)
        df_nc = leer_bytes(content, notas_credito.filename, tipo="notas_credito")
        if df_nc.empty:
            raise HTTPException(400, "No se encontraron datos válidos en el archivo de notas crédito")
        diagnostico["notas_credito"] = _column_diagnostic("notas_credito", df_nc)
        if diagnostico["notas_credito"]["faltantes"]:
            missing = ", ".join(diagnostico["notas_credito"]["faltantes"])
            raise HTTPException(400, f"Notas crédito sin columnas requeridas: {missing}")
        df_nc = procesar_notas_credito(df_nc)
        pending_data["notas_credito"] = df_nc
        resultados["notas_credito"] = len(df_nc)

    for key, df in pending_data.items():
        set_df(x_session_id, key, df)

    return {"ok": True, "filas": resultados, "diagnostico": diagnostico}


@router.get("/status")
def status(x_session_id: str = Header(default="default-session")):
    return get_status(x_session_id)


@router.get("/schema")
def schema():
    return {
        "columnas_requeridas": REQUIRED_COLUMNS,
        "umbrales_default": {
            "inv_min_dias": INV_MIN_DIAS,
            "inv_max_dias": INV_MAX_DIAS,
            "quieto_dias": 60,
        },
    }


@router.delete("/reset")
def reset(x_session_id: str = Header(default="default-session")):
    clear_all(x_session_id)
    return {"ok": True}


# ── Resumen General ───────────────────────────────────────────────────────────

@router.get("/resumen")
def resumen(x_session_id: str = Header(default="default-session")):
    df_v = get_df(x_session_id, "ventas")
    df_i = get_df(x_session_id, "inventario")
    if df_v is None:
        raise HTTPException(404, "No hay datos de ventas cargados")

    ing_total  = float(df_v["Ingreso"].sum())
    und_total  = int(df_v["Cant"].sum())
    n_fact     = int(df_v["Factura"].nunique()) if "Factura" in df_v.columns else 0
    ticket     = ing_total / n_fact if n_fact > 0 else 0

    # Período analizado
    fecha_ini = str(df_v["Fecha"].min().date()) if df_v["Fecha"].notna().any() else None
    fecha_fin = str(df_v["Fecha"].max().date()) if df_v["Fecha"].notna().any() else None
    max_fecha = df_v["Fecha"].max()
    min_fecha = df_v["Fecha"].min()
    dias_periodo = _inclusive_days(min_fecha, max_fecha)

    # Comparación primera mitad vs segunda mitad del período
    variacion_ing = variacion_und = variacion_ticket = None
    if pd.notna(max_fecha) and pd.notna(min_fecha) and dias_periodo > 2:
        mid_fecha = min_fecha + pd.Timedelta(days=dias_periodo // 2)
        df_primera = df_v[df_v["Fecha"] <= mid_fecha]
        df_segunda = df_v[df_v["Fecha"] > mid_fecha]
        ing1 = float(df_primera["Ingreso"].sum())
        ing2 = float(df_segunda["Ingreso"].sum())
        und1 = float(df_primera["Cant"].sum())
        und2 = float(df_segunda["Cant"].sum())
        fact1 = int(df_primera["Factura"].nunique()) if "Factura" in df_primera.columns else 1
        fact2 = int(df_segunda["Factura"].nunique()) if "Factura" in df_segunda.columns else 1
        tick1 = ing1 / fact1 if fact1 > 0 else 0
        tick2 = ing2 / fact2 if fact2 > 0 else 0
        if ing1 > 0:
            variacion_ing = round((ing2 - ing1) / ing1 * 100, 1)
        if und1 > 0:
            variacion_und = round((und2 - und1) / und1 * 100, 1)
        if tick1 > 0:
            variacion_ticket = round((tick2 - tick1) / tick1 * 100, 1)

    # Utilidad bruta
    util_bruta = margen_pct = None
    if df_i is not None and "Precio Compra" in df_i.columns:
        m = _sales_profit_frame(df_v, df_i)
        util_bruta = float(m["utilidad_total"].sum())
        margen_pct = round(util_bruta / ing_total * 100, 1) if ing_total else 0

    # Tendencia semanal
    tend = []
    if df_v["Fecha"].notna().any():
        s = df_v.set_index("Fecha").resample("W")["Ingreso"].sum().reset_index()
        tend = [{"fecha": str(r["Fecha"].date()), "ingreso": round(r["Ingreso"], 0)}
                for _, r in s.iterrows()]

    # Por sede (con % participación)
    sedes_df = (df_v.groupby("Punto Venta", as_index=False)
             .agg(ingresos=("Ingreso","sum"), unidades=("Cant","sum"))
             .sort_values("ingresos", ascending=False)
             .rename(columns={"Punto Venta":"sede"}))
    total_sedes = float(sedes_df["ingresos"].sum())
    sedes_df["pct"] = (sedes_df["ingresos"] / total_sedes * 100).round(1) if total_sedes > 0 else 0
    sedes = json.loads(sedes_df.to_json(orient="records"))

    # ── Signos vitales cruzados (requieren inventario + ventas) ──
    capital_quieto = 0.0
    productos_sin_stock = 0
    productos_criticos_7d = 0   # se agotan en < 7 días
    productos_atencion_15d = 0  # se agotan en < 15 días

    if df_i is not None:
        import numpy as np
        df_a = _inventory_with_total(df_i)
        if "Total" not in df_a.columns:
            # Detección dinámica de sedes: columnas numéricas que no sean de precio/referencia
            excluir = ["Referencia", "Descripcion", "Laboratorio", "Nivel", "Precio Compra", "Precio Venta", "Comision", "Utilidad", "Stock Maximo", "Stock Minimo", "Total", "IVA", "Codigo"]
            posibles_sedes = [c for c in df_a.columns if c not in excluir and pd.api.types.is_numeric_dtype(df_a[c])]
            df_a["Total"] = df_a[posibles_sedes].sum(axis=1) if posibles_sedes else 0
        else:
            # Si ya tiene una columna Total, nos aseguramos que sea numérica
            df_a["Total"] = pd.to_numeric(df_a["Total"], errors="coerce").fillna(0)

        v_agr = df_v.groupby("Referencia", as_index=False).agg(
            uds_vendidas=("Cant", "sum"),
            ultima_venta=("Fecha", "max")
        )
        df_a = df_a.merge(v_agr, on="Referencia", how="left")
        df_a["uds_vendidas"] = df_a["uds_vendidas"].fillna(0)

        if pd.notna(max_fecha):
            df_a["dias_sin_venta"] = (max_fecha - df_a["ultima_venta"]).dt.days.fillna(9999)
        else:
            df_a["dias_sin_venta"] = 9999

        quieto = df_a[(df_a["Total"] > 0) & (df_a["dias_sin_venta"] > 60)]
        if "Precio Compra" in quieto.columns:
            capital_quieto = float((quieto["Total"] * quieto["Precio Compra"]).sum())

        if pd.notna(max_fecha) and pd.notna(min_fecha):
            df_a["rotacion_diaria"] = df_a["uds_vendidas"] / dias_periodo
            productos_sin_stock = int(len(df_a[(df_a["rotacion_diaria"] > 0) & (df_a["Total"] <= 0)]))
            df_a["cobertura_dias"] = np.where(
                df_a["rotacion_diaria"] > 0,
                df_a["Total"] / df_a["rotacion_diaria"],
                9999
            )
            # Alertas con regla 25-40 días
            productos_criticos_7d = int(len(df_a[(df_a["cobertura_dias"] <= INV_MIN_DIAS * 0.4) & (df_a["rotacion_diaria"] > 0)]))
            productos_atencion_15d = int(len(df_a[(df_a["cobertura_dias"] > INV_MIN_DIAS * 0.4) & (df_a["cobertura_dias"] < INV_MIN_DIAS) & (df_a["rotacion_diaria"] > 0)]))

    # Top 5 productos por ingreso
    top_prod_df = (df_v.groupby(["Referencia", "Descripcion"], as_index=False)["Ingreso"]
                   .sum().nlargest(5, "Ingreso"))
    ing_max_prod = float(top_prod_df["Ingreso"].max()) if len(top_prod_df) > 0 else 1
    top_productos = [{"nombre": r["Descripcion"][:32], "ingreso": round(r["Ingreso"], 0),
                      "pct": round(r["Ingreso"] / ing_max_prod * 100, 0)}
                     for _, r in top_prod_df.iterrows()]

    # Top 5 vendedores (busca varias columnas posibles)
    top_vendedores = []
    vend_col = next((c for c in ["Creada", "Vendedor", "Asesor", "Usuario", "Cajero", "Nombre Vendedor"] if c in df_v.columns), None)
    if vend_col:
        top_vend_df = (df_v.groupby(vend_col, as_index=False)["Ingreso"]
                       .sum().nlargest(5, "Ingreso"))
        ing_max_vend = float(top_vend_df["Ingreso"].max()) if len(top_vend_df) > 0 else 1
        top_vendedores = [{"vendedor": str(r[vend_col])[:25], "ingreso": round(r["Ingreso"], 0),
                           "pct": round(r["Ingreso"] / ing_max_vend * 100, 0)}
                          for _, r in top_vend_df.iterrows()]

    # Top 5 laboratorios por ingreso (siempre disponible como alternativa)
    top_laboratorios = []
    if "Laboratorio" in df_v.columns:
        top_lab_df = (df_v.groupby("Laboratorio", as_index=False)["Ingreso"]
                      .sum().nlargest(5, "Ingreso"))
        ing_max_lab = float(top_lab_df["Ingreso"].max()) if len(top_lab_df) > 0 else 1
        top_laboratorios = [{"laboratorio": str(r["Laboratorio"])[:28], "ingreso": round(r["Ingreso"], 0),
                             "pct": round(r["Ingreso"] / ing_max_lab * 100, 0)}
                            for _, r in top_lab_df.iterrows()]

    # ── Devoluciones (Notas Crédito) ─────────────────────────────────────────
    df_nc = get_df(x_session_id, "notas_credito")
    devoluciones_resumen = None
    if df_nc is not None and len(df_nc) > 0:
        total_devuelto = float(df_nc["Total Neto"].sum())
        n_notas = int(len(df_nc))
        tasa_devolucion = round(total_devuelto / ing_total * 100, 2) if ing_total > 0 else 0
        ingresos_netos = round(ing_total - total_devuelto, 0)
        devoluciones_resumen = {
            "total_devuelto": round(total_devuelto, 0),
            "n_notas":        n_notas,
            "tasa_pct":       tasa_devolucion,
            "ingresos_netos": ingresos_netos,
        }

    return {
        "periodo": {"inicio": fecha_ini, "fin": fecha_fin, "dias": dias_periodo},
        "kpis": {
            "ingresos":        round(ing_total, 0),
            "unidades":        und_total,
            "facturas":        n_fact,
            "ticket":          round(ticket, 0),
            "utilidad":        round(util_bruta, 0) if util_bruta else None,
            "margen_pct":      margen_pct,
            "variacion_ing":   variacion_ing,
            "variacion_und":   variacion_und,
            "variacion_ticket": variacion_ticket,
        },
        "alertas": {
            "sin_stock":           productos_sin_stock,
            "criticos_7d":         productos_criticos_7d,
            "atencion_15d":        productos_atencion_15d,
            "capital_quieto":      round(capital_quieto, 0),
        },
        "devoluciones":      devoluciones_resumen,
        "tendencia":         tend,
        "sedes":             sedes,
        "top_productos":     top_productos,
        "top_vendedores":    top_vendedores,
        "top_laboratorios":  top_laboratorios,
    }


# ── Notas Crédito / Devoluciones ─────────────────────────────────────────────

@router.get("/notas-credito")
def endpoint_notas_credito(x_session_id: str = Header(default="default-session")):
    df_nc = get_df(x_session_id, "notas_credito")
    df_v  = get_df(x_session_id, "ventas")
    if df_nc is None:
        raise HTTPException(404, "No hay datos de notas crédito cargados")

    total_devuelto = float(df_nc["Total Neto"].sum())
    n_notas        = int(len(df_nc))
    promedio_nota  = round(total_devuelto / n_notas, 0) if n_notas > 0 else 0
    total_saldo    = float(df_nc["Saldo"].sum()) if "Saldo" in df_nc.columns else 0

    ing_bruto      = float(df_v["Ingreso"].sum()) if df_v is not None else 0
    tasa_pct       = round(total_devuelto / ing_bruto * 100, 2) if ing_bruto > 0 else 0
    ingresos_netos = round(ing_bruto - total_devuelto, 0)

    # Tendencia semanal
    tendencia = []
    if "Fecha" in df_nc.columns and df_nc["Fecha"].notna().any():
        s = df_nc.set_index("Fecha").resample("W")["Total Neto"].sum().reset_index()
        tendencia = [{"fecha": str(r["Fecha"].date()), "total": round(r["Total Neto"], 0)}
                     for _, r in s.iterrows()]

    # Por sede
    col_sede = "Punto Venta" if "Punto Venta" in df_nc.columns else None
    por_sede = []
    if col_sede:
        sede_df = (df_nc.groupby(col_sede, as_index=False)
                   .agg(total_devuelto=("Total Neto", "sum"), n_notas=("Total Neto", "count"))
                   .sort_values("total_devuelto", ascending=False)
                   .rename(columns={col_sede: "sede"}))
        por_sede = json.loads(sede_df.to_json(orient="records"))

    # Por vendedor
    por_vendedor = []
    if "Creada" in df_nc.columns:
        vend_df = (df_nc.groupby("Creada", as_index=False)
                   .agg(total_devuelto=("Total Neto", "sum"), n_notas=("Total Neto", "count"))
                   .sort_values("total_devuelto", ascending=False)
                   .rename(columns={"Creada": "vendedor"}))
        por_vendedor = json.loads(vend_df.to_json(orient="records"))

    # Por motivo
    por_motivo = []
    if "Motivo" in df_nc.columns:
        mot_df = (df_nc.groupby("Motivo", as_index=False)
                  .agg(total=("Total Neto", "sum"), n=("Total Neto", "count"))
                  .sort_values("total", ascending=False))
        por_motivo = json.loads(mot_df.to_json(orient="records"))

    # Cruce con ventas: productos devueltos (por Factura)
    top_productos_devueltos = []
    if df_v is not None and "Factura" in df_nc.columns and "Factura" in df_v.columns:
        nc_facts = df_nc[["Factura", "Total Neto"]].rename(columns={"Total Neto": "devuelto"})
        cruce = df_v.merge(nc_facts, on="Factura", how="inner")
        if len(cruce) > 0:
            prod_dev = (cruce.groupby(["Referencia", "Descripcion"], as_index=False)
                        .agg(unidades_devueltas=("Cant", "sum"),
                             ingreso_devuelto=("devuelto", "sum"))
                        .sort_values("ingreso_devuelto", ascending=False)
                        .head(15))
            prod_dev["nombre"] = prod_dev["Descripcion"].str[:35]
            top_productos_devueltos = json.loads(prod_dev.to_json(orient="records"))

    # Tabla detalle
    cols_tabla = [c for c in ["Fecha", "NotaCredito", "Punto Venta", "Total Neto",
                               "Creada", "Motivo", "Factura", "Observaciones", "Saldo"]
                  if c in df_nc.columns]
    tabla = _df_to_records(df_nc[cols_tabla].sort_values("Fecha", ascending=False), max_rows=300)

    return {
        "kpis": {
            "total_devuelto":  round(total_devuelto, 0),
            "n_notas":         n_notas,
            "promedio_nota":   promedio_nota,
            "tasa_pct":        tasa_pct,
            "ingresos_brutos": round(ing_bruto, 0),
            "ingresos_netos":  ingresos_netos,
            "saldo_pendiente": round(total_saldo, 0),
        },
        "tendencia":               tendencia,
        "por_sede":                por_sede,
        "por_vendedor":            por_vendedor,
        "por_motivo":              por_motivo,
        "top_productos_devueltos": top_productos_devueltos,
        "tabla":                   tabla,
    }


# ── Ventas ────────────────────────────────────────────────────────────────────

@router.get("/ventas")
def ventas(sede: str = "Todas", nivel: str = "Todos",
           laboratorio: str = "Todos",
           fecha_ini: str = None, fecha_fin: str = None,
           x_session_id: str = Header(default="default-session")):
    df = get_df(x_session_id, "ventas")
    if df is None:
        raise HTTPException(404, "No hay datos de ventas")

    if sede != "Todas":
        df = df[df["Punto Venta"] == sede]
    if nivel != "Todos" and "Nivel" in df.columns:
        df = df[df["Nivel"] == nivel]
    if laboratorio != "Todos" and "Laboratorio" in df.columns:
        df = df[df["Laboratorio"] == laboratorio]
    if fecha_ini:
        df = df[df["Fecha"] >= pd.Timestamp(fecha_ini)]
    if fecha_fin:
        df = df[df["Fecha"] <= pd.Timestamp(fecha_fin)]

    ing_total = float(df["Ingreso"].sum())
    dias_periodo = 1
    if df["Fecha"].notna().any():
        dias_periodo = _inclusive_days(df["Fecha"].min(), df["Fecha"].max())
    promedio_diario = round(ing_total / dias_periodo, 0)

    top_prod = (df.groupby(["Referencia","Descripcion"], as_index=False)["Cant"]
                .sum().nlargest(15,"Cant").sort_values("Cant", ascending=True)
                .assign(nombre=lambda x: x["Descripcion"].str[:35]))
    top_prod = json.loads(top_prod.to_json(orient="records"))

    top_labs = (df.groupby("Laboratorio", as_index=False)["Ingreso"]
                .sum().nlargest(10,"Ingreso").sort_values("Ingreso", ascending=True)
                .assign(lab=lambda x: x["Laboratorio"].str[:28]))
    top_labs = json.loads(top_labs.to_json(orient="records"))

    por_cat = []
    if "Nivel" in df.columns:
        por_cat = (df.groupby("Nivel", as_index=False)["Ingreso"]
                   .sum().sort_values("Ingreso", ascending=True))
        por_cat = json.loads(por_cat.to_json(orient="records"))

    vendedores = []
    if "Creada" in df.columns:
        vendedores = (df.groupby("Creada", as_index=False)
                      .agg(unidades=("Cant","sum"), ingresos=("Ingreso","sum"),
                           facturas=("Referencia","count"))
                      .sort_values("ingresos", ascending=False)
                      .rename(columns={"Creada":"vendedor"}))
        vendedores = json.loads(vendedores.to_json(orient="records"))

    # Tendencia mensual
    tend_mensual = []
    if df["Fecha"].notna().any():
        s = df.set_index("Fecha").resample("ME")["Ingreso"].sum().reset_index()
        tend_mensual = [{"mes": r["Fecha"].strftime("%b %Y"), "ingreso": round(r["Ingreso"], 0)}
                        for _, r in s.iterrows()]

    # Tabla detalle de productos
    detalle = (df.groupby(["Referencia","Descripcion","Laboratorio"], as_index=False)
               .agg(unidades=("Cant","sum"), ingreso=("Ingreso","sum"))
               .sort_values("ingreso", ascending=False))
    detalle = json.loads(detalle.to_json(orient="records"))

    sedes_opts  = sorted(get_df(x_session_id, "ventas")["Punto Venta"].dropna().unique().tolist())
    niveles_opts = sorted(df["Nivel"].dropna().unique().tolist()) if "Nivel" in df.columns else []
    labs_opts = sorted(get_df(x_session_id, "ventas")["Laboratorio"].dropna().unique().tolist()) if "Laboratorio" in get_df(x_session_id, "ventas").columns else []

    return {
        "registros": len(df),
        "ingreso_total": round(ing_total, 0),
        "promedio_diario": promedio_diario,
        "dias_periodo": dias_periodo,
        "top_productos": top_prod,
        "top_labs": top_labs,
        "por_categoria": por_cat,
        "vendedores": vendedores,
        "tendencia_mensual": tend_mensual,
        "detalle_productos": detalle,
        "filtros": {"sedes": sedes_opts, "niveles": niveles_opts, "laboratorios": labs_opts},
    }


# ── Metas y Proyecciones ──────────────────────────────────────────────────────

@router.get("/metas")
def proyeccion_metas(
    agresividad: str = "normal",
    fecha_ini: str = None,
    fecha_fin: str = None,
    x_session_id: str = Header(default="default-session")
):
    df = get_df(x_session_id, "ventas")
    if df is None or len(df) == 0:
        raise HTTPException(404, "No hay datos de ventas")

    # Mapeo de agresividad
    agresividad_map = {
        "conservador": 1.02,
        "normal": 1.05,
        "agresivo": 1.10
    }
    factor_crecimiento = agresividad_map.get(agresividad, 1.05)

    if "Fecha" not in df.columns:
        raise HTTPException(400, "No hay columna Fecha para calcular metas")

    fecha_max_data = df["Fecha"].max()
    year_max = fecha_max_data.year
    month_max = fecha_max_data.month
    
    # Determinar el "último mes completo" (mes anterior al último mes en los datos)
    if month_max == 1:
        mes_ant = 12
        year_ant = year_max - 1
    else:
        mes_ant = month_max - 1
        year_ant = year_max
        
    df_mes_ant = df[(df["Fecha"].dt.year == year_ant) & (df["Fecha"].dt.month == mes_ant)]
    
    if not df_mes_ant.empty:
        df_base = df_mes_ant
        mes_base_nombre = f"{mes_ant:02d}/{year_ant}"
    else:
        df_base = df
        mes_base_nombre = "todo el periodo cargado"

    df_base["Fecha_Date"] = df_base["Fecha"].dt.date
    fechas_unicas = sorted(df_base["Fecha_Date"].dropna().unique())
    if not fechas_unicas:
        raise HTTPException(400, "No hay fechas válidas en ventas para el periodo base")
        
    mitad_idx = len(fechas_unicas) // 2
    fechas_m1 = set(fechas_unicas[:mitad_idx])
    fechas_m2 = set(fechas_unicas[mitad_idx:])

    # Determinar el rango de proyección objetivo
    
    if fecha_ini and fecha_fin:
        try:
            d_ini = datetime.strptime(fecha_ini, "%Y-%m-%d").date()
            d_fin = datetime.strptime(fecha_fin, "%Y-%m-%d").date()
            dias_totales_proy = (d_fin - d_ini).days + 1
            if dias_totales_proy <= 0:
                raise ValueError("Rango inválido")
            
            # Calcular festivos y domingos en el rango dado
            co_holidays = holidays.CO(years=[d_ini.year, d_fin.year])
            domingos_festivos = 0
            habiles = 0
            curr_date = d_ini
            while curr_date <= d_fin:
                if curr_date.weekday() == 6 or curr_date in co_holidays:
                    domingos_festivos += 1
                else:
                    habiles += 1
                curr_date += timedelta(days=1)
                
        except ValueError:
            raise HTTPException(400, "Formato de fecha inválido o rango erróneo")
    else:
        # Calcular exactitud del mes actual (mes objetivo) por defecto
        _, dias_totales_proy = calendar.monthrange(year_max, month_max)
        
        # Calcular festivos y domingos en Colombia para este mes
        co_holidays = holidays.CO(years=year_max)
        domingos_festivos = 0
        habiles = 0
        for day in range(1, dias_totales_proy + 1):
            dt = date(year_max, month_max, day)
            if dt.weekday() == 6 or dt in co_holidays:
                domingos_festivos += 1
            else:
                habiles += 1

    col_sede = "Punto Venta" if "Punto Venta" in df_base.columns else None
    col_vend = "Creada" if "Creada" in df_base.columns else None
    
    if not col_sede or not col_vend:
        raise HTTPException(400, "Faltan columnas de Sede o Vendedor")

    sedes_data = []
    
    for sede, df_sede in df_base.groupby(col_sede):
        dias_sede = df_sede["Fecha_Date"].nunique()
        if dias_sede == 0: continue
        ingresos_sede = df_sede["Ingreso"].sum()
        idp_sede = ingresos_sede / dias_sede
        
        # Tendencia
        df_m1 = df_sede[df_sede["Fecha_Date"].isin(fechas_m1)]
        df_m2 = df_sede[df_sede["Fecha_Date"].isin(fechas_m2)]
        
        idp_m1 = df_m1["Ingreso"].sum() / max(df_m1["Fecha_Date"].nunique(), 1)
        idp_m2 = df_m2["Ingreso"].sum() / max(df_m2["Fecha_Date"].nunique(), 1)
        
        tendencia = idp_m2 / idp_m1 if idp_m1 > 0 else 1.0
        tendencia_capeada = min(max(tendencia, 0.9), 1.15)
        
        # Proyección base a días objetivo
        proyeccion_base = idp_sede * dias_totales_proy * tendencia_capeada
        
        # Asignación de meta según tendencia y agresividad
        if tendencia > 1.05:
            meta_sede = proyeccion_base * factor_crecimiento
        elif tendencia < 0.95:
            # Meta de recuperación
            meta_sede = (idp_sede * dias_totales_proy) * (factor_crecimiento + 0.02)
        else:
            meta_sede = proyeccion_base * factor_crecimiento
            
        ticket_sede = ingresos_sede / max(df_sede["Factura"].nunique(), 1)
        
        vendedores = []
        vends_raw = []
        
        for vend, df_v in df_sede.groupby(col_vend):
            ingreso_v = df_v["Ingreso"].sum()
            aporte_v = ingreso_v / ingresos_sede if ingresos_sede > 0 else 0
            dias_v = df_v["Fecha_Date"].nunique()
            
            # Filtro para excluir reemplazos temporales:
            # Si un vendedor aporta menos del 2% del total de la sede Y trabajó menos de 5 días en el mes, se considera temporal/reemplazo.
            if aporte_v < 0.02 and dias_v < 5:
                continue
                
            ticket_v = ingreso_v / max(df_v["Factura"].nunique(), 1)
            
            vends_raw.append({
                "nombre": vend,
                "ingreso_actual": float(ingreso_v),
                "ticket_promedio": float(ticket_v),
                "aporte": round(aporte_v * 100, 1)
            })
            
        # Distribución equitativa: peso igual para todos los vendedores fijos
        num_vendedores = len(vends_raw)
        peso_igual = 1.0 / num_vendedores if num_vendedores > 0 else 0
        
        for v in vends_raw:
            meta_v = meta_sede * peso_igual
            vendedores.append({
                "nombre": v["nombre"],
                "ingreso_actual": v["ingreso_actual"],
                "ticket_promedio": v["ticket_promedio"],
                "aporte_historico": v["aporte"],
                "peso_distribucion": round(peso_igual * 100, 1),
                "meta": float(meta_v)
            })
            
        vendedores.sort(key=lambda x: x["meta"], reverse=True)
        
        sedes_data.append({
            "sede": sede,
            "ingreso_actual": float(ingresos_sede),
            "idp": float(idp_sede),
            "tendencia": round(tendencia, 2),
            "proyeccion_base": float(proyeccion_base),
            "meta_sugerida": float(meta_sede),
            "vendedores": vendedores
        })
        
    sedes_data.sort(key=lambda x: x["meta_sugerida"], reverse=True)
    
    return {
        "resumen": {
            "ingreso_actual_total": sum(s["ingreso_actual"] for s in sedes_data),
            "meta_total": sum(s["meta_sugerida"] for s in sedes_data),
            "proyeccion_total": sum(s["proyeccion_base"] for s in sedes_data),
            "dias_mes": dias_totales_proy,
            "dias_habiles": habiles,
            "dias_festivos": domingos_festivos,
            "mes_base_usado": mes_base_nombre
        },
        "sedes": sedes_data
    }


# ── Rentabilidad ──────────────────────────────────────────────────────────────

@router.get("/rentabilidad")
def rentabilidad(x_session_id: str = Header(default="default-session")):
    df_v = get_df(x_session_id, "ventas")
    df_i = get_df(x_session_id, "inventario")
    if df_v is None or df_i is None:
        raise HTTPException(404, "Necesitas ventas e inventario")
    if "Precio Compra" not in df_i.columns:
        raise HTTPException(400, "Inventario sin columna Precio Compra")

    r = _sales_profit_frame(df_v, df_i)
    max_fecha = df_v["Fecha"].max() if "Fecha" in df_v.columns else pd.NaT
    min_fecha = df_v["Fecha"].min() if "Fecha" in df_v.columns else pd.NaT
    dias_periodo = _inclusive_days(min_fecha, max_fecha)
    r["rotacion_diaria"] = (r["cant_vend"] / dias_periodo).round(3)
    r["utilidad_unit"] = r["margen_unit"].round(2)
    r["precio_compra"] = r["Precio Compra"]

    # --- ABC CRUZADO ---
    # ABC Ventas (Ingreso)
    r = r.sort_values("ingreso_total", ascending=False)
    total_ingreso = r["ingreso_total"].sum()
    r["acum_ingreso"] = r["ingreso_total"].cumsum()
    def abc_ingreso(acum):
        if total_ingreso == 0: return "C"
        pct = acum / total_ingreso
        if pct <= 0.80: return "A"
        elif pct <= 0.95: return "B"
        else: return "C"
    r["abc_ventas"] = r["acum_ingreso"].apply(abc_ingreso)

    # ABC Margen (Utilidad)
    r = r.sort_values("utilidad_total", ascending=False)
    total_utilidad = r[r["utilidad_total"] > 0]["utilidad_total"].sum()
    r["acum_utilidad"] = r["utilidad_total"].clip(lower=0).cumsum()
    def abc_utilidad(acum):
        if total_utilidad == 0: return "C"
        pct = acum / total_utilidad
        if pct <= 0.80: return "A"
        elif pct <= 0.95: return "B"
        else: return "C"
    r["abc_margen"] = r["acum_utilidad"].apply(abc_utilidad)

    r["matriz_abc"] = r["abc_ventas"] + "-" + r["abc_margen"]

    matriz = r[["Referencia", "descripcion", "laboratorio", "cant_vend", "ingreso_total", "utilidad_total", "margen_pct", "abc_ventas", "abc_margen", "matriz_abc"]].copy()
    matriz["nombre"] = matriz["descripcion"].str[:40]
    matriz = json.loads(matriz.to_json(orient="records"))
    # -------------------

    top_r = (r.nlargest(15,"utilidad_total").sort_values("utilidad_total",ascending=True)
              .assign(nombre=lambda x: x["descripcion"].str[:30]))
    top_r = json.loads(top_r.to_json(orient="records"))

    umbral_alta_rotacion = _high_rotation_threshold(r)
    bajo_m = r[
        (r["margen_pct"] < LOW_MARGIN_PCT)
        & (r["cant_vend"] >= umbral_alta_rotacion)
    ].copy()
    bajo_m_total = len(bajo_m)
    bajo_m = bajo_m.sort_values(
        ["margen_pct", "cant_vend", "ingreso_total"],
        ascending=[True, False, False],
    ).head(50)
    bajo_m["nombre"] = bajo_m["descripcion"].str[:30]
    bajo_m["precio_venta"] = bajo_m["precio_venta_prom"]
    bajo_m = json.loads(bajo_m.to_json(orient="records"))

    por_cat = []
    if "Nivel" in r.columns:
        por_cat = (r.groupby("Nivel",as_index=False)["utilidad_total"]
                   .sum().sort_values("utilidad_total",ascending=True))
        por_cat = json.loads(por_cat.to_json(orient="records"))

    por_lab = (r.groupby("laboratorio",as_index=False)["utilidad_total"]
               .sum().nlargest(10,"utilidad_total")
               .sort_values("utilidad_total",ascending=True)
               .assign(lab=lambda x: x["laboratorio"].str[:25]))
    por_lab = json.loads(por_lab.to_json(orient="records"))

    util_total = float(r["utilidad_total"].sum())
    ing_total  = float(r["ingreso_total"].sum())

    return {
        "kpis": {
            "utilidad_total": round(util_total,0),
            "margen_global":  round(util_total/ing_total*100,1) if ing_total else 0,
            "ingreso_total":  round(ing_total,0),
            "productos":      len(r),
            "bajo_margen_count": bajo_m_total,
            "bajo_margen_umbral_pct": LOW_MARGIN_PCT,
            "alta_rotacion_min_unidades": round(umbral_alta_rotacion, 2),
            "dias_periodo": dias_periodo,
        },
        "top_rentables": top_r,
        "bajo_margen":   bajo_m,
        "por_categoria": por_cat,
        "por_laboratorio": por_lab,
        "matriz_abc": matriz
    }


# ── Inventario ────────────────────────────────────────────────────────────────

@router.get("/inventario")
def inventario(
    sede: str = "Todas",
    inv_min_dias: int = INV_MIN_DIAS,
    inv_max_dias: int = INV_MAX_DIAS,
    quieto_dias: int = 60,
    x_session_id: str = Header(default="default-session")
):
    df_i = get_df(x_session_id, "inventario")
    df_v = get_df(x_session_id, "ventas")
    if df_i is None:
        raise HTTPException(404, "No hay datos de inventario")
    if inv_min_dias <= 0 or inv_max_dias <= inv_min_dias or quieto_dias <= 0:
        raise HTTPException(400, "Umbrales inválidos: usa mínimo > 0, máximo > mínimo y quieto > 0")

    if sede != "Todas" and sede in df_i.columns:
        df_a = df_i.copy()
        df_a["Total"] = pd.to_numeric(df_a[sede], errors="coerce").fillna(0)
    else:
        df_a = _inventory_with_total(df_i)

    if df_v is not None and "Fecha" in df_v.columns:
        if sede != "Todas":
            df_v_filtered = df_v[df_v["Punto Venta"] == sede]
        else:
            df_v_filtered = df_v

        v_agr = df_v_filtered.groupby("Referencia",as_index=False).agg(
            uds_vendidas=("Cant","sum"),
            ingreso_generado=("Ingreso", "sum"),
            ultima_venta=("Fecha","max")
        )
        
        max_fecha = df_v_filtered["Fecha"].max()
        min_fecha = df_v_filtered["Fecha"].min()

        # Forecasting (Tendencia 15 días)
        from datetime import timedelta
        import numpy as np
        if pd.notna(max_fecha):
            fecha_15_dias = max_fecha - timedelta(days=15)
            fecha_30_dias = max_fecha - timedelta(days=30)
            v_15d = df_v_filtered[df_v_filtered["Fecha"] > fecha_15_dias].groupby("Referencia", as_index=False)["Cant"].sum()
            v_15d.rename(columns={"Cant": "cant_15d_reciente"}, inplace=True)
            v_30d = df_v_filtered[(df_v_filtered["Fecha"] > fecha_30_dias) & (df_v_filtered["Fecha"] <= fecha_15_dias)].groupby("Referencia", as_index=False)["Cant"].sum()
            v_30d.rename(columns={"Cant": "cant_15d_anterior"}, inplace=True)
            
            v_agr = v_agr.merge(v_15d, on="Referencia", how="left").merge(v_30d, on="Referencia", how="left")
            v_agr["cant_15d_reciente"] = v_agr["cant_15d_reciente"].fillna(0)
            v_agr["cant_15d_anterior"] = v_agr["cant_15d_anterior"].fillna(0)
            
            v_agr["factor_tendencia"] = np.where(
                v_agr["cant_15d_anterior"] > 0,
                (v_agr["cant_15d_reciente"] / v_agr["cant_15d_anterior"]).clip(0.5, 3.0),
                np.where(v_agr["cant_15d_reciente"] > 0, 2.0, 1.0)
            )
        else:
            v_agr["factor_tendencia"] = 1.0

        # ABC Classification
        v_agr = v_agr.sort_values("ingreso_generado", ascending=False)
        v_agr["acumulado"] = v_agr["ingreso_generado"].cumsum()
        total_ingreso = v_agr["ingreso_generado"].sum()
        
        def clasificar_abc(acum):
            if total_ingreso == 0: return "C"
            pct = acum / total_ingreso
            if pct <= 0.80: return "A"
            elif pct <= 0.95: return "B"
            else: return "C"
            
        v_agr["clasificacion_abc"] = v_agr["acumulado"].apply(clasificar_abc)

        df_a  = df_a.merge(v_agr, on="Referencia", how="left")
        df_a["uds_vendidas"] = df_a["uds_vendidas"].fillna(0)
        df_a["clasificacion_abc"] = df_a["clasificacion_abc"].fillna("C") # Si no se vendió, es C
        df_a["factor_tendencia"] = df_a.get("factor_tendencia", 1.0).fillna(1.0)
        
        if pd.notna(max_fecha) and pd.notna(min_fecha):
            df_a["dias_sin_venta"] = (max_fecha - df_a["ultima_venta"]).dt.days
            
            dias_periodo = _inclusive_days(min_fecha, max_fecha)
            df_a["rotacion_diaria"] = df_a["uds_vendidas"] / dias_periodo
            df_a["rotacion_proyectada"] = df_a["rotacion_diaria"] * df_a["factor_tendencia"]
            
            import numpy as np
            df_a["cobertura_dias"] = np.where(df_a["rotacion_proyectada"] > 0, df_a["Total"] / df_a["rotacion_proyectada"], 9999)
            df_a["cobertura_dias"] = df_a["cobertura_dias"].round(1)
        else:
            df_a["dias_sin_venta"] = 9999
            df_a["cobertura_dias"] = 9999
            df_a["rotacion_diaria"] = 0
            df_a["rotacion_proyectada"] = 0
    else:
        df_a["uds_vendidas"] = 0
        df_a["dias_sin_venta"] = 9999
        df_a["cobertura_dias"] = 9999
        df_a["rotacion_diaria"] = 0
        df_a["rotacion_proyectada"] = 0
        df_a["factor_tendencia"] = 1.0
        df_a["clasificacion_abc"] = "C"

    df_a["dias_sin_venta"] = df_a["dias_sin_venta"].fillna(9999)
    df_a["cobertura_dias"] = df_a["cobertura_dias"].fillna(9999)

    # 1. Bajo Stock: Cobertura por debajo del mínimo saludable configurado.
    bajo = df_a[(df_a["cobertura_dias"] < inv_min_dias) & (df_a["rotacion_proyectada"] > 0)].copy()
    
    # Calcular déficit real en unidades para llegar a la cobertura mínima.
    bajo["stock_ideal"] = bajo["rotacion_proyectada"] * inv_min_dias
    bajo["deficit"] = bajo["stock_ideal"] - bajo["Total"]
    bajo["deficit"] = bajo["deficit"].apply(lambda x: max(1, round(x)))

    # 2. Sobrestock: Cobertura por encima del máximo saludable configurado.
    sobre = df_a[(df_a["cobertura_dias"] > inv_max_dias) & (df_a["cobertura_dias"] < 9999) & (df_a["rotacion_proyectada"] > 0)].copy()
    if "Precio Compra" in sobre.columns:
        sobre["capital_exceso"] = (sobre["Total"] - (sobre["rotacion_proyectada"] * inv_max_dias)) * sobre["Precio Compra"]
    else:
        sobre["capital_exceso"] = 0

    sin_stock = df_a[(df_a["Total"]==0) & (df_a["rotacion_diaria"] > 0)]

    # 3. Inventario Quieto: stock sin venta por encima del umbral configurado.
    quieto = df_a[(df_a["Total"] > 0) & (df_a["dias_sin_venta"] > quieto_dias)].copy()
    if "Precio Compra" in quieto.columns:
        quieto["capital_inmovilizado"] = quieto["Total"] * quieto["Precio Compra"]
    else:
        quieto["capital_inmovilizado"] = 0

    top_quieto = (quieto.nlargest(15, "capital_inmovilizado")
                  .sort_values("capital_inmovilizado", ascending=True)
                  .assign(nombre=lambda x: x["Descripcion"].str[:30]))
    top_quieto = json.loads(top_quieto.to_json(orient="records"))

    top_deficit = (bajo.nlargest(15,"deficit")
                   .sort_values("deficit",ascending=True)
                   .assign(nombre=lambda x: x["Descripcion"].str[:30]))
    top_deficit = json.loads(top_deficit.to_json(orient="records"))

    top_sobre = (sobre.nlargest(15, "capital_exceso")
                  .sort_values("capital_exceso", ascending=True)
                  .assign(nombre=lambda x: x["Descripcion"].str[:30]))
    top_sobre = json.loads(top_sobre.to_json(orient="records"))

    stock_sede = {}
    for s in SEDES:
        if s in df_i.columns:
            stock_sede[s] = int(df_i[s].sum())

    # Obtener sedes dinámicamente para el selector del frontend
    excluir_selector = ["Referencia", "Descripcion", "Laboratorio", "Nivel", "Precio Compra", "Precio Venta", "Comision", "Utilidad", "Stock Maximo", "Stock Minimo", "Total", "IVA", "Codigo"]
    sedes_finales = [c for c in df_i.columns if c not in excluir_selector and pd.api.types.is_numeric_dtype(df_i[c])]

    return {
        "kpis": {
            "bajo_stock":      len(bajo),
            "sin_stock":       len(sin_stock),
            "sobre_stock":     len(sobre),
            "stock_total":     int(df_a["Total"].sum()),
            "inventario_quieto": len(quieto),
            "capital_quieto":  float(quieto["capital_inmovilizado"].sum()) if len(quieto) > 0 else 0,
            "capital_exceso":  float(sobre["capital_exceso"].sum()) if len(sobre) > 0 else 0,
            "inv_min_dias":    inv_min_dias,
            "inv_max_dias":    inv_max_dias,
            "quieto_dias":     quieto_dias,
        },
        "bajo_stock_tabla":       _df_to_records(bajo.sort_values(["clasificacion_abc", "cobertura_dias"], ascending=[True, True])),
        "sobre_stock_tabla":      _df_to_records(sobre.sort_values("cobertura_dias", ascending=False)),
        "inventario_quieto_tabla": _df_to_records(quieto.sort_values("capital_inmovilizado", ascending=False)),
        "top_deficit":            top_deficit,
        "top_quieto":             top_quieto,
        "top_sobre":              top_sobre,
        "stock_por_sede":         stock_sede,
        "sedes_disponibles":      sedes_finales
    }


# ── Compras vs Ventas ─────────────────────────────────────────────────────────

@router.get("/compras")
def compras(
    proveedor: str = "Todos",
    estado: str = "Todos",
    buscar: str = "",
    inv_min_dias: int = INV_MIN_DIAS,
    inv_max_dias: int = INV_MAX_DIAS,
    x_session_id: str = Header(default="default-session")
):
    df_c = get_df(x_session_id, "compras")
    df_v = get_df(x_session_id, "ventas")
    df_i = get_df(x_session_id, "inventario")
    if df_c is None or df_v is None or df_i is None:
        raise HTTPException(404, "Se requieren Compras, Ventas e Inventario para la conciliación.")
    if inv_min_dias <= 0 or inv_max_dias <= inv_min_dias:
        raise HTTPException(400, "Umbrales inválidos: usa mínimo > 0 y máximo > mínimo")

    # 1. Agrupar Compras por Referencia
    c_agr = df_c.groupby("REFERENCIA", as_index=False)["CANT"].sum().rename(columns={"REFERENCIA": "Referencia", "CANT": "uds_compradas"})
    
    # 2. Agrupar Ventas por Referencia
    v_agr = df_v.groupby("Referencia", as_index=False)["Cant"].sum().rename(columns={"Cant": "uds_vendidas"})

    # 3. Cruzar con Inventario Actual
    df_i_total = _inventory_with_total(df_i)
    comp = df_i_total[["Referencia", "Descripcion", "Total"]].copy()
    comp = comp.rename(columns={"Total": "inv_actual"})
    
    # Intentar obtener Categoría/Nivel para diferenciar perecederos
    if "Nivel" in df_i.columns:
        nivel_df = df_i[["Referencia", "Nivel"]].drop_duplicates("Referencia")
        comp = comp.merge(nivel_df, on="Referencia", how="left")
    elif "Nivel" in df_v.columns:
        nivel_df = df_v.groupby("Referencia", as_index=False)["Nivel"].first()
        comp = comp.merge(nivel_df, on="Referencia", how="left")
    else:
        comp["Nivel"] = "Desconocida"
        
    comp["Nivel"] = comp["Nivel"].fillna("Desconocida")

    comp = comp.merge(c_agr, on="Referencia", how="left")
    comp = comp.merge(v_agr, on="Referencia", how="left")
    
    # Llenar ceros
    comp["uds_compradas"] = comp["uds_compradas"].fillna(0)
    comp["uds_vendidas"] = comp["uds_vendidas"].fillna(0)
    
    # 4. INGENIERÍA INVERSA: Inventario Inicial
    comp["inv_inicial"] = comp["inv_actual"] - comp["uds_compradas"] + comp["uds_vendidas"]
    
    # Filtrar productos inactivos (todo en 0)
    comp = comp[(comp["inv_actual"] > 0) | (comp["uds_compradas"] > 0) | (comp["uds_vendidas"] > 0)]
    
    # 5. Días del Periodo
    dias_periodo = 30
    if "Fecha" in df_v.columns and df_v["Fecha"].notna().any():
        dias_periodo = _inclusive_days(df_v["Fecha"].min(), df_v["Fecha"].max(), default=30)
        
    comp["venta_diaria"] = comp["uds_vendidas"] / dias_periodo
    comp["cobertura_dias"] = comp.apply(lambda x: (x["inv_actual"] / x["venta_diaria"]) if x["venta_diaria"] > 0 else 9999, axis=1)

    # 6. Estado (Basado en Cobertura 25-40 días)
    def calcular_estado_flujo(row):
        if row["cobertura_dias"] < inv_min_dias:
            return "desabastecimiento" # Falta
        elif row["cobertura_dias"] > inv_max_dias:
            return "sobre_compra"      # Sobre / Exceso
        else:
            return "equilibrio"        # OK
            
    comp["estado"] = comp.apply(calcular_estado_flujo, axis=1)

    # Aplicar filtros
    filtered = comp.copy()
    if estado != "Todos":
        filtered = filtered[filtered["estado"] == estado]
    if buscar:
        mask = (filtered["Referencia"].astype(str).str.contains(buscar, case=False, na=False) |
                filtered["Descripcion"].astype(str).str.contains(buscar, case=False, na=False))
        filtered = filtered[mask]

    # Proveedores
    # Cruzar proveedor desde compras
    prov_ref = df_c.groupby("REFERENCIA", as_index=False)["PROVEEDOR"].first().rename(columns={"REFERENCIA": "Referencia", "PROVEEDOR": "proveedor"})
    filtered = filtered.merge(prov_ref, on="Referencia", how="left")
    filtered["proveedor"] = filtered["proveedor"].fillna("Sin proveedor")

    if proveedor != "Todos":
        filtered = filtered[filtered["proveedor"] == proveedor]

    top_prov = (df_c.groupby("PROVEEDOR",as_index=False)
                .agg(unidades=("CANT","sum"), costo_total=("Costo Total","sum"))
                .nlargest(10,"unidades")
                .rename(columns={"PROVEEDOR":"proveedor"}))
    top_prov = json.loads(top_prov.to_json(orient="records"))

    proveedores_opts = sorted(df_c["PROVEEDOR"].dropna().unique().tolist())

    return {
        "kpis": {
            "total_comprado": int(comp["uds_compradas"].sum()),
            "total_vendido":  int(comp["uds_vendidas"].sum()),
            "n_sobre_compra": int(len(comp[comp["estado"]=="sobre_compra"])),
            "n_desabastecimiento": int(len(comp[comp["estado"]=="desabastecimiento"])),
            "dias_periodo": int(dias_periodo),
            "inv_min_dias": inv_min_dias,
            "inv_max_dias": inv_max_dias,
        },
        "comparativo": json.loads(filtered.sort_values("uds_compradas", ascending=False).to_json(orient="records")),
        "top_proveedores": top_prov,
        "filtros": {"proveedores": proveedores_opts, "estados": ["sobre_compra", "desabastecimiento", "equilibrio"]},
    }


# ── Sedes ─────────────────────────────────────────────────────────────────────

@router.get("/sedes")
def sedes(sede_detalle: str = None, x_session_id: str = Header(default="default-session")):
    df_v = get_df(x_session_id, "ventas")
    df_i = get_df(x_session_id, "inventario")
    if df_v is None:
        raise HTTPException(404, "No hay datos de ventas")

    comparativo = (df_v.groupby("Punto Venta", as_index=False).agg(
        ingresos=("Ingreso","sum"), unidades=("Cant","sum"),
        facturas=("Factura","nunique") if "Factura" in df_v.columns else ("Cant","count"),
        productos_unicos=("Referencia","nunique"),
    ).rename(columns={"Punto Venta":"sede"})
    .sort_values("ingresos",ascending=False))
    comparativo = json.loads(comparativo.to_json(orient="records"))

    # Calcular ticket promedio
    for r in comparativo:
        r["ticket"] = round(r["ingresos"]/r["facturas"],0) if r["facturas"] else 0

    # Top 5 de la sede seleccionada
    top5 = []
    if sede_detalle:
        df_s = df_v[df_v["Punto Venta"]==sede_detalle]
        top5 = (df_s.groupby(["Referencia","Descripcion"],as_index=False)["Cant"]
                .sum().nlargest(5,"Cant")
                .assign(nombre=lambda x: x["Descripcion"].str[:35]))
        top5 = json.loads(top5.to_json(orient="records"))

    stock_sede = {}
    if df_i is not None:
        for s in SEDES:
            if s in df_i.columns:
                stock_sede[s] = int(df_i[s].sum())

    lista_sedes = sorted(df_v["Punto Venta"].dropna().unique().tolist())

    return {
        "comparativo":   comparativo,
        "top5_sede":     top5,
        "stock_sedes":   stock_sede,
        "lista_sedes":   lista_sedes,
    }
