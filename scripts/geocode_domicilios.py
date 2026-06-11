"""
Geocodifica las direcciones de domicilios a coordenadas y las guarda en la caché
(GEOCODE_CACHE.parquet). Procesa las direcciones más frecuentes primero, así que
con unos pocos miles de geocodificaciones se cubre la mayoría de los domicilios.

Uso:
    python scripts/geocode_domicilios.py --limit 1500
    python scripts/geocode_domicilios.py --limit 500 --retry-failed

Nominatim permite ~1 petición por segundo, por eso se procesa por bloques. Ejecútalo
varias veces (o déjalo correr) hasta que el porcentaje cubierto sea suficiente.
"""
import argparse
import logging
import sys
from pathlib import Path

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT_DIR))

from backend.services.geocoding import normalize_address, geocode_addresses, load_cache  # noqa: E402


def _order_year_first(df: pd.DataFrame) -> tuple[list[str], int]:
    """Direcciones del año en curso primero (por frecuencia), luego el resto."""
    work = df.copy()
    work["Fecha"] = pd.to_datetime(work["Fecha"], errors="coerce")
    work["_n"] = work["Direccion"].map(normalize_address)
    work = work[work["_n"].notna()]
    if work.empty:
        return [], 0
    year = int(work["Fecha"].max().year)
    cur = work[work["Fecha"].dt.year == year]
    cur_order = cur["_n"].value_counts().index.tolist()
    all_order = work["_n"].value_counts().index.tolist()
    seen = set(cur_order)
    return cur_order + [a for a in all_order if a not in seen], year

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

DOMICILIOS_PATH = ROOT_DIR / "data" / "historico" / "HISTORICO_DOMICILIOS.parquet"


def main() -> None:
    parser = argparse.ArgumentParser(description="Geocodifica direcciones de domicilios (frecuentes primero).")
    parser.add_argument("--limit", type=int, default=1500, help="Máximo de direcciones nuevas a geocodificar en esta corrida.")
    parser.add_argument("--retry-failed", action="store_true", help="Reintenta direcciones que fallaron antes.")
    args = parser.parse_args()

    if not DOMICILIOS_PATH.exists():
        raise SystemExit(f"No existe {DOMICILIOS_PATH}. Ejecuta primero la sincronización de domicilios.")

    df = pd.read_parquet(DOMICILIOS_PATH, columns=["Fecha", "Direccion"])
    # Año en curso primero, luego el resto por frecuencia.
    ordered, year = _order_year_first(df)

    cache = load_cache()
    ya = int((cache["ok"] == True).sum()) if not cache.empty else 0  # noqa: E712
    logger.info("Direcciones únicas: %s | prioridad: año %s | ya geocodificadas: %s | objetivo esta corrida: %s",
                f"{len(ordered):,}", year, f"{ya:,}", args.limit)

    result = geocode_addresses(ordered, limit=args.limit, retry_failed=args.retry_failed)
    logger.info("Resultado: %s", result)


if __name__ == "__main__":
    main()
