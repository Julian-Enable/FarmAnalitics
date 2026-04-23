# =============================================================================
# backend/routers/analytics.py  — Todos los endpoints de análisis
# =============================================================================
from fastapi import APIRouter, UploadFile, File, HTTPException
from typing import Optional, Union
import pandas as pd
import json

from backend.services.data_store import get_df, set_df, get_status, clear_all
from backend.services.processing import (
    leer_bytes, procesar_ventas, procesar_compras, procesar_inventario,
)

router = APIRouter(prefix="/api")

SEDES = ["PRINCIPAL", "SUCURSAL", "MORATO", "VARDI", "CEDI"]

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


# ── Upload ────────────────────────────────────────────────────────────────────

@router.post("/upload")
async def upload_files(
    ventas:     Optional[Union[list[UploadFile], UploadFile]] = File(default=None),
    compras:    Optional[Union[list[UploadFile], UploadFile]] = File(default=None),
    inventario: Optional[UploadFile]                          = File(default=None),
):
    """Recibe archivos, los procesa y los almacena en memoria."""
    resultados = {}

    # Normalizar: si llega un solo archivo, convertirlo a lista
    if ventas and not isinstance(ventas, list):
        ventas = [ventas]
    if compras and not isinstance(compras, list):
        compras = [compras]

    # Ventas (puede ser múltiples archivos)
    if ventas:
        dfs = []
        for f in ventas:
            content = await f.read()
            dfs.append(leer_bytes(content, f.filename))
        df_v = procesar_ventas(pd.concat(dfs, ignore_index=True))
        set_df("ventas", df_v)
        resultados["ventas"] = len(df_v)

    # Compras
    if compras:
        dfs = []
        for f in compras:
            content = await f.read()
            dfs.append(leer_bytes(content, f.filename))
        df_c = procesar_compras(pd.concat(dfs, ignore_index=True))
        set_df("compras", df_c)
        resultados["compras"] = len(df_c)

    # Inventario
    if inventario:
        content = await inventario.read()
        df_i = procesar_inventario(leer_bytes(content, inventario.filename))
        set_df("inventario", df_i)
        resultados["inventario"] = len(df_i)

    return {"ok": True, "filas": resultados}


@router.get("/status")
def status():
    return get_status()


@router.delete("/reset")
def reset():
    clear_all()
    return {"ok": True}


# ── Resumen General ───────────────────────────────────────────────────────────

@router.get("/resumen")
def resumen():
    df_v = get_df("ventas")
    df_i = get_df("inventario")
    if df_v is None:
        raise HTTPException(404, "No hay datos de ventas cargados")

    ing_total  = float(df_v["Ingreso"].sum())
    und_total  = int(df_v["Cant"].sum())
    n_fact     = int(df_v["Factura"].nunique()) if "Factura" in df_v.columns else 0
    ticket     = ing_total / n_fact if n_fact > 0 else 0

    # Utilidad bruta
    util_bruta = margen_pct = None
    if df_i is not None and "Precio Compra" in df_i.columns and "Precio Venta" in df_i.columns:
        v = df_v.groupby("Referencia", as_index=False)["Cant"].sum()
        m = v.merge(df_i[["Referencia", "Precio Compra", "Precio Venta"]], on="Referencia", how="inner")
        m["Util"] = (m["Precio Venta"] - m["Precio Compra"]) * m["Cant"]
        util_bruta = float(m["Util"].sum())
        margen_pct = round(util_bruta / ing_total * 100, 1) if ing_total else 0

    # Tendencia semanal
    tend = []
    if df_v["Fecha"].notna().any():
        s = df_v.set_index("Fecha").resample("W")["Ingreso"].sum().reset_index()
        tend = [{"fecha": str(r["Fecha"].date()), "ingreso": round(r["Ingreso"], 0)}
                for _, r in s.iterrows()]

    # Por sede
    sedes = (df_v.groupby("Punto Venta", as_index=False)
             .agg(ingresos=("Ingreso","sum"), unidades=("Cant","sum"))
             .sort_values("ingresos", ascending=False)
             .rename(columns={"Punto Venta":"sede"}))
    sedes = json.loads(sedes.to_json(orient="records"))

    return {
        "kpis": {
            "ingresos":   round(ing_total, 0),
            "unidades":   und_total,
            "facturas":   n_fact,
            "ticket":     round(ticket, 0),
            "utilidad":   round(util_bruta, 0) if util_bruta else None,
            "margen_pct": margen_pct,
        },
        "tendencia": tend,
        "sedes":     sedes,
    }


# ── Ventas ────────────────────────────────────────────────────────────────────

@router.get("/ventas")
def ventas(sede: str = "Todas", nivel: str = "Todos",
           laboratorio: str = "Todos",
           fecha_ini: str = None, fecha_fin: str = None):
    df = get_df("ventas")
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
        dias_periodo = max((df["Fecha"].max() - df["Fecha"].min()).days, 1)
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
        s = df.set_index("Fecha").resample("M")["Ingreso"].sum().reset_index()
        tend_mensual = [{"mes": r["Fecha"].strftime("%b %Y"), "ingreso": round(r["Ingreso"], 0)}
                        for _, r in s.iterrows()]

    # Tabla detalle de productos
    detalle = (df.groupby(["Referencia","Descripcion","Laboratorio"], as_index=False)
               .agg(unidades=("Cant","sum"), ingreso=("Ingreso","sum"))
               .sort_values("ingreso", ascending=False))
    detalle = json.loads(detalle.to_json(orient="records"))

    sedes_opts  = sorted(get_df("ventas")["Punto Venta"].dropna().unique().tolist())
    niveles_opts = sorted(df["Nivel"].dropna().unique().tolist()) if "Nivel" in df.columns else []
    labs_opts = sorted(get_df("ventas")["Laboratorio"].dropna().unique().tolist()) if "Laboratorio" in get_df("ventas").columns else []

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


# ── Rentabilidad ──────────────────────────────────────────────────────────────

@router.get("/rentabilidad")
def rentabilidad():
    df_v = get_df("ventas")
    df_i = get_df("inventario")
    if df_v is None or df_i is None:
        raise HTTPException(404, "Necesitas ventas e inventario")
    if "Precio Compra" not in df_i.columns:
        raise HTTPException(400, "Inventario sin columna Precio Compra")

    v = df_v.groupby("Referencia", as_index=False).agg(
        cant_vend=("Cant","sum"),
        descripcion=("Descripcion","first"),
        laboratorio=("Laboratorio","first"),
    )
    r = v.merge(df_i[["Referencia","Precio Compra","Precio Venta"] +
                      (["Nivel"] if "Nivel" in df_i.columns else [])],
                on="Referencia", how="inner")
    r["margen_unit"]   = r["Precio Venta"] - r["Precio Compra"]
    r["margen_pct"]    = ((r["margen_unit"] / r["Precio Venta"]) * 100).round(2)
    r["utilidad_total"] = r["margen_unit"] * r["cant_vend"]
    r["ingreso_total"]  = r["Precio Venta"] * r["cant_vend"]

    top_r = (r.nlargest(15,"utilidad_total").sort_values("utilidad_total",ascending=True)
              .assign(nombre=lambda x: x["descripcion"].str[:30]))
    top_r = json.loads(top_r.to_json(orient="records"))
    bajo_m = r[r["cant_vend"]>=5].nsmallest(15,"margen_pct").copy()
    bajo_m["nombre"] = bajo_m["descripcion"].str[:30]
    bajo_m["precio_venta"] = bajo_m["Precio Venta"]
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
        },
        "top_rentables": top_r,
        "bajo_margen":   bajo_m,
        "por_categoria": por_cat,
        "por_laboratorio": por_lab,
    }


# ── Inventario ────────────────────────────────────────────────────────────────

@router.get("/inventario")
def inventario(sede: str = "Todas"):
    df_i = get_df("inventario")
    df_v = get_df("ventas")
    if df_i is None:
        raise HTTPException(404, "No hay datos de inventario")

    if sede != "Todas" and sede in df_i.columns:
        df_a = df_i.copy()
        df_a["Total"] = df_a[sede]
    else:
        df_a = df_i.copy()

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
        
        max_fecha = df_v_filtered["Fecha"].max()
        min_fecha = df_v_filtered["Fecha"].min()
        if pd.notna(max_fecha) and pd.notna(min_fecha):
            df_a["dias_sin_venta"] = (max_fecha - df_a["ultima_venta"]).dt.days
            
            dias_periodo = (max_fecha - min_fecha).days
            dias_periodo = dias_periodo if dias_periodo > 0 else 1
            df_a["rotacion_diaria"] = df_a["uds_vendidas"] / dias_periodo
            
            import numpy as np
            df_a["cobertura_dias"] = np.where(df_a["rotacion_diaria"] > 0, df_a["Total"] / df_a["rotacion_diaria"], 9999)
            df_a["cobertura_dias"] = df_a["cobertura_dias"].round(1)
        else:
            df_a["dias_sin_venta"] = 9999
            df_a["cobertura_dias"] = 9999
            df_a["rotacion_diaria"] = 0
    else:
        df_a["uds_vendidas"] = 0
        df_a["dias_sin_venta"] = 9999
        df_a["cobertura_dias"] = 9999
        df_a["rotacion_diaria"] = 0
        df_a["clasificacion_abc"] = "C"

    df_a["dias_sin_venta"] = df_a["dias_sin_venta"].fillna(9999)
    df_a["cobertura_dias"] = df_a["cobertura_dias"].fillna(9999)

    # 1. Bajo Stock (Reabastecer): Cobertura crítica (<= 15 días) y con rotación
    bajo = df_a[(df_a["cobertura_dias"] <= 15) & (df_a["rotacion_diaria"] > 0)].copy()
    
    # Calcular déficit real en unidades (cuánto falta para llegar a 15 días de cobertura)
    bajo["stock_ideal"] = bajo["rotacion_diaria"] * 15
    bajo["deficit"] = bajo["stock_ideal"] - bajo["Total"]
    bajo["deficit"] = bajo["deficit"].apply(lambda x: max(1, round(x)))

    sin_stock = df_a[(df_a["Total"]==0) & (df_a["rotacion_diaria"] > 0)]

    # 2. Inventario Quieto: Tiene stock PERO no se vende hace más de 60 días (y tiene fecha de venta antigua o nunca)
    quieto = df_a[(df_a["Total"] > 0) & (df_a["dias_sin_venta"] > 60)].copy()
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

    stock_sede = {}
    for s in SEDES:
        if s in df_i.columns:
            stock_sede[s] = int(df_i[s].sum())

    return {
        "kpis": {
            "bajo_stock":   len(bajo),
            "sin_stock":    len(sin_stock),
            "stock_total":  int(df_a["Total"].sum()),
            "inventario_quieto": len(quieto),
            "capital_quieto": float(quieto["capital_inmovilizado"].sum()) if len(quieto) > 0 else 0
        },
        "bajo_stock_tabla": _df_to_records(bajo.sort_values(["clasificacion_abc", "cobertura_dias"], ascending=[True, True])),
        "inventario_quieto_tabla": _df_to_records(quieto.sort_values("capital_inmovilizado", ascending=False)),
        "top_deficit":       top_deficit,
        "top_quieto":        top_quieto,
        "stock_por_sede":    stock_sede,
        "sedes_disponibles": SEDES
    }


# ── Compras vs Ventas ─────────────────────────────────────────────────────────

@router.get("/compras")
def compras(proveedor: str = "Todos", estado: str = "Todos", buscar: str = ""):
    df_c = get_df("compras")
    df_v = get_df("ventas")
    df_i = get_df("inventario")
    if df_c is None or df_v is None or df_i is None:
        raise HTTPException(404, "Se requieren Compras, Ventas e Inventario para la conciliación.")

    # 1. Agrupar Compras por Referencia
    c_agr = df_c.groupby("REFERENCIA", as_index=False)["CANT"].sum().rename(columns={"REFERENCIA": "Referencia", "CANT": "uds_compradas"})
    
    # 2. Agrupar Ventas por Referencia
    v_agr = df_v.groupby("Referencia", as_index=False)["Cant"].sum().rename(columns={"Cant": "uds_vendidas"})

    # 3. Cruzar con Inventario Actual
    comp = df_i[["Referencia", "Descripcion", "Total"]].copy()
    comp = comp.rename(columns={"Total": "inv_actual"})
    comp = comp.merge(c_agr, on="Referencia", how="left")
    comp = comp.merge(v_agr, on="Referencia", how="left")
    
    # Llenar ceros
    comp["uds_compradas"] = comp["uds_compradas"].fillna(0)
    comp["uds_vendidas"] = comp["uds_vendidas"].fillna(0)
    
    # 4. INGENIERÍA INVERSA: Inventario Inicial
    comp["inv_inicial"] = comp["inv_actual"] - comp["uds_compradas"] + comp["uds_vendidas"]
    
    # 5. Días del Periodo
    dias_periodo = 30
    if "Fecha" in df_v.columns and df_v["Fecha"].notna().any():
        dias_periodo = (df_v["Fecha"].max() - df_v["Fecha"].min()).days or 30
        
    comp["venta_diaria"] = comp["uds_vendidas"] / dias_periodo
    comp["cobertura_dias"] = comp.apply(lambda x: (x["inv_actual"] / x["venta_diaria"]) if x["venta_diaria"] > 0 else 9999, axis=1)

    # 6. Estado
    comp["diferencia"] = comp["uds_compradas"] - comp["uds_vendidas"]
    comp["estado"] = comp["diferencia"].apply(lambda d: "sobre_compra" if d > 0 else ("desabastecimiento" if d < 0 else "equilibrio"))

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
            "dias_periodo": int(dias_periodo)
        },
        "comparativo": json.loads(filtered.sort_values("uds_compradas", ascending=False).to_json(orient="records")),
        "top_proveedores": top_prov,
        "filtros": {"proveedores": proveedores_opts, "estados": ["sobre_compra", "desabastecimiento", "equilibrio"]},
    }


# ── Sedes ─────────────────────────────────────────────────────────────────────

@router.get("/sedes")
def sedes(sede_detalle: str = None):
    df_v = get_df("ventas")
    df_i = get_df("inventario")
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
