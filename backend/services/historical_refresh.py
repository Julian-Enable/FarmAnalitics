import logging
from datetime import datetime

import pandas as pd

from backend.services.db_config import is_db_configured
from backend.services.historical_store import get_historical_store
from backend.services.safe_query import get_executor
from descargar_historico import DATASETS, download_dataset, download_lookups, merge_local, output_path, read_local, save_df


logger = logging.getLogger(__name__)


def _json_date(value) -> str | None:
    if value is None or pd.isna(value):
        return None
    return pd.Timestamp(value).strftime("%Y-%m-%d %H:%M:%S")


def _dataset_status(config) -> dict:
    path = output_path(config.name)
    result = {
        "name": config.name,
        "path": str(path),
        "exists": path.exists(),
        "rows": 0,
        "min": None,
        "max": None,
        "null_dates": None,
    }
    if not path.exists():
        return result

    if path.suffix.lower() == ".parquet":
        try:
            import pyarrow.parquet as pq

            parquet_file = pq.ParquetFile(path)
            result["rows"] = int(parquet_file.metadata.num_rows)
            table = pq.read_table(path, columns=[config.date_column])
            dates = pd.to_datetime(table.column(config.date_column).to_pandas(), errors="coerce")
        except Exception:
            df = read_local(path, config.date_column)
            result["rows"] = int(len(df))
            dates = pd.to_datetime(df[config.date_column], errors="coerce") if config.date_column in df.columns else pd.Series(dtype="datetime64[ns]")
    else:
        df = read_local(path, config.date_column)
        result["rows"] = int(len(df))
        dates = pd.to_datetime(df[config.date_column], errors="coerce") if config.date_column in df.columns else pd.Series(dtype="datetime64[ns]")

    if not dates.empty:
        result["min"] = _json_date(dates.min())
        result["max"] = _json_date(dates.max())
        result["null_dates"] = int(dates.isna().sum())
    return result


def historical_status() -> dict:
    datasets = {key: _dataset_status(config) for key, config in DATASETS.items()}
    datasets["inventario"] = _dataset_status(type("InventoryConfig", (), {
        "name": "INVENTARIO_ACTUAL",
        "date_column": "FechaActualizacion",
    })())
    return {
        "available": bool(datasets.get("ventas", {}).get("exists")),
        "data_dir": str(output_path("HISTORICO_VENTAS").parent),
        "datasets": datasets,
    }


def refresh_from_last_update() -> dict:
    if not is_db_configured():
        raise RuntimeError("Base de datos no configurada")

    executor = get_executor()
    connection = executor.test_connection()
    if not connection.get("connected"):
        raise RuntimeError(connection.get("message") or "No hay conexion SQL")

    end = pd.Timestamp(datetime.now()) + pd.Timedelta(seconds=1)
    result = {
        "ok": True,
        "started_at": _json_date(pd.Timestamp(datetime.now())),
        "end": _json_date(end),
        "lookups": {"ok": False},
        "datasets": {},
    }

    download_lookups(executor)
    result["lookups"] = {"ok": True}

    for key, config in DATASETS.items():
        before = _dataset_status(config)
        previous_max = pd.to_datetime(before.get("max"), errors="coerce") if before.get("max") else None
        if previous_max is None or pd.isna(previous_max):
            start = pd.Timestamp(datetime.now().date().replace(month=1, day=1))
        else:
            start = max(previous_max - pd.Timedelta(days=1), pd.Timestamp("2000-01-01"))

        logger.info("Actualizando %s desde %s hasta %s", config.name, start, end)
        new_df = download_dataset(executor, config, start, end)
        merged = merge_local(config, new_df)
        save_df(merged, config.name)
        after = _dataset_status(config)

        result["datasets"][key] = {
            "start": _json_date(start),
            "previous_max": before.get("max"),
            "new_rows": int(len(new_df)),
            "rows_before": before.get("rows", 0),
            "rows_after": after.get("rows", 0),
            "max_after": after.get("max"),
        }

    store = get_historical_store()
    store._cache.clear()
    result["status"] = historical_status()
    result["finished_at"] = _json_date(pd.Timestamp(datetime.now()))
    return result
