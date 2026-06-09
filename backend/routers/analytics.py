# =============================================================================
# backend/routers/analytics.py  â€” Todos los endpoints de anÃ¡lisis
# =============================================================================
from fastapi import APIRouter, UploadFile, File, HTTPException, Header
from typing import Optional, Union
# =============================================================================
# backend/routers/analytics.py  â€” Todos los endpoints de anÃ¡lisis
# =============================================================================
from fastapi import APIRouter, UploadFile, File, HTTPException, Header
from typing import Optional, Union
import pandas as pd
import numpy as np
import json
import calendar
import holidays
from datetime import datetime, timedelta, date

from backend.services.data_store import get_df as _store_get_df, set_df, get_status as _store_get_status, clear_all, get_default_ventas
from backend.services.processing import (
    leer_bytes, procesar_ventas, procesar_compras, procesar_inventario, procesar_notas_credito,
)
from backend.services.db_config import is_db_configured
from backend.services.db_service import get_db_service
from backend.services.historical_store import get_historical_store
from backend.services.historical_refresh import historical_status, refresh_from_last_update
from backend.services.management_analytics import (
    detector_anomalias,
    pedido_por_proveedor,
    reporte_diario,
    rentabilidad_gerencial,
    sugerido_traslados,
)

def get_df(session_id, key, fecha_ini=None, fecha_fin=None, sede=None, limit=None):
    if is_db_configured():
        db = get_db_service()
        if db:
            if key == "ventas":
                return db.get_ventas(fecha_ini, fecha_fin, sede, limit)
            elif key == "compras":
                return db.get_compras(fecha_ini, fecha_fin)
            elif key == "inventario":
                return db.get_inventario()
            elif key == "notas_credito":
                return db.get_notas_credito(fecha_ini, fecha_fin)
    historical = get_historical_store()
    if historical.available():
        if key == "ventas":
            return historical.get_ventas(fecha_ini, fecha_fin, sede, limit)
        if key == "compras":
            return historical.get_compras(fecha_ini, fecha_fin)
        if key == "inventario" and historical.inventory_available():
            return historical.get_inventario()
        if key == "notas_credito":
            return historical.get_notas_credito(fecha_ini, fecha_fin)
    return _store_get_df(session_id, key)

def get_status(session_id):
    historical = get_historical_store()
    if historical.available():
        return {
            "ventas": True,
            "compras": not historical.get_compras().empty,
            "inventario": historical.inventory_available(),
            "notas_credito": not historical.get_notas_credito().empty,
        }
    if is_db_configured():
        db = get_db_service()
        if db:
            historical = historical_status()
            connected = False
            try:
                connected = bool(db.test_connection().get("connected"))
            except Exception:
                connected = False
            if historical.get("available"):
                return {
                    "ventas": True,
                    "compras": historical["datasets"].get("compras", {}).get("exists", False),
                    "inventario": historical["datasets"].get("inventario", {}).get("exists", False) or connected,
                    "notas_credito": historical["datasets"].get("notas_credito", {}).get("exists", False),
                }
            if connected:
                return {"ventas": True, "compras": True, "inventario": True, "notas_credito": True}
    return _store_get_status(session_id)
from config import (
    SEDES_INVENTARIO, MAX_UPLOAD_SIZE, ALLOWED_EXTENSIONS, EXCLUDED_INVENTORY_COLUMNS,
    REQUIRED_COLUMNS, INV_MIN_DIAS, INV_MAX_DIAS, LOW_MARGIN_PCT,
    HIGH_ROTATION_QUANTILE, HIGH_ROTATION_MIN_UNITS, QUIETO_DIAS_DEFAULT,
)

router = APIRouter(prefix="/api")

SEDES = SEDES_INVENTARIO
MIN_ANALYTICS_DATE = date(2024, 1, 1)

# â”€â”€ Helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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


def _parse_iso_date(value: str | None, field: str) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(400, f"{field} debe tener formato YYYY-MM-DD")


def _effective_summary_range(fecha_ini: str | None, fecha_fin: str | None) -> tuple[date, date]:
    today = date.today()
    f_fin = _parse_iso_date(fecha_fin, "fecha_fin") or today
    if f_fin < MIN_ANALYTICS_DATE or f_fin > today:
        f_fin = today

    f_ini = _parse_iso_date(fecha_ini, "fecha_ini") or date(f_fin.year, 1, 1)
    if f_ini < MIN_ANALYTICS_DATE:
        f_ini = date(f_fin.year, 1, 1)
    if f_ini < MIN_ANALYTICS_DATE:
        f_ini = MIN_ANALYTICS_DATE

    if f_ini > f_fin:
        raise HTTPException(400, "fecha_ini no puede ser mayor que fecha_fin")

    return f_ini, f_fin


def _normalize_optional_date_range(fecha_ini: str | None, fecha_fin: str | None) -> tuple[str | None, str | None]:
    if not fecha_ini and not fecha_fin:
        return None, None
    f_ini, f_fin = _effective_summary_range(fecha_ini, fecha_fin)
    return f_ini.strftime("%Y-%m-%d"), f_fin.strftime("%Y-%m-%d")


def _apply_date_filter(
    df: pd.DataFrame,
    date_col: str,
    fecha_ini: str | None = None,
    fecha_fin: str | None = None,
) -> pd.DataFrame:
    """Filtra por rango de fechas inclusivo si la columna existe."""
    if df is None or date_col not in df.columns:
        return df

    filtered = df.copy()
    if fecha_ini:
        filtered = filtered[filtered[date_col] >= pd.Timestamp(fecha_ini)]
    if fecha_fin:
        end = pd.Timestamp(fecha_fin)
        if isinstance(fecha_fin, str) and len(fecha_fin) == 10:
            filtered = filtered[filtered[date_col] < end + pd.Timedelta(days=1)]
        else:
            filtered = filtered[filtered[date_col] <= end]
    return filtered


def _preferred_vendedor_series(df: pd.DataFrame) -> pd.Series | None:
    """Nombre comercial del vendedor; usa Creada solo como respaldo."""
    if df is None or df.empty:
        return None
    if "NombreVendedor" not in df.columns and "Creada" not in df.columns:
        return None

    nombre = (
        df["NombreVendedor"].astype(str).str.strip()
        if "NombreVendedor" in df.columns
        else pd.Series("", index=df.index)
    )
    creada = (
        df["Creada"].astype(str).str.strip()
        if "Creada" in df.columns
        else pd.Series("", index=df.index)
    )
    invalid = {"", "nan", "none", "nombrevendedor", "creada"}
    return nombre.where(~nombre.str.lower().isin(invalid), creada).str.strip()


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


def _notas_credito_key_cols(df: pd.DataFrame) -> list[str]:
    if "NotaCreditoKey" in df.columns:
        return ["NotaCreditoKey"]
    if {"NotaCreditoID", "ID_PuntoVenta"}.issubset(df.columns):
        return ["NotaCreditoID", "ID_PuntoVenta"]
    if {"NotaCredito", "Punto Venta"}.issubset(df.columns):
        return ["NotaCredito", "Punto Venta"]
    if "NotaCredito" in df.columns:
        return ["NotaCredito"]
    return []


def _notas_credito_note_frame(df_nc: pd.DataFrame) -> pd.DataFrame:
    """Devuelve una fila por nota credito para no duplicar totales por producto."""
    if df_nc is None or df_nc.empty:
        return pd.DataFrame()

    df = df_nc.copy()
    if "Total Neto" not in df.columns and "TotalNota" in df.columns:
        df["Total Neto"] = df["TotalNota"]
    if "Total Neto" not in df.columns and "Total" in df.columns:
        df["Total Neto"] = df["Total"]
    if "NotaCredito" not in df.columns and "NotaCreditoID" in df.columns:
        df["NotaCredito"] = df["NotaCreditoID"]
    if "Motivo" not in df.columns:
        if "Observaciones" in df.columns:
            from backend.services.processing import _categorizar_motivo
            df["Motivo"] = df["Observaciones"].apply(_categorizar_motivo)
        else:
            df["Motivo"] = "Sin observacion"

    for col in ["Total Neto", "Saldo"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    if "Fecha" in df.columns:
        df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce")

    key_cols = _notas_credito_key_cols(df)
    if not key_cols:
        return df
    return df.sort_values("Fecha").drop_duplicates(subset=key_cols, keep="last")


def _notas_credito_product_frame(df_nc: pd.DataFrame) -> pd.DataFrame:
    """Asigna el total de cada nota entre sus lineas para ranking de productos."""
    if df_nc is None or df_nc.empty or "Referencia" not in df_nc.columns:
        return pd.DataFrame()

    df = df_nc.copy()
    key_cols = _notas_credito_key_cols(df)
    if not key_cols:
        return pd.DataFrame()

    if "Total Neto" not in df.columns and "TotalNota" in df.columns:
        df["Total Neto"] = df["TotalNota"]
    if "TotalProducto" not in df.columns:
        return pd.DataFrame()

    df["TotalProducto"] = pd.to_numeric(df["TotalProducto"], errors="coerce").fillna(0)
    df["Total Neto"] = pd.to_numeric(df["Total Neto"], errors="coerce").fillna(0)
    if "Cantidad" in df.columns:
        df["Cantidad"] = pd.to_numeric(df["Cantidad"], errors="coerce").fillna(0)

    note_totals = _notas_credito_note_frame(df)[key_cols + ["Total Neto"]].rename(columns={"Total Neto": "total_nota"})
    line_sums = df.groupby(key_cols, as_index=False)["TotalProducto"].sum().rename(columns={"TotalProducto": "total_productos"})
    lines = df.merge(note_totals, on=key_cols, how="left").merge(line_sums, on=key_cols, how="left")
    lines["devuelto_asignado"] = np.where(
        lines["total_productos"] > 0,
        lines["total_nota"] * lines["TotalProducto"] / lines["total_productos"],
        lines["TotalProducto"],
    )
    return lines


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
    if kind == "ventas":
        aliases = {
            "Referencia": {"REFERENCIA"},
            "Descripcion": {"DESCRIPCION"},
            "Cant": {"CANT"},
            "Precio Venta": {"Precio", "PRECIO"},
            "Laboratorio": {"LABORATORIO"},
            "Fecha": {"FECHA"},
            "Punto Venta": {"SEDE"},
        }
        missing = [
            col for col in missing
            if not aliases.get(col, set()).intersection(columns)
        ]
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
    """Valida extensiÃ³n y tamaÃ±o antes de leer el archivo en memoria."""
    from pathlib import Path

    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"Formato no soportado: {file.filename}")

    content = await file.read()
    if not content:
        raise HTTPException(400, f"Archivo vacÃ­o: {file.filename}")
    if len(content) > MAX_UPLOAD_SIZE:
        max_mb = MAX_UPLOAD_SIZE // (1024 * 1024)
        raise HTTPException(413, f"Archivo demasiado grande: {file.filename}. MÃ¡ximo {max_mb} MB")

    return content


# â”€â”€ Upload â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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

    # Ventas (puede ser mÃºltiples archivos)
    if ventas:
        dfs = []
        for f in ventas:
            content = await _read_upload(f)
            df = leer_bytes(content, f.filename)
            if not df.empty:
                dfs.append(df)
        if not dfs:
            raise HTTPException(400, "No se encontraron datos vÃ¡lidos en los archivos de ventas")
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
            raise HTTPException(400, "No se encontraron datos vÃ¡lidos en los archivos de compras")
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
            raise HTTPException(400, "No se encontraron datos vÃ¡lidos en el archivo de inventario")
        diagnostico["inventario"] = _ensure_required_columns("inventario", df_i)
        pending_data["inventario"] = df_i
        resultados["inventario"] = len(df_i)

    # Notas CrÃ©dito
    if notas_credito:
        content = await _read_upload(notas_credito)
        df_nc = leer_bytes(content, notas_credito.filename, tipo="notas_credito")
        if df_nc.empty:
            raise HTTPException(400, "No se encontraron datos vÃ¡lidos en el archivo de notas crÃ©dito")
        diagnostico["notas_credito"] = _column_diagnostic("notas_credito", df_nc)
        if diagnostico["notas_credito"]["faltantes"]:
            missing = ", ".join(diagnostico["notas_credito"]["faltantes"])
            raise HTTPException(400, f"Notas crÃ©dito sin columnas requeridas: {missing}")
        df_nc = procesar_notas_credito(df_nc)
        pending_data["notas_credito"] = df_nc
        resultados["notas_credito"] = len(df_nc)

    for key, df in pending_data.items():
        set_df(x_session_id, key, df)

    return {"ok": True, "filas": resultados, "diagnostico": diagnostico}


@router.get("/status")
def status(x_session_id: str = Header(default="default-session")):
    s = get_status(x_session_id)
    db_connection = {"connected": False, "message": "DB no configurada"}
    if is_db_configured():
        db = get_db_service()
        if db:
            try:
                db_connection = db.test_connection()
            except Exception as exc:
                db_connection = {"connected": False, "message": str(exc)}
    s["db_connected"] = bool(db_connection.get("connected"))
    s["db_message"] = db_connection.get("message")
    s["historical"] = historical_status()
    return s


@router.get("/historico/status")
def historico_status():
    return historical_status()


@router.post("/historico/actualizar")
def historico_actualizar():
    try:
        return refresh_from_last_update()
    except Exception as exc:
        raise HTTPException(500, str(exc))


@router.get("/schema")
def schema():
    return {
        "columnas_requeridas": REQUIRED_COLUMNS,
        "umbrales_default": {
            "inv_min_dias": INV_MIN_DIAS,
            "inv_max_dias": INV_MAX_DIAS,
            "quieto_dias": QUIETO_DIAS_DEFAULT,
        },
    }


@router.delete("/reset")
def reset(x_session_id: str = Header(default="default-session")):
    clear_all(x_session_id)
    return {"ok": True}


# â”€â”€ ExploraciÃ³n de Base de Datos â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@router.get("/db/status")
def db_status():
    if not is_db_configured():
        return {"connected": False, "message": "DB no configurada en .env"}
    db = get_db_service()
    return db.test_connection() if db else {"connected": False, "message": "No se pudo crear DB service"}

@router.get("/db/tables")
def db_tables():
    if not is_db_configured():
        return []
    db = get_db_service()
    return db.get_tables_info() if db else []

@router.get("/db/columns/{table_name}")
def db_columns(table_name: str):
    if not is_db_configured():
        return []
    db = get_db_service()
    return db.get_table_columns(table_name) if db else []

@router.get("/db/preview/{table_name}")
def db_preview(table_name: str):
    if not is_db_configured():
        return []
    db = get_db_service()
    return db.get_table_preview(table_name) if db else []


# â”€â”€ Resumen General â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@router.get("/resumen")
def resumen(
    fecha_ini: str = None,
    fecha_fin: str = None,
    x_session_id: str = Header(default="default-session")
):
    db = get_db_service()
    if not db:
        raise HTTPException(500, "Base de datos no conectada")

    # Definir un unico rango efectivo para que todos los KPIs usen el mismo periodo.
    f_ini, f_fin = _effective_summary_range(fecha_ini, fecha_fin)
    fecha_ini_eff = f_ini.strftime("%Y-%m-%d")
    fecha_fin_eff = f_fin.strftime("%Y-%m-%d")
    dias_periodo = max((f_fin - f_ini).days + 1, 1)

    # 1. KPIs principales
    kpis = db.get_resumen_kpis(fecha_ini_eff, fecha_fin_eff)
    ing_total = kpis.get("ingresos", 0)
    und_total = kpis.get("unidades", 0)
    n_fact = kpis.get("facturas", 0)
    ticket = ing_total / n_fact if n_fact > 0 else 0

    # 2. Utilidad y Costos
    costos = db.get_resumen_costo_utilidad(fecha_ini_eff, fecha_fin_eff)
    costo_total = costos.get("costo_total")
    util_bruta = None
    margen_pct = None
    if costo_total is not None:
        util_bruta = ing_total - costo_total
        margen_pct = round((util_bruta / ing_total * 100), 1) if ing_total > 0 else 0

    # 3. Tendencia
    tend = db.get_resumen_tendencia(fecha_ini_eff, fecha_fin_eff)

    # 4. Rankings (Top 5)
    top_productos_raw = db.get_resumen_ranking("producto", fecha_ini_eff, fecha_fin_eff, limit=5)
    top_sedes_raw = db.get_resumen_ranking("sede", fecha_ini_eff, fecha_fin_eff, limit=100)
    top_vendedores_raw = db.get_resumen_ranking("vendedor", fecha_ini_eff, fecha_fin_eff, limit=5)
    top_labs_raw = db.get_resumen_ranking("laboratorio", fecha_ini_eff, fecha_fin_eff, limit=5)

    def format_ranking(raw_list, name_key, max_ingreso=None):
        if not raw_list: return []
        m_ing = max_ingreso or max(r["ingreso"] for r in raw_list)
        if m_ing <= 0: m_ing = 1
        return [
            {name_key: str(r.get("nombre") or r.get("sede") or r.get("vendedor") or r.get("laboratorio"))[:32],
             "ingreso": round(r["ingreso"], 0),
             "pct": round(r["ingreso"] / m_ing * 100, 0)}
            for r in raw_list
        ]

    ing_max_prod = max([r["ingreso"] for r in top_productos_raw], default=1)
    top_productos = format_ranking(top_productos_raw, "nombre", ing_max_prod)

    ing_max_vend = max([r["ingreso"] for r in top_vendedores_raw], default=1)
    top_vendedores = format_ranking(top_vendedores_raw, "vendedor", ing_max_vend)

    ing_max_lab = max([r["ingreso"] for r in top_labs_raw], default=1)
    top_laboratorios = format_ranking(top_labs_raw, "laboratorio", ing_max_lab)

    total_sedes = sum(r["ingreso"] for r in top_sedes_raw)
    sedes = []
    for r in top_sedes_raw:
        sedes.append({
            "sede": r["sede"],
            "ingresos": r["ingreso"],
            "pct": round((r["ingreso"] / total_sedes * 100), 1) if total_sedes > 0 else 0
        })

    # 5. Notas CrÃ©dito
    df_nc = db.get_notas_credito(fecha_ini_eff, fecha_fin_eff)
    devoluciones_resumen = None
    if df_nc is not None and not df_nc.empty:
        notas_unicas = _notas_credito_note_frame(df_nc)
        total_devuelto = float(notas_unicas["Total Neto"].sum())
        n_notas = len(notas_unicas)
        tasa_devolucion = round(total_devuelto / ing_total * 100, 2) if ing_total > 0 else 0
        ingresos_netos = round(ing_total - total_devuelto, 0)
        devoluciones_resumen = {
            "total_devuelto": round(total_devuelto, 0),
            "n_notas": n_notas,
            "tasa_pct": tasa_devolucion,
            "ingresos_netos": ingresos_netos,
        }

    # 6. Alertas de inventario (Optimizadas con get_resumen_alertas_df)
    capital_quieto = 0.0
    productos_sin_stock = 0
    productos_criticos_7d = 0
    productos_atencion_15d = 0

    df_a = db.get_resumen_alertas_df(fecha_ini_eff, fecha_fin_eff)
    if df_a is not None and not df_a.empty:
        import numpy as np
        # df_a tiene: Referencia, Total, cant_vend, ultima_venta, PrecioCompra

        # Calcular dias_sin_venta
        max_fecha = pd.to_datetime(f_fin)
        df_a["ultima_venta"] = pd.to_datetime(df_a["ultima_venta"])
        df_a["dias_sin_venta"] = (max_fecha - df_a["ultima_venta"]).dt.days.fillna(9999)

        quieto = df_a[(df_a["Total"] > 0) & (df_a["dias_sin_venta"] > QUIETO_DIAS_DEFAULT)]
        if "PrecioCompra" in quieto.columns:
            capital_quieto = float((quieto["Total"] * pd.to_numeric(quieto["PrecioCompra"], errors="coerce").fillna(0)).sum())

        df_a["rotacion_diaria"] = df_a["cant_vend"] / max(dias_periodo, 1)
        productos_sin_stock = int(len(df_a[(df_a["rotacion_diaria"] > 0) & (df_a["Total"] <= 0)]))
        df_a["cobertura_dias"] = np.where(
            df_a["rotacion_diaria"] > 0,
            df_a["Total"] / df_a["rotacion_diaria"],
            9999
        )
        productos_criticos_7d = int(len(df_a[(df_a["cobertura_dias"] <= INV_MIN_DIAS * 0.4) & (df_a["rotacion_diaria"] > 0)]))
        productos_atencion_15d = int(len(df_a[(df_a["cobertura_dias"] > INV_MIN_DIAS * 0.4) & (df_a["cobertura_dias"] < INV_MIN_DIAS) & (df_a["rotacion_diaria"] > 0)]))

    return {
        "periodo": {"inicio": str(f_ini), "fin": str(f_fin), "dias": dias_periodo},
        "kpis": {
            "ingresos":        round(ing_total, 0),
            "unidades":        und_total,
            "facturas":        n_fact,
            "ticket":          round(ticket, 0),
            "utilidad":        round(util_bruta, 0) if util_bruta is not None else None,
            "margen_pct":      margen_pct,
            # variacion se desactiva temporalmente en la PoC para hacerlo mÃ¡s rÃ¡pido
            "variacion_ing":   None,
            "variacion_und":   None,
            "variacion_ticket": None,
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


# â”€â”€ Rentabilidad â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@router.get("/rentabilidad")
def rentabilidad(fecha_ini: str = None, fecha_fin: str = None, x_session_id: str = Header(default="default-session")):
    from backend.services.db_config import is_db_configured
    from backend.services.db_service import get_db_service

    fecha_ini, fecha_fin = _normalize_optional_date_range(fecha_ini, fecha_fin)

    if is_db_configured():
        db = get_db_service()
        if db:
            res = db.get_analisis_rentabilidad_sql(fecha_ini=fecha_ini, fecha_fin=fecha_fin)
            if res:
                try:
                    df_v_g = get_df(x_session_id, "ventas", fecha_ini=fecha_ini, fecha_fin=fecha_fin)
                    df_i_g = get_df(x_session_id, "inventario")
                    res["gerencial"] = rentabilidad_gerencial(df_v_g, df_i_g)
                except Exception:
                    res["gerencial"] = {}
                return res

    # Fallback si no hay BD o no hay resultados
    df_v = get_df(x_session_id, "ventas", fecha_ini=fecha_ini, fecha_fin=fecha_fin)
    df_i = get_df(x_session_id, "inventario")
    if df_v is None or df_i is None:
        raise HTTPException(404, "Faltan datos para rentabilidad")

    df_v = _apply_date_filter(df_v, "Fecha", fecha_ini, fecha_fin)

    r = _sales_profit_frame(df_v, df_i)
    r = r.sort_values("utilidad_total", ascending=False)
    r = r.replace([np.inf, -np.inf], np.nan).fillna(0)

    r["cum_util"] = r["utilidad_total"].cumsum()
    total_util = r["utilidad_total"].sum()
    if total_util > 0:
        r["pct_cum"] = r["cum_util"] / total_util
        r["matriz_abc"] = np.where(r["pct_cum"] <= 0.8, "A", np.where(r["pct_cum"] <= 0.95, "B", "C"))
    else:
        r["matriz_abc"] = "C"

    utilidad_total = float(r["utilidad_total"].sum()) if not r.empty else 0.0
    ingreso_total = float(r["ingreso_total"].sum()) if not r.empty else 0.0
    margen_global = round(utilidad_total / ingreso_total * 100, 2) if ingreso_total > 0 else 0
    alta_rotacion_min = _high_rotation_threshold(r) if not r.empty else HIGH_ROTATION_MIN_UNITS
    bajo_margen_df = r[(r["margen_pct"] < LOW_MARGIN_PCT) & (r["cant_vend"] >= alta_rotacion_min)].copy()
    por_laboratorio = (
        r.groupby("laboratorio", as_index=False)
        .agg(utilidad_total=("utilidad_total", "sum"))
        .sort_values("utilidad_total", ascending=False)
        .head(15)
    ) if "laboratorio" in r.columns and not r.empty else pd.DataFrame()
    dias_periodo = _inclusive_days(df_v["Fecha"].min(), df_v["Fecha"].max(), default=1) if "Fecha" in df_v.columns else 1

    return {
        "kpis": {
            "utilidad_total": round(utilidad_total, 0),
            "ingreso_total": round(ingreso_total, 0),
            "margen_global": margen_global,
            "productos": int(len(r)),
            "bajo_margen_count": int(len(bajo_margen_df)),
            "bajo_margen_umbral_pct": LOW_MARGIN_PCT,
            "alta_rotacion_min_unidades": round(float(alta_rotacion_min), 0),
            "dias_periodo": int(dias_periodo),
        },
        "top_rentables": json.loads(r.nlargest(15, "utilidad_total").to_json(orient="records")),
        "bajo_margen": json.loads(bajo_margen_df.sort_values("margen_pct").to_json(orient="records")),
        "matriz_abc": json.loads(r.to_json(orient="records")),
        "por_laboratorio": json.loads(por_laboratorio.to_json(orient="records")) if not por_laboratorio.empty else [],
        "gerencial": rentabilidad_gerencial(df_v, df_i),
    }


def _management_frames(x_session_id: str):
    df_v = get_df(x_session_id, "ventas")
    df_c = get_df(x_session_id, "compras")
    df_i = get_df(x_session_id, "inventario")
    df_n = get_df(x_session_id, "notas_credito")
    if df_v is None or df_i is None:
        raise HTTPException(404, "Faltan ventas o inventario para analitica gerencial")
    if df_c is None:
        df_c = pd.DataFrame()
    if df_n is None:
        df_n = pd.DataFrame()
    return df_v, df_c, df_i, df_n


@router.get("/gerencia")
def gerencia_operativa(x_session_id: str = Header(default="default-session")):
    df_v, df_c, df_i, df_n = _management_frames(x_session_id)
    traslados = sugerido_traslados(df_v, df_i)
    pedidos = pedido_por_proveedor(df_v, df_c, df_i)
    rentabilidad = rentabilidad_gerencial(df_v, df_i)
    anomalias = detector_anomalias(df_v, df_c, df_i, df_n)
    diario = reporte_diario(df_v, df_c, df_i, df_n)
    return {
        "traslados": traslados,
        "pedidos": pedidos,
        "rentabilidad": rentabilidad,
        "anomalias": anomalias,
        "reporte_diario": diario,
    }


@router.get("/gerencia/traslados")
def gerencia_traslados(x_session_id: str = Header(default="default-session")):
    df_v, _, df_i, _ = _management_frames(x_session_id)
    return sugerido_traslados(df_v, df_i)


@router.get("/gerencia/pedidos")
def gerencia_pedidos(x_session_id: str = Header(default="default-session")):
    df_v, df_c, df_i, _ = _management_frames(x_session_id)
    return pedido_por_proveedor(df_v, df_c, df_i)


@router.get("/gerencia/anomalias")
def gerencia_anomalias(x_session_id: str = Header(default="default-session")):
    df_v, df_c, df_i, df_n = _management_frames(x_session_id)
    return detector_anomalias(df_v, df_c, df_i, df_n)


@router.get("/gerencia/reporte-diario")
def gerencia_reporte_diario(x_session_id: str = Header(default="default-session")):
    df_v, df_c, df_i, df_n = _management_frames(x_session_id)
    return reporte_diario(df_v, df_c, df_i, df_n)
# ── Inventario ───────────────────────────────────────────────────────────────
@router.get("/inventario")
def inventario(inv_min_dias: int = INV_MIN_DIAS, inv_max_dias: int = INV_MAX_DIAS, quieto_dias: int = QUIETO_DIAS_DEFAULT, x_session_id: str = Header(default="default-session")):
    df_i = get_df(x_session_id, "inventario")
    df_v = get_df(x_session_id, "ventas")
    if df_i is None or df_v is None:
        raise HTTPException(404, "Faltan datos")

    df_a = _inventory_with_total(df_i)

    # ── Filtrar ventas esporádicas para rotación ──
    from backend.services.management_analytics import _tag_sporadic
    df_v_filtered, sporadic_summary = _tag_sporadic(df_v)
    if df_v_filtered is None or df_v_filtered.empty:
        df_v_filtered = df_v

    # Rotación con datos filtrados (sin picos esporádicos)
    v_agr_filtered = df_v_filtered.groupby("Referencia", as_index=False).agg(uds_vendidas=("Cant", "sum"))
    # Última venta con datos completos
    v_agr_ultima = df_v.groupby("Referencia", as_index=False).agg(ultima_venta=("Fecha", "max"))

    df_a = df_a.merge(v_agr_filtered, on="Referencia", how="left")
    df_a = df_a.merge(v_agr_ultima, on="Referencia", how="left")
    df_a["uds_vendidas"] = df_a["uds_vendidas"].fillna(0)

    # Info de esporádicas excluidas
    if not sporadic_summary.empty:
        df_a = df_a.merge(sporadic_summary, on="Referencia", how="left")
        df_a["uds_esporadicas_excluidas"] = df_a["uds_esporadicas_excluidas"].fillna(0)
    else:
        df_a["uds_esporadicas_excluidas"] = 0

    max_fecha = df_v["Fecha"].max()
    min_fecha = df_v["Fecha"].min()
    dias = max((max_fecha - min_fecha).days + 1, 1) if pd.notna(max_fecha) and pd.notna(min_fecha) else 1

    if pd.notna(max_fecha):
        df_a["dias_sin_venta"] = (max_fecha - df_a["ultima_venta"]).dt.days.fillna(9999)
    else:
        df_a["dias_sin_venta"] = 9999

    df_a["rotacion_diaria"] = df_a["uds_vendidas"] / dias
    df_a["rotacion_proyectada"] = df_a["rotacion_diaria"]
    df_a["factor_tendencia"] = 1.0

    import numpy as np
    df_a["cobertura_dias"] = np.where(df_a["rotacion_diaria"] > 0, df_a["Total"] / df_a["rotacion_diaria"], 9999)

    bajo = df_a[(df_a["cobertura_dias"] < inv_min_dias) & (df_a["rotacion_diaria"] > 0)].copy()
    bajo["deficit"] = (inv_min_dias * bajo["rotacion_diaria"]) - bajo["Total"]
    bajo["deficit"] = bajo["deficit"].clip(lower=1).round()
    bajo["clasificacion_abc"] = "B"
    bajo_stock_tabla = json.loads(bajo.sort_values("deficit", ascending=False).to_json(orient="records"))

    quieto = df_a[(df_a["Total"] > 0) & (df_a["dias_sin_venta"] >= quieto_dias)].copy()
    if "Precio Compra" in quieto.columns:
        quieto["capital_inmovilizado"] = quieto["Total"] * pd.to_numeric(quieto["Precio Compra"], errors="coerce").fillna(0)
    else:
        quieto["capital_inmovilizado"] = 0

    inventario_quieto_tabla = json.loads(quieto.sort_values("capital_inmovilizado", ascending=False).to_json(orient="records"))

    top_deficit = json.loads(
        bajo.nlargest(15, "deficit")
        .assign(nombre=lambda x: x["Descripcion"].astype(str).str[:30])
        .to_json(orient="records")
    ) if not bajo.empty else []
    top_quieto = json.loads(
        quieto.nlargest(15, "capital_inmovilizado")
        .assign(nombre=lambda x: x["Descripcion"].astype(str).str[:30])
        .to_json(orient="records")
    ) if not quieto.empty else []

    excluir_selector = [
        "Referencia", "Descripcion", "Laboratorio", "Nivel", "Precio Compra", "Precio Venta",
        "Comision", "Utilidad", "Stock Maximo", "Stock Minimo", "Total", "IVA", "Codigo",
    ]
    sedes_disponibles = [
        c for c in df_i.columns
        if c not in excluir_selector and pd.api.types.is_numeric_dtype(df_i[c])
    ]

    # Calculate KPIs for frontend
    kpis = {
        "bajo_stock": int(len(bajo)),
        "sin_stock": int(len(bajo[bajo["Total"] <= 0])),
        "sobre_stock": int(len(df_a[(df_a["cobertura_dias"] > inv_max_dias) & (df_a["rotacion_diaria"] > 0)])),
        "inventario_quieto": int(len(quieto)),
        "capital_quieto": float(quieto["capital_inmovilizado"].sum()),
        "capital_exceso": 0.0,
        "inv_min_dias": int(inv_min_dias),
        "inv_max_dias": int(inv_max_dias),
        "quieto_dias": int(quieto_dias),
    }

    return {
        "kpis": kpis,
        "bajo_stock_tabla": bajo_stock_tabla,
        "inventario_quieto_tabla": inventario_quieto_tabla,
        "top_deficit": top_deficit,
        "top_quieto": top_quieto,
        "top_sobre": [],
        "sobre_stock_tabla": [],
        "stock_por_sede": {},
        "sedes_disponibles": sedes_disponibles,
    }


# â”€â”€ Compras â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@router.get("/compras")
def compras(
    fecha_ini: str = None,
    fecha_fin: str = None,
    proveedor: str = "Todos",
    estado: str = "Todos",
    buscar: str = "",
    inv_min_dias: int = INV_MIN_DIAS,
    inv_max_dias: int = INV_MAX_DIAS,
    x_session_id: str = Header(default="default-session"),
):
    df_c = get_df(x_session_id, "compras", fecha_ini=fecha_ini, fecha_fin=fecha_fin)
    df_v = get_df(x_session_id, "ventas", fecha_ini=fecha_ini, fecha_fin=fecha_fin)
    df_i = get_df(x_session_id, "inventario")
    if df_c is None or df_v is None:
        raise HTTPException(404, "Faltan datos")

    c = (
        df_c.groupby(["REFERENCIA", "DESCRIPCION"], as_index=False)
        .agg(uds_compradas=("CANT", "sum"), proveedor=("PROVEEDOR", "first"))
        .rename(columns={"REFERENCIA": "Referencia", "DESCRIPCION": "Descripcion"})
    )
    v = df_v.groupby("Referencia", as_index=False).agg(uds_vendidas=("Cant", "sum"))

    comp = c.merge(v, on="Referencia", how="outer").fillna({"uds_compradas": 0, "uds_vendidas": 0})
    if df_i is not None:
        inv_cols = [c for c in ["Referencia", "Descripcion", "Total", "Nivel"] if c in df_i.columns]
        inv = _inventory_with_total(df_i)[inv_cols].rename(columns={"Total": "inv_actual"})
        comp = comp.merge(inv, on="Referencia", how="left").fillna({"inv_actual": 0})
        comp["Descripcion"] = comp["Descripcion_x"].fillna(comp.get("Descripcion_y")) if "Descripcion_x" in comp.columns else comp.get("Descripcion")
        comp = comp.drop(columns=[c for c in ["Descripcion_x", "Descripcion_y"] if c in comp.columns])
    else:
        comp["inv_actual"] = 0
        comp["Descripcion"] = comp["Descripcion"].fillna("")

    comp["inv_inicial"] = comp["inv_actual"] + comp["uds_vendidas"] - comp["uds_compradas"]
    dias_periodo = 30
    if "Fecha" in df_v.columns and df_v["Fecha"].notna().any():
        dias_periodo = _inclusive_days(df_v["Fecha"].min(), df_v["Fecha"].max(), default=30)

    comp["venta_diaria"] = comp["uds_vendidas"] / max(dias_periodo, 1)
    comp["cobertura_dias"] = np.where(comp["venta_diaria"] > 0, comp["inv_actual"] / comp["venta_diaria"], 9999)
    comp["estado"] = np.select(
        [comp["cobertura_dias"] < inv_min_dias, comp["cobertura_dias"] > inv_max_dias],
        ["desabastecimiento", "sobre_compra"],
        default="equilibrio",
    )

    filtered = comp.copy()
    if proveedor != "Todos":
        filtered = filtered[filtered["proveedor"] == proveedor]
    if estado != "Todos":
        filtered = filtered[filtered["estado"] == estado]
    if buscar:
        mask = (
            filtered["Referencia"].astype(str).str.contains(buscar, case=False, na=False)
            | filtered["Descripcion"].astype(str).str.contains(buscar, case=False, na=False)
        )
        filtered = filtered[mask]

    top_prov = (
        df_c.groupby("PROVEEDOR", as_index=False)
        .agg(unidades=("CANT", "sum"), costo_total=("Costo Total", "sum"))
        .nlargest(10, "unidades")
        .rename(columns={"PROVEEDOR": "proveedor"})
    )

    return {
        "kpis": {
            "total_comprado": int(comp["uds_compradas"].sum()),
            "total_vendido": int(comp["uds_vendidas"].sum()),
            "n_sobre_compra": int(len(comp[comp["estado"] == "sobre_compra"])),
            "n_desabastecimiento": int(len(comp[comp["estado"] == "desabastecimiento"])),
            "dias_periodo": int(dias_periodo),
            "inv_min_dias": inv_min_dias,
            "inv_max_dias": inv_max_dias,
        },
        "comparativo": json.loads(filtered.sort_values("uds_compradas", ascending=False).to_json(orient="records")),
        "top_proveedores": json.loads(top_prov.to_json(orient="records")),
        "filtros": {
            "proveedores": sorted(df_c["PROVEEDOR"].dropna().unique().tolist()),
            "estados": ["sobre_compra", "desabastecimiento", "equilibrio"],
        },
    }


# â”€â”€ Notas CrÃ©dito / Devoluciones â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@router.get("/notas-credito")
def endpoint_notas_credito(
    fecha_ini: str = None,
    fecha_fin: str = None,
    x_session_id: str = Header(default="default-session")
):
    fecha_ini, fecha_fin = _normalize_optional_date_range(fecha_ini, fecha_fin)
    df_nc = get_df(x_session_id, "notas_credito", fecha_ini=fecha_ini, fecha_fin=fecha_fin)
    df_v  = get_df(x_session_id, "ventas", fecha_ini=fecha_ini, fecha_fin=fecha_fin)
    if df_nc is None:
        raise HTTPException(404, "No hay datos de notas credito cargados")

    df_nc = _apply_date_filter(df_nc, "Fecha", fecha_ini, fecha_fin)
    df_v = _apply_date_filter(df_v, "Fecha", fecha_ini, fecha_fin) if df_v is not None else None
    notas_unicas = _notas_credito_note_frame(df_nc)
    lineas_producto = _notas_credito_product_frame(df_nc)
    dias_periodo = 1
    if fecha_ini and fecha_fin:
        dias_periodo = max((datetime.strptime(fecha_fin, "%Y-%m-%d").date() - datetime.strptime(fecha_ini, "%Y-%m-%d").date()).days + 1, 1)
    elif not notas_unicas.empty and "Fecha" in notas_unicas.columns and notas_unicas["Fecha"].notna().any():
        dias_periodo = _inclusive_days(notas_unicas["Fecha"].min(), notas_unicas["Fecha"].max())

    if notas_unicas.empty:
        return {
            "kpis": {
                "total_devuelto": 0,
                "n_notas": 0,
                "promedio_nota": 0,
                "tasa_pct": 0,
                "ingresos_brutos": float(df_v["Ingreso"].sum()) if df_v is not None and "Ingreso" in df_v.columns else 0,
                "ingresos_netos": float(df_v["Ingreso"].sum()) if df_v is not None and "Ingreso" in df_v.columns else 0,
                "saldo_pendiente": 0,
                "dias_periodo": int(dias_periodo),
            },
            "tendencia": [],
            "por_sede": [],
            "por_vendedor": [],
            "por_motivo": [],
            "top_productos_devueltos": [],
            "tabla": [],
        }

    vendedor_series = _preferred_vendedor_series(notas_unicas)
    if vendedor_series is not None:
        notas_unicas["Vendedor"] = vendedor_series

    total_devuelto = float(notas_unicas["Total Neto"].sum())
    n_notas        = int(len(notas_unicas))
    promedio_nota  = round(total_devuelto / n_notas, 0) if n_notas > 0 else 0
    total_saldo    = float(notas_unicas["Saldo"].sum()) if "Saldo" in notas_unicas.columns else 0

    ing_bruto      = float(df_v["Ingreso"].sum()) if df_v is not None else 0
    tasa_pct       = round(total_devuelto / ing_bruto * 100, 2) if ing_bruto > 0 else 0
    ingresos_netos = round(ing_bruto - total_devuelto, 0)

    # Tendencia semanal
    tendencia = []
    if "Fecha" in notas_unicas.columns and notas_unicas["Fecha"].notna().any():
        s = notas_unicas.set_index("Fecha").resample("W")["Total Neto"].sum().reset_index()
        tendencia = [{"fecha": str(r["Fecha"].date()), "total": round(r["Total Neto"], 0)}
                     for _, r in s.iterrows()]

    # Por sede
    col_sede = "Punto Venta" if "Punto Venta" in notas_unicas.columns else None
    por_sede = []
    if col_sede:
        sede_df = (notas_unicas.groupby(col_sede, as_index=False)
                   .agg(total_devuelto=("Total Neto", "sum"), n_notas=("Total Neto", "count"))
                   .sort_values("total_devuelto", ascending=False)
                   .rename(columns={col_sede: "sede"}))
        por_sede = json.loads(sede_df.to_json(orient="records"))

    # Por vendedor
    por_vendedor = []
    if "Vendedor" in notas_unicas.columns:
        vend_df = (notas_unicas.groupby("Vendedor", as_index=False)
                   .agg(total_devuelto=("Total Neto", "sum"), n_notas=("Total Neto", "count"))
                   .sort_values("total_devuelto", ascending=False)
                   .rename(columns={"Vendedor": "vendedor"}))
        por_vendedor = json.loads(vend_df.to_json(orient="records"))

    # Por motivo
    por_motivo = []
    if "Motivo" in notas_unicas.columns:
        mot_df = (notas_unicas.groupby("Motivo", as_index=False)
                  .agg(total=("Total Neto", "sum"), n=("Total Neto", "count"))
                  .sort_values("total", ascending=False))
        por_motivo = json.loads(mot_df.to_json(orient="records"))

    # Productos devueltos: usar las lineas reales de la nota credito.
    top_productos_devueltos = []
    if not lineas_producto.empty:
        cantidad_col = "Cantidad" if "Cantidad" in lineas_producto.columns else None
        agg_map = {"ingreso_devuelto": ("devuelto_asignado", "sum")}
        if cantidad_col:
            agg_map["unidades_devueltas"] = (cantidad_col, "sum")
        prod_dev = (lineas_producto.groupby(["Referencia", "Descripcion"], as_index=False)
                    .agg(**agg_map)
                    .sort_values("ingreso_devuelto", ascending=False)
                    .head(15))
        if "unidades_devueltas" not in prod_dev.columns:
            prod_dev["unidades_devueltas"] = 0
        prod_dev["nombre"] = prod_dev["Descripcion"].astype(str).str[:35]
        top_productos_devueltos = json.loads(prod_dev.to_json(orient="records"))

    # Tabla detalle
    cols_tabla = [c for c in ["Fecha", "NotaCredito", "Punto Venta", "Total Neto",
                               "Vendedor", "Creada", "Motivo", "Factura", "Observaciones", "Saldo"]
                  if c in notas_unicas.columns]
    tabla = _df_to_records(notas_unicas[cols_tabla].sort_values("Fecha", ascending=False), max_rows=300)

    return {
        "kpis": {
            "total_devuelto":  round(total_devuelto, 0),
            "n_notas":         n_notas,
            "promedio_nota":   promedio_nota,
            "tasa_pct":        tasa_pct,
            "ingresos_brutos": round(ing_bruto, 0),
            "ingresos_netos":  ingresos_netos,
            "saldo_pendiente": round(total_saldo, 0),
            "dias_periodo":    int(dias_periodo),
        },
        "tendencia":               tendencia,
        "por_sede":                por_sede,
        "por_vendedor":            por_vendedor,
        "por_motivo":              por_motivo,
        "top_productos_devueltos": top_productos_devueltos,
        "tabla":                   tabla,
    }


# Ventas

@router.get("/ventas")
def ventas(sede: str = "Todas", nivel: str = "Todos",
           laboratorio: str = "Todos",
           fecha_ini: str = None, fecha_fin: str = None,
           x_session_id: str = Header(default="default-session")):

    from backend.services.db_config import is_db_configured
    from backend.services.db_service import get_db_service

    if is_db_configured():
        db = get_db_service()
        if db:
            return db.get_analisis_ventas_sql(
                fecha_ini=fecha_ini,
                fecha_fin=fecha_fin,
                sede=sede,
                nivel=nivel,
                laboratorio=laboratorio
            )

    # Fallback si no hay BD (Mantener cÃ³digo original como backup de memoria)
    df = get_df(x_session_id, "ventas", fecha_ini=fecha_ini, fecha_fin=fecha_fin, sede=sede)
    if df is None:
        raise HTTPException(404, "No hay datos de ventas")

    df = _apply_date_filter(df, "Fecha", fecha_ini, fecha_fin)
    if sede != "Todas":
        df = df[df["Punto Venta"] == sede]
    if nivel != "Todos" and "Nivel" in df.columns:
        df = df[df["Nivel"] == nivel]
    if laboratorio != "Todos" and "Laboratorio" in df.columns:
        df = df[df["Laboratorio"] == laboratorio]

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
    vendedor_series = _preferred_vendedor_series(df)
    if vendedor_series is not None:
        df["__VendedorVenta"] = vendedor_series
        agg_map = {
            "unidades": ("Cant", "sum"),
            "ingresos": ("Ingreso", "sum"),
        }
        agg_map["facturas"] = ("Factura", "nunique") if "Factura" in df.columns else ("Referencia", "count")
        vendedores = (df.groupby("__VendedorVenta", as_index=False)
                      .agg(**agg_map)
                      .sort_values("ingresos", ascending=False)
                      .rename(columns={"__VendedorVenta":"vendedor"}))
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


# â”€â”€ Metas y Proyecciones â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@router.get("/metas")
def proyeccion_metas(
    agresividad: str = "normal",
    fecha_ini: str = None,
    fecha_fin: str = None,
    x_session_id: str = Header(default="default-session")
):
    df = get_df(x_session_id, "ventas")
    if df is None or len(df) == 0:
        df = get_default_ventas()
    if df is None or len(df) == 0:
        raise HTTPException(404, "No hay datos de ventas")

    agresividad_map = {
        "conservador": 1.02,
        "normal": 1.05,
        "agresivo": 1.10,
    }
    factor_crecimiento = agresividad_map.get(agresividad, 1.05)

    if "Fecha" not in df.columns:
        raise HTTPException(400, "No hay columna Fecha para calcular metas")
    if "Ingreso" not in df.columns:
        raise HTTPException(400, "No hay columna Ingreso para calcular metas")

    df = df.copy()
    df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce")
    df = df[df["Fecha"].notna()]
    if df.empty:
        raise HTTPException(400, "No hay fechas vÃ¡lidas en ventas")

    if fecha_ini and fecha_fin:
        try:
            d_ini = datetime.strptime(fecha_ini, "%Y-%m-%d").date()
            d_fin = datetime.strptime(fecha_fin, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(400, "Formato de fecha invÃ¡lido o rango errÃ³neo")
        if d_fin < d_ini:
            raise HTTPException(400, "Formato de fecha invÃ¡lido o rango errÃ³neo")
        y_obj, m_obj = d_ini.year, d_ini.month
        dias_totales_proy = (d_fin - d_ini).days + 1
    else:
        hoy = date.today()
        y_obj, m_obj = hoy.year, hoy.month

        # Si el mes objetivo actual no tiene base en datos, usar el Ãºltimo mes disponible + 1.
        meses_disponibles = (
            df.assign(ym=df["Fecha"].dt.to_period("M"))
            .groupby("ym", as_index=False)
            .size()
            .sort_values("ym")
        )
        if not meses_disponibles.empty:
            ultimo_periodo = meses_disponibles["ym"].iloc[-1]
            ultimo_y, ultimo_m = int(ultimo_periodo.year), int(ultimo_periodo.month)
            if m_obj == 1:
                y_base_actual, m_base_actual = y_obj - 1, 12
            else:
                y_base_actual, m_base_actual = y_obj, m_obj - 1
            existe_base_actual = (
                (df["Fecha"].dt.year == y_base_actual) & (df["Fecha"].dt.month == m_base_actual)
            ).any()
            if not existe_base_actual:
                if ultimo_m == 12:
                    y_obj, m_obj = ultimo_y + 1, 1
                else:
                    y_obj, m_obj = ultimo_y, ultimo_m + 1

        _, dias_totales_proy = calendar.monthrange(y_obj, m_obj)

    if m_obj == 1:
        y_base, m_base = y_obj - 1, 12
    else:
        y_base, m_base = y_obj, m_obj - 1

    y_hist = y_obj - 1
    m_hist_obj = m_obj
    m_hist_prev = m_base

    habiles = dias_totales_proy
    domingos_festivos = 0

    col_sede = "Punto Venta" if "Punto Venta" in df.columns else None
    col_vend = None
    vendedor_series = _preferred_vendedor_series(df)
    if vendedor_series is not None:
        df["__VendedorMeta"] = vendedor_series
        col_vend = "__VendedorMeta"
    if not col_sede:
        raise HTTPException(400, "Falta columna de Sede (Punto Venta)")

    sedes_data = []

    for sede, df_sede_all in df.groupby(col_sede):
        df_base = df_sede_all[(df_sede_all["Fecha"].dt.year == y_base) & (df_sede_all["Fecha"].dt.month == m_base)].copy()
        if df_base.empty:
            limite_base = pd.Timestamp(date(y_obj, m_obj, 1))
            historico_sede = df_sede_all[df_sede_all["Fecha"] < limite_base].copy()
            if historico_sede.empty:
                continue
            ultimo_periodo_sede = historico_sede["Fecha"].dt.to_period("M").max()
            df_base = historico_sede[historico_sede["Fecha"].dt.to_period("M") == ultimo_periodo_sede].copy()
            if df_base.empty:
                continue

        ventas_mes_anterior = float(df_base["Ingreso"].sum())
        base_period = df_base["Fecha"].dt.to_period("M").iloc[0]
        base_year, base_month = int(base_period.year), int(base_period.month)
        dias_mes_anterior = calendar.monthrange(base_year, base_month)[1]
        idp_sede = ventas_mes_anterior / max(dias_mes_anterior, 1)
        proyeccion_base = idp_sede * dias_totales_proy

        df_hist_obj = df_sede_all[(df_sede_all["Fecha"].dt.year == y_hist) & (df_sede_all["Fecha"].dt.month == m_hist_obj)]
        df_hist_prev = df_sede_all[(df_sede_all["Fecha"].dt.year == y_hist) & (df_sede_all["Fecha"].dt.month == m_hist_prev)]
        venta_hist_obj = float(df_hist_obj["Ingreso"].sum())
        venta_hist_prev = float(df_hist_prev["Ingreso"].sum())

        incremento_hist = (venta_hist_obj / venta_hist_prev - 1.0) if venta_hist_prev > 0 else 0.0
        incremento_hist = max(min(incremento_hist, 0.35), -0.20)
        incremento_aplicado = incremento_hist + (factor_crecimiento - 1.0)

        meta_sede = max(proyeccion_base * (1.0 + incremento_aplicado), 0.0)

        vendedores = []
        vends_raw = []
        if col_vend and col_vend in df_base.columns:
            vend_valid = df_base[
                df_base[col_vend].notna()
                & (df_base[col_vend].astype(str).str.strip() != "")
            ]
            for vend, df_v in vend_valid.groupby(col_vend):
                ingreso_v = float(df_v["Ingreso"].sum())
                aporte_v = ingreso_v / ventas_mes_anterior if ventas_mes_anterior > 0 else 0
                if aporte_v < 0.05:
                    continue
                ticket_v = ingreso_v / max(df_v["Factura"].nunique(), 1) if "Factura" in df_v.columns else 0.0
                vends_raw.append({
                    "nombre": vend,
                    "ingreso_actual": ingreso_v,
                    "ticket_promedio": float(ticket_v),
                    "aporte": round(aporte_v * 100, 1)
                })
        num_vendedores = len(vends_raw)
        peso_igual = 1.0 / num_vendedores if num_vendedores > 0 else 0

        for vendedor in vends_raw:
            meta_vendedor = meta_sede * peso_igual
            vendedores.append({
                "nombre": vendedor["nombre"],
                "ingreso_actual": vendedor["ingreso_actual"],
                "ticket_promedio": vendedor["ticket_promedio"],
                "aporte_historico": vendedor["aporte"],
                "peso_distribucion": round(peso_igual * 100, 1),
                "meta": float(meta_vendedor),
            })

        vendedores.sort(key=lambda x: x["meta"], reverse=True)

        sedes_data.append({
            "sede": sede,
            "ingreso_actual": float(ventas_mes_anterior),
            "idp": float(idp_sede),
            "tendencia": round(1.0 + incremento_hist, 2),
            "proyeccion_base": float(proyeccion_base),
            "meta_sugerida": float(meta_sede),
            "incremento_hist_pct": round(incremento_hist * 100, 2),
            "incremento_aplicado_pct": round(incremento_aplicado * 100, 2),
            "ventas_hist_mismo_mes": float(venta_hist_obj),
            "ventas_hist_mes_anterior": float(venta_hist_prev),
            "mes_base_sede": f"{base_year:04d}-{base_month:02d}",
            "vendedores": vendedores,
        })

    sedes_data.sort(key=lambda x: x["meta_sugerida"], reverse=True)
    ingreso_actual_total = sum(s["ingreso_actual"] for s in sedes_data)
    proyeccion_total = sum(s["proyeccion_base"] for s in sedes_data)
    meta_total = sum(s["meta_sugerida"] for s in sedes_data)

    mes_base_usado = f"{y_base:04d}-{m_base:02d}"
    periodo_objetivo = (
        {"inicio": str(d_ini), "fin": str(d_fin)}
        if fecha_ini and fecha_fin
        else {"inicio": f"{y_obj:04d}-{m_obj:02d}-01", "fin": f"{y_obj:04d}-{m_obj:02d}-{dias_totales_proy:02d}"}
    )

    return {
        "resumen": {
            "ingreso_actual_total": round(ingreso_actual_total, 0),
            "proyeccion_total": round(proyeccion_total, 0),
            "meta_total": round(meta_total, 0),
            "dias_mes": int(dias_totales_proy),
            "dias_habiles": int(habiles),
            "dias_festivos": int(domingos_festivos),
            "mes_base_usado": mes_base_usado,
            "agresividad": agresividad,
            "periodo_objetivo": periodo_objetivo,
        },
        "sedes": sedes_data,
    }

    df_c = _apply_date_filter(df_c, "FECHA", fecha_ini, fecha_fin)
    df_v = _apply_date_filter(df_v, "Fecha", fecha_ini, fecha_fin)

    # 1. Agrupar Compras por Referencia
    c_agr = df_c.groupby("REFERENCIA", as_index=False)["CANT"].sum().rename(columns={"REFERENCIA": "Referencia", "CANT": "uds_compradas"})

    # 2. Agrupar Ventas por Referencia
    v_agr = df_v.groupby("Referencia", as_index=False)["Cant"].sum().rename(columns={"Cant": "uds_vendidas"})

    # 3. Cruzar con Inventario Actual
    df_i_total = _inventory_with_total(df_i)
    comp = df_i_total[["Referencia", "Descripcion", "Total"]].copy()
    comp = comp.rename(columns={"Total": "inv_actual"})

    # Intentar obtener CategorÃ­a/Nivel para diferenciar perecederos
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

    # 4. INGENIERÃA INVERSA: Inventario Inicial
    comp["inv_inicial"] = comp["inv_actual"] - comp["uds_compradas"] + comp["uds_vendidas"]

    # Filtrar productos inactivos (todo en 0)
    comp = comp[(comp["inv_actual"] > 0) | (comp["uds_compradas"] > 0) | (comp["uds_vendidas"] > 0)]

    # 5. DÃ­as del Periodo
    dias_periodo = 30
    if "Fecha" in df_v.columns and df_v["Fecha"].notna().any():
        dias_periodo = _inclusive_days(df_v["Fecha"].min(), df_v["Fecha"].max(), default=30)

    comp["venta_diaria"] = comp["uds_vendidas"] / dias_periodo
    comp["cobertura_dias"] = comp.apply(lambda x: (x["inv_actual"] / x["venta_diaria"]) if x["venta_diaria"] > 0 else 9999, axis=1)

    # 6. Estado (Basado en Cobertura 25-40 dÃ­as)
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


# â”€â”€ Sedes â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@router.get("/sedes")
def sedes(
    sede_detalle: str = None,
    fecha_ini: str = None,
    fecha_fin: str = None,
    x_session_id: str = Header(default="default-session")
):
    df_v = get_df(x_session_id, "ventas")
    df_i = None
    try:
        df_i = get_df(x_session_id, "inventario")
    except Exception:
        # Sedes can be calculated from historical sales alone. Inventory is only
        # used for the optional stock summary and may be blocked by Azure SQL.
        df_i = None
    if df_v is None:
        raise HTTPException(404, "No hay datos de ventas")
    df_v = _apply_date_filter(df_v, "Fecha", fecha_ini, fecha_fin)

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


