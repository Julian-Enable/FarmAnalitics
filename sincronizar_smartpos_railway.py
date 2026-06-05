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
from descargar_historico import DATASETS, download_dataset, download_inventory, download_lookups, merge_local, save_df, validate_against_sql


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


def sync_local(recent_days: int, validate: bool) -> None:
    if not is_db_configured():
        raise RuntimeError("Base de datos no configurada en .env")

    executor = get_executor()
    connection = executor.test_connection()
    if not connection.get("connected"):
        raise RuntimeError(connection.get("message") or "No hay conexion SQL")

    start = pd.Timestamp(datetime.now() - relativedelta(days=recent_days)).normalize()
    end = pd.Timestamp(datetime.now()) + pd.Timedelta(seconds=1)
    logger.info("Sincronizando SmartPOS desde %s hasta %s", start, end)

    download_lookups(executor)
    download_inventory(executor)

    for config in DATASETS.values():
        df = download_dataset(executor, config, start, end)
        df = merge_local(config, df)
        save_df(df, config.name)

    if validate:
        validate_against_sql(executor, start, end)


def upload_to_railway() -> None:
    railway = shutil.which("railway")
    if not railway:
        raise RuntimeError("Railway CLI no esta instalado o no esta en PATH")
    if not DATA_DIR.exists():
        raise RuntimeError(f"No existe {DATA_DIR}")
    for path in sorted(DATA_DIR.iterdir()):
        if not path.is_file():
            continue
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
