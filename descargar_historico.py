import argparse
import logging
import os
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd
from dateutil.relativedelta import relativedelta
from dotenv import load_dotenv

load_dotenv()

ROOT_DIR = Path(__file__).resolve().parent
sys.path.append(str(ROOT_DIR))

from backend.services.db_config import is_db_configured
from backend.services.safe_query import get_executor


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

OUTPUT_DIR = Path(os.getenv("HISTORICAL_DATA_DIR", ROOT_DIR / "data" / "historico"))
BACKUP_DIR = OUTPUT_DIR / "_backups"
DEFAULT_YEARS_BACK = 2
TARGET_ROWS_PER_CHUNK = 35_000
MAX_RECURSION_DEPTH = 12


@dataclass(frozen=True)
class DatasetConfig:
    name: str
    date_column: str
    select_sql: str
    count_sql: str
    dedupe_subset: tuple[str, ...]


DATASETS = {
    "ventas": DatasetConfig(
        name="HISTORICO_VENTAS",
        date_column="Fecha",
        dedupe_subset=("FacturaID", "Referencia", "Fecha", "ID_PuntoVenta"),
        count_sql="""
            SELECT COUNT_BIG(*) AS filas
            FROM FACTURAS f
            INNER JOIN FACTURAS_PRODUCTOS fp ON f.ID = fp.ID_Factura
            WHERE f.Enabled = 1
              AND f.Anulada = 'N/A'
              AND f.FechaFactura >= ?
              AND f.FechaFactura < ?
        """,
        select_sql="""
            SELECT
                f.ID AS FacturaID,
                f.Factura,
                f.FechaFactura AS Fecha,
                f.ID_PuntoVenta,
                fp.Referencia,
                fp.Descripcion,
                fp.Cantidad AS Cant,
                fp.PrecioVenta AS [Precio Venta],
                fp.Cantidad * fp.PrecioVenta AS Ingreso,
                r.ID_Laboratorio,
                r.ID_Nivel,
                f.Creada,
                u.Nombre AS NombreVendedor,
                f.ID_Cliente,
                f.Total
            FROM FACTURAS f
            INNER JOIN FACTURAS_PRODUCTOS fp ON f.ID = fp.ID_Factura
            LEFT JOIN REFERENCIAS r ON fp.Referencia = r.Referencia
            LEFT JOIN USUARIOS u ON f.Creada = u.Login
            WHERE f.Enabled = 1
              AND f.Anulada = 'N/A'
              AND f.FechaFactura >= ?
              AND f.FechaFactura < ?
        """,
    ),
    "compras": DatasetConfig(
        name="HISTORICO_COMPRAS",
        date_column="FECHA",
        dedupe_subset=("CompraID", "REFERENCIA"),
        count_sql="""
            SELECT COUNT_BIG(*) AS filas
            FROM COMPRAS c
            INNER JOIN COMPRAS_PRODUCTOS cp ON c.ID = cp.ID_Compra
            WHERE c.Enabled = 1
              AND c.Fecha >= ?
              AND c.Fecha < ?
        """,
        select_sql="""
            SELECT
                c.ID AS CompraID,
                c.Fecha AS FECHA,
                c.ID_Proveedor,
                cp.Referencia AS REFERENCIA,
                cp.Descripcion AS DESCRIPCION,
                r.ID_Laboratorio,
                cp.PrecioCompra AS PRECIO,
                cp.Cantidad AS CANT,
                c.ID_PuntoVenta,
                cp.Cantidad * cp.PrecioCompra AS [Costo Total]
            FROM COMPRAS c
            INNER JOIN COMPRAS_PRODUCTOS cp ON c.ID = cp.ID_Compra
            LEFT JOIN REFERENCIAS r ON cp.Referencia = r.Referencia
            WHERE c.Enabled = 1
              AND c.Fecha >= ?
              AND c.Fecha < ?
        """,
    ),
    "notas_credito": DatasetConfig(
        name="HISTORICO_NOTAS_CREDITO",
        date_column="Fecha",
        dedupe_subset=("NotaCreditoID", "ID_PuntoVenta", "Referencia", "Cantidad", "PrecioVenta", "TotalProducto"),
        count_sql="""
            SELECT COUNT_BIG(*) AS filas
            FROM NOTAS_CREDITO nc
            LEFT JOIN NOTAS_CREDITO_PRODUCTOS ncp
              ON nc.ID = ncp.ID_NotaCredito
             AND nc.ID_PuntoVenta = ncp.ID_PuntoVenta
            WHERE nc.Enabled = 1
              AND nc.Fecha >= ?
              AND nc.Fecha < ?
        """,
        select_sql="""
            SELECT
                nc.ID AS NotaCreditoID,
                nc.Fecha,
                nc.ID_PuntoVenta,
                nc.Creada,
                u.Nombre AS NombreVendedor,
                nc.SubTotal AS SubTotalNota,
                nc.IVA AS IVANota,
                nc.Total AS TotalNota,
                nc.Saldo,
                nc.Observaciones,
                ncp.Referencia,
                r.Descripcion1 AS Descripcion,
                r.ID_Laboratorio,
                ncp.Cantidad,
                ncp.PrecioVenta,
                ncp.IVA AS IVAProducto,
                ncp.Total AS TotalProducto
            FROM NOTAS_CREDITO nc
            LEFT JOIN NOTAS_CREDITO_PRODUCTOS ncp
              ON nc.ID = ncp.ID_NotaCredito
             AND nc.ID_PuntoVenta = ncp.ID_PuntoVenta
            LEFT JOIN REFERENCIAS r ON ncp.Referencia = r.Referencia
            LEFT JOIN USUARIOS u ON nc.Creada = u.Login
            WHERE nc.Enabled = 1
              AND nc.Fecha >= ?
              AND nc.Fecha < ?
        """,
    ),
    "notas_devolucion": DatasetConfig(
        name="HISTORICO_NOTAS_DEVOLUCION",
        date_column="Fecha",
        dedupe_subset=("NotaDevolucionID", "Referencia"),
        count_sql="""
            SELECT COUNT_BIG(*) AS filas
            FROM NOTAS_DEVOLUCION nd
            LEFT JOIN NOTAS_DEVOLUCION_PRODUCTOS ndp ON nd.ID = ndp.ID_NotaDevolucion
            WHERE nd.Fecha >= ?
              AND nd.Fecha < ?
        """,
        select_sql="""
            SELECT
                nd.ID AS NotaDevolucionID,
                nd.Fecha,
                nd.ID_PuntoVenta,
                nd.ID_Proveedor,
                ndp.Referencia,
                ndp.Descripcion,
                r.ID_Laboratorio,
                ndp.Cantidad,
                ndp.PrecioVenta,
                ndp.Total AS TotalProducto
            FROM NOTAS_DEVOLUCION nd
            LEFT JOIN NOTAS_DEVOLUCION_PRODUCTOS ndp ON nd.ID = ndp.ID_NotaDevolucion
            LEFT JOIN REFERENCIAS r ON ndp.Referencia = r.Referencia
            WHERE nd.Fecha >= ?
              AND nd.Fecha < ?
        """,
    ),
}


LOOKUP_QUERIES = {
    "LOOKUP_PUNTO_VENTA": "SELECT ID, Nombre FROM PUNTO_VENTA",
    "LOOKUP_LABORATORIOS": "SELECT ID, Nombre FROM LABORATORIOS",
    "LOOKUP_NIVELES": "SELECT ID, Nombre FROM NIVELES",
    "LOOKUP_PROVEEDORES": "SELECT ID, Nombre FROM PROVEEDORES",
}


INVENTORY_SQL = """
    SELECT
        i.Referencia,
        r.Descripcion1 AS Descripcion,
        r.ID_Laboratorio,
        i.Cantidad AS Total,
        r.PrecioCompra AS [Precio Compra],
        r.PrecioVenta AS [Precio Venta],
        r.StockMinimo AS [Stock Minimo],
        r.StockMaximo AS [Stock Maximo],
        r.ID_Nivel,
        r.Comision,
        r.Utilidad,
        r.Codigo,
        i.PdeV0,
        i.PdeV1,
        i.PdeV2,
        i.PdeV3,
        i.PdeV4,
        i.PdeV5,
        i.PdeV6,
        i.PdeV7,
        i.PdeV8,
        i.PdeV9,
        i.PdeV10,
        i.PdeV11,
        i.PdeV12,
        i.PdeV13,
        i.PdeV14,
        i.PdeV15,
        i.PdeV16,
        i.PdeV17,
        i.PdeV18,
        i.PdeV19
    FROM INVENTARIO i
    INNER JOIN REFERENCIAS r ON i.Referencia = r.Referencia
    WHERE r.Enabled = 1
"""


def check_parquet_support() -> bool:
    try:
        import pyarrow  # noqa: F401
        return True
    except ImportError:
        try:
            import fastparquet  # noqa: F401
            return True
        except ImportError:
            return False


def output_path(base_name: str) -> Path:
    suffix = ".parquet" if check_parquet_support() else ".csv"
    return OUTPUT_DIR / f"{base_name}{suffix}"


def read_local(path: Path, date_column: str | None = None) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_parquet(path) if path.suffix == ".parquet" else pd.read_csv(path)
    if date_column and date_column in df.columns:
        df[date_column] = pd.to_datetime(df[date_column], errors="coerce")
    return df


def backup_existing(path: Path) -> None:
    if not path.exists():
        return
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUP_DIR / f"{path.stem}_{stamp}{path.suffix}"
    shutil.copy2(path, backup_path)
    logger.info("Backup creado: %s", backup_path)


def save_df(df: pd.DataFrame, base_name: str) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = output_path(base_name)
    backup_existing(path)

    tmp_path = path.with_suffix(path.suffix + ".tmp")
    if path.suffix == ".parquet":
        df.to_parquet(tmp_path, index=False)
    else:
        df.to_csv(tmp_path, index=False)
    tmp_path.replace(path)
    logger.info("Guardado %s: %s filas en %s", base_name, f"{len(df):,}", path)
    return path


def merge_local(config: DatasetConfig, new_df: pd.DataFrame) -> pd.DataFrame:
    path = output_path(config.name)
    local_df = read_local(path, config.date_column)
    if local_df.empty:
        merged = new_df.copy()
    elif new_df.empty:
        merged = local_df.copy()
    else:
        merged = pd.concat([local_df, new_df], ignore_index=True)

    dedupe_cols = [col for col in config.dedupe_subset if col in merged.columns]
    if dedupe_cols:
        before = len(merged)
        merged = merged.drop_duplicates(subset=dedupe_cols, keep="last")
        removed = before - len(merged)
        if removed:
            logger.info("%s: %s duplicados removidos al mezclar", config.name, f"{removed:,}")

    if config.date_column in merged.columns:
        merged[config.date_column] = pd.to_datetime(merged[config.date_column], errors="coerce")
        merged = merged.sort_values(config.date_column)

    logger.info(
        "%s merge: local=%s nuevos=%s final=%s",
        config.name,
        f"{len(local_df):,}",
        f"{len(new_df):,}",
        f"{len(merged):,}",
    )
    return merged


def count_remote(executor, config: DatasetConfig, start: pd.Timestamp, end: pd.Timestamp) -> int:
    df = executor.execute_read(
        config.count_sql,
        params=(start.strftime("%Y-%m-%d %H:%M:%S"), end.strftime("%Y-%m-%d %H:%M:%S")),
        max_rows=10,
    )
    if df.empty:
        return 0
    return int(df.iloc[0]["filas"])


def split_range(start: pd.Timestamp, end: pd.Timestamp) -> tuple[pd.Timestamp, pd.Timestamp]:
    delta = end - start
    return start + (delta / 2), end


def fetch_range(
    executor,
    config: DatasetConfig,
    start: pd.Timestamp,
    end: pd.Timestamp,
    depth: int = 0,
) -> tuple[list[pd.DataFrame], int]:
    try:
        expected = count_remote(executor, config, start, end)
    except Exception as exc:
        if depth >= MAX_RECURSION_DEPTH:
            raise
        mid, _ = split_range(start, end)
        logger.warning(
            "%s: conteo lento/fallido %s -> %s (%s). Dividiendo rango.",
            config.name,
            start.strftime("%Y-%m-%d %H:%M"),
            end.strftime("%Y-%m-%d %H:%M"),
            exc,
        )
        left_dfs, left_count = fetch_range(executor, config, start, mid, depth + 1)
        right_dfs, right_count = fetch_range(executor, config, mid, end, depth + 1)
        return left_dfs + right_dfs, left_count + right_count

    if expected == 0:
        return [], 0

    if expected > TARGET_ROWS_PER_CHUNK and depth < MAX_RECURSION_DEPTH:
        mid, _ = split_range(start, end)
        left_dfs, left_count = fetch_range(executor, config, start, mid, depth + 1)
        right_dfs, right_count = fetch_range(executor, config, mid, end, depth + 1)
        return left_dfs + right_dfs, left_count + right_count

    logger.info(
        "Descargando %s %s -> %s: %s filas esperadas",
        config.name,
        start.strftime("%Y-%m-%d"),
        end.strftime("%Y-%m-%d"),
        f"{expected:,}",
    )
    df = executor.execute_read(
        config.select_sql,
        params=(start.strftime("%Y-%m-%d %H:%M:%S"), end.strftime("%Y-%m-%d %H:%M:%S")),
        max_rows=max(expected + 100, TARGET_ROWS_PER_CHUNK + 100),
    )
    if len(df) != expected:
        raise RuntimeError(
            f"{config.name} incompleto en {start} -> {end}: SQL cuenta {expected:,} filas, "
            f"pero se descargaron {len(df):,}."
        )
    return [df], expected


def month_ranges(start: pd.Timestamp, end: pd.Timestamp) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    ranges = []
    current = start
    while current < end:
        next_month = current + relativedelta(months=1)
        ranges.append((current, min(next_month, end)))
        current = next_month
    return ranges


def download_dataset(executor, config: DatasetConfig, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    all_dfs: list[pd.DataFrame] = []
    expected_total = 0
    for period_start, period_end in month_ranges(start, end):
        dfs, expected = fetch_range(executor, config, period_start, period_end)
        all_dfs.extend(dfs)
        expected_total += expected

    df = pd.concat(all_dfs, ignore_index=True) if all_dfs else pd.DataFrame()
    dedupe_cols = [col for col in config.dedupe_subset if col in df.columns]
    if dedupe_cols:
        before = len(df)
        df = df.drop_duplicates(subset=dedupe_cols, keep="last")
        if len(df) != before:
            logger.warning("%s: %s duplicados removidos", config.name, f"{before - len(df):,}")

    if len(df) != expected_total:
        logger.warning(
            "%s: SQL reporto %s filas y el archivo final tiene %s tras deduplicar",
            config.name,
            f"{expected_total:,}",
            f"{len(df):,}",
        )
    return df


def download_lookups(executor) -> None:
    for name, sql in LOOKUP_QUERIES.items():
        df = executor.execute_read(sql, max_rows=5_000)
        save_df(df, name)


def download_inventory(executor) -> pd.DataFrame:
    df = executor.execute_read(INVENTORY_SQL, max_rows=300_000)
    if df.empty:
        return df

    lookup_path = output_path("LOOKUP_PUNTO_VENTA")
    lookup = read_local(lookup_path)
    rename_dict = {}
    if not lookup.empty and {"ID", "Nombre"}.issubset(lookup.columns):
        rename_dict = dict(zip(lookup["ID"].astype(str), lookup["Nombre"].astype(str)))

    df = df.rename(columns={col: rename_dict[col] for col in df.columns if col in rename_dict})
    for col in df.columns:
        if col not in {"Referencia", "Descripcion", "ID_Laboratorio", "ID_Nivel", "Codigo"}:
            numeric = pd.to_numeric(df[col], errors="coerce")
            if numeric.notna().any():
                df[col] = numeric.fillna(0)
    save_df(df, "INVENTARIO_ACTUAL")
    return df


def local_summary() -> None:
    for config in DATASETS.values():
        path = output_path(config.name)
        df = read_local(path, config.date_column)
        if df.empty:
            logger.warning("%s: no existe o esta vacio", config.name)
            continue
        dates = pd.to_datetime(df[config.date_column], errors="coerce")
        logger.info(
            "%s local: %s filas, min=%s, max=%s, fechas_nulas=%s",
            config.name,
            f"{len(df):,}",
            dates.min(),
            dates.max(),
            f"{dates.isna().sum():,}",
        )

    inv_path = output_path("INVENTARIO_ACTUAL")
    inv = read_local(inv_path)
    if inv.empty:
        logger.warning("INVENTARIO_ACTUAL: no existe o esta vacio")
    else:
        logger.info("INVENTARIO_ACTUAL local: %s filas", f"{len(inv):,}")


def validate_against_sql(executor, start: pd.Timestamp, end: pd.Timestamp, dataset_names: list[str] | None = None) -> None:
    logger.info("=== VALIDACION SQL vs LOCAL ===")
    selected = DATASETS.values() if not dataset_names else [DATASETS[name] for name in dataset_names]
    for config in selected:
        path = output_path(config.name)
        local_df = read_local(path, config.date_column)
        local_count = 0
        if not local_df.empty and config.date_column in local_df.columns:
            dates = pd.to_datetime(local_df[config.date_column], errors="coerce")
            local_count = int(((dates >= start) & (dates < end)).sum())

        remote_total = 0
        for period_start, period_end in month_ranges(start, end):
            remote_total += count_remote(executor, config, period_start, period_end)

        status = "OK" if local_count == remote_total else "DIFERENCIA"
        logger.info(
            "%s: local=%s sql=%s estado=%s",
            config.name,
            f"{local_count:,}",
            f"{remote_total:,}",
            status,
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Descarga historica completa desde SmartPOS por bloques seguros.")
    parser.add_argument("--years", type=int, default=DEFAULT_YEARS_BACK, help="Anios hacia atras a descargar.")
    parser.add_argument(
        "--recent-days",
        type=int,
        default=None,
        help="Descarga solo los ultimos N dias. Ideal para actualizacion diaria.",
    )
    parser.add_argument(
        "--merge",
        action="store_true",
        help="Mezcla lo descargado con el archivo local y elimina duplicados.",
    )
    parser.add_argument(
        "--dataset",
        choices=["all", *DATASETS.keys()],
        default="all",
        help="Dataset a descargar.",
    )
    parser.add_argument("--validate-only", action="store_true", help="Solo valida local vs SQL, no descarga.")
    parser.add_argument("--skip-validate", action="store_true", help="No valida conteos contra SQL al terminar.")
    parser.add_argument("--local-summary", action="store_true", help="Muestra resumen local y termina.")
    parser.add_argument("--skip-lookups", action="store_true", help="No refresca lookups maestros.")
    parser.add_argument("--include-inventory", action="store_true", help="Descarga inventario actual.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.local_summary:
        local_summary()
        return

    if not is_db_configured():
        raise SystemExit("Base de datos no configurada en .env")

    executor = get_executor()
    connection = executor.test_connection()
    if not connection.get("connected"):
        raise SystemExit(f"No hay conexion SQL: {connection.get('message')}")

    if args.recent_days is not None:
        if args.recent_days < 1:
            raise SystemExit("--recent-days debe ser mayor o igual a 1")
        start = pd.Timestamp(datetime.now() - relativedelta(days=args.recent_days)).normalize()
    else:
        start = pd.Timestamp(datetime.now() - relativedelta(years=args.years)).normalize()
    end = pd.Timestamp(datetime.now()) + pd.Timedelta(seconds=1)
    logger.info("Rango objetivo: %s -> %s", start, end)

    if args.validate_only:
        selected_names = list(DATASETS.keys()) if args.dataset == "all" else [args.dataset]
        validate_against_sql(executor, start, end, selected_names)
        return

    if not args.skip_lookups:
        download_lookups(executor)

    if args.include_inventory:
        download_inventory(executor)

    selected = DATASETS.values() if args.dataset == "all" else [DATASETS[args.dataset]]
    for config in selected:
        df = download_dataset(executor, config, start, end)
        if args.merge:
            df = merge_local(config, df)
        save_df(df, config.name)

    if not args.skip_validate:
        selected_names = list(DATASETS.keys()) if args.dataset == "all" else [args.dataset]
        validate_against_sql(executor, start, end, selected_names)
    local_summary()


if __name__ == "__main__":
    main()
