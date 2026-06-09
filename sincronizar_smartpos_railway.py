import argparse
import logging
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
from dateutil.relativedelta import relativedelta
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent
load_dotenv(ROOT_DIR / ".env")

from backend.services.db_config import is_db_configured
from backend.services.safe_query import get_executor
from descargar_historico import (
    DATASETS,
    download_dataset,
    download_inventory,
    download_lookups,
    merge_local,
    output_path,
    read_local,
    save_df,
    validate_against_sql,
)


DATA_DIR = ROOT_DIR / "data" / "historico"
LOG_DIR = ROOT_DIR / "logs"
RAILWAY_VOLUME = "farmanalitics-volume"
RAILWAY_REMOTE_PATH = "/historico"

LOG_DIR.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "sync_smartpos_railway.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


def _run(cmd: list[str]) -> None:
    logger.info("Ejecutando: %s", " ".join(cmd))
    subprocess.run(cmd, cwd=ROOT_DIR, check=True)


def _incremental_start(config, fallback_days: int) -> tuple[pd.Timestamp, pd.Timestamp | None]:
    path = output_path(config.name)
    local_df = read_local(path, config.date_column)
    if local_df.empty or config.date_column not in local_df.columns:
        fallback = pd.Timestamp(datetime.now() - relativedelta(days=fallback_days)).normalize()
        return fallback, None

    dates = pd.to_datetime(local_df[config.date_column], errors="coerce").dropna()
    if dates.empty:
        fallback = pd.Timestamp(datetime.now() - relativedelta(days=fallback_days)).normalize()
        return fallback, None

    previous_max = dates.max()
    start = max(previous_max - pd.Timedelta(days=1), pd.Timestamp("2000-01-01"))
    return start, previous_max


def sync_local(recent_days: int, validate: bool) -> None:
    if not is_db_configured():
        raise RuntimeError("Base de datos no configurada en .env")

    executor = get_executor()
    connection = executor.test_connection()
    if not connection.get("connected"):
        raise RuntimeError(connection.get("message") or "No hay conexion SQL")

    end = pd.Timestamp(datetime.now()) + pd.Timedelta(seconds=1)
    logger.info("Sincronizando SmartPOS incremental hasta %s", end)

    logger.info("Paso 1/4: descargando tablas de apoyo")
    download_lookups(executor)
    logger.info("Paso 2/4: descargando inventario actual")
    download_inventory(executor)

    total_datasets = len(DATASETS)
    logger.info("Paso 3/4: actualizando historicos recientes (%s datasets)", total_datasets)
    current_dataset = 0
    validation_starts = []
    for config in DATASETS.values():
        current_dataset += 1
        start, previous_max = _incremental_start(config, recent_days)
        validation_starts.append(start)
        if previous_max is not None:
            logger.info(
                "[%s/%s] Consultando %s desde ultima fecha local %s (margen 1 dia): %s -> %s",
                current_dataset,
                total_datasets,
                config.name,
                previous_max,
                start,
                end,
            )
        else:
            logger.info(
                "[%s/%s] Consultando %s sin historico local; fallback ultimos %s dias: %s -> %s",
                current_dataset,
                total_datasets,
                config.name,
                recent_days,
                start,
                end,
            )
        df = download_dataset(executor, config, start, end)
        logger.info("[%s/%s] Mezclando %s con historico local", current_dataset, total_datasets, config.name)
        df = merge_local(config, df)
        save_df(df, config.name)

    if validate:
        start = min(validation_starts) if validation_starts else pd.Timestamp(datetime.now() - relativedelta(days=recent_days)).normalize()
        logger.info("Paso 4/4: validando conteos contra SQL")
        validate_against_sql(executor, start, end)
    else:
        logger.info("Paso 4/4: validacion omitida para acelerar la sincronizacion diaria")


def upload_to_railway() -> None:
    railway = shutil.which("railway")
    if not railway:
        raise RuntimeError("Railway CLI no esta instalado o no esta en PATH")
    if not DATA_DIR.exists():
        raise RuntimeError(f"No existe {DATA_DIR}")
    files = [path for path in sorted(DATA_DIR.iterdir()) if path.is_file()]
    logger.info("Subiendo %s archivos a Railway volume %s", len(files), RAILWAY_VOLUME)
    for index, path in enumerate(files, start=1):
        size_mb = path.stat().st_size / (1024 * 1024)
        logger.info("[%s/%s] Subiendo %s (%.1f MB)", index, len(files), path.name, size_mb)
        _run([
            railway,
            "volume",
            "files",
            "--volume",
            RAILWAY_VOLUME,
            "upload",
            str(path),
            f"{RAILWAY_REMOTE_PATH}/{path.name}",
            "--overwrite",
            "--json",
        ])
        logger.info("[%s/%s] Subida terminada: %s", index, len(files), path.name)
    logger.info("Reiniciando servicio en Railway")
    _run([railway, "restart", "--yes"])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sincroniza SmartPOS local y sube historico a Railway.")
    parser.add_argument("--recent-days", type=int, default=35, help="Dias recientes a reconsultar y mezclar.")
    parser.add_argument("--skip-upload", action="store_true", help="No sube archivos a Railway.")
    parser.add_argument("--skip-validate", action="store_true", help="No valida conteos contra SQL.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    sync_local(args.recent_days, validate=not args.skip_validate)
    if not args.skip_upload:
        upload_to_railway()
    logger.info("Sincronizacion completa")


if __name__ == "__main__":
    main()
