"""
Geocodificación de direcciones de domicilios a coordenadas (lat/lon).

Las coordenadas guardadas en SmartPOS (CordX/CordY) no son confiables (vacías en
datos recientes y a menudo apuntan a la sede), así que las direcciones de texto se
geocodifican con Nominatim (OpenStreetMap) y se guardan en una caché parquet para
no volver a consultarlas. La caché vive junto al histórico y se sube a Railway con
el resto de archivos, de modo que producción usa lo ya geocodificado.

La nomenclatura informal de Bogotá no siempre resuelve; las direcciones no
geocodificadas simplemente no se grafican en el mapa (sí aparecen en las tablas).
"""
from __future__ import annotations

import logging
import os
import re
import time
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).resolve().parents[2]
_configured_dir = os.getenv("HISTORICAL_DATA_DIR")
DATA_DIR = Path(_configured_dir) if _configured_dir else ROOT_DIR / "data" / "historico"
CACHE_NAME = "GEOCODE_CACHE"

# Bogotá: viewbox y centro para sesgar el geocodificador.
BOGOTA_VIEWBOX = (-74.25, 4.83, -73.99, 4.45)  # left, top, right, bottom
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

_VIA_REPLACEMENTS = [
    (r"^(CL|CLL|CLLE|CALLE)\b", "Calle"),
    (r"^(CRA|KRA|KR|CR|CARRERA|CARR|CARERA)\b", "Carrera"),
    (r"^(AV CL|AVENIDA CALLE|AC)\b", "Avenida Calle"),
    (r"^(AV KR|AV CRA|AVENIDA CARRERA|AK)\b", "Avenida Carrera"),
    (r"^(AV|AVDA|AVENIDA)\b", "Avenida"),
    (r"^(DG|DIAG|DIAGONAL)\b", "Diagonal"),
    (r"^(TV|TRV|TRANSV|TRANSVERSAL)\b", "Transversal"),
]


def _cache_path() -> Path:
    return DATA_DIR / f"{CACHE_NAME}.parquet"


def normalize_address(raw) -> str | None:
    """Normaliza una dirección a una clave estable para la caché (sin apto/interior)."""
    if raw is None:
        return None
    text = str(raw)
    if not text or text.lower() in {"nan", "none"}:
        return None
    # La parte antes de ';' es la calle; lo de después suele ser apto/interior/torre.
    text = text.split(";")[0]
    text = text.upper().strip()
    text = re.sub(r"\s+", " ", text)
    if len(text) < 4:
        return None
    return text


def address_to_query(norm: str) -> str:
    """Construye la cadena de búsqueda a nivel de esquina (vía principal + vía
    generadora). El número de casa exacto rara vez existe en OpenStreetMap, así que
    se usa la intersección, que resuelve mucho mejor y basta para un mapa por zonas.

    Ej: 'CL 86 69 H 40' -> 'Calle 86 # 69, Bogotá, Colombia'
    """
    via = "Calle"
    rest = norm
    for pattern, replacement in _VIA_REPLACEMENTS:
        new = re.sub(pattern, replacement, norm)
        if new != norm:
            via = replacement
            rest = new[len(replacement):]
            break
    else:
        # Sin prefijo de vía reconocible: usar la dirección tal cual.
        cleaned = re.sub(r"[#\-]", " ", norm)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return f"{cleaned}, Bogotá, Colombia"

    rest = re.sub(r"\bN[°ºO\.]*\b", " ", rest)
    rest = rest.replace("#", " ").replace("-", " ")
    # Tokens numéricos (admiten sufijo de letra: 71C, 12A).
    nums = re.findall(r"\d+[A-Z]?", rest)
    if len(nums) >= 2:
        return f"{via} {nums[0]} # {nums[1]}, Bogotá, Colombia"
    if len(nums) == 1:
        return f"{via} {nums[0]}, Bogotá, Colombia"
    return f"{via}, Bogotá, Colombia"


def load_cache() -> pd.DataFrame:
    path = _cache_path()
    if not path.exists():
        return pd.DataFrame(columns=["direccion_norm", "lat", "lon", "ok"])
    try:
        df = pd.read_parquet(path)
    except Exception as exc:  # pragma: no cover - lectura defensiva
        logger.warning("No se pudo leer la caché de geocodificación: %s", exc)
        return pd.DataFrame(columns=["direccion_norm", "lat", "lon", "ok"])
    for col in ["direccion_norm", "lat", "lon", "ok"]:
        if col not in df.columns:
            df[col] = None
    return df


def save_cache(df: pd.DataFrame) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    df = df.drop_duplicates(subset=["direccion_norm"], keep="last")
    df.to_parquet(_cache_path(), index=False)


def attach_coords(df: pd.DataFrame, address_col: str = "Direccion") -> pd.DataFrame:
    """Agrega columnas lat/lon a un DataFrame de domicilios usando la caché."""
    out = df.copy()
    if address_col not in out.columns:
        out["lat"] = None
        out["lon"] = None
        return out
    out["direccion_norm"] = out[address_col].map(normalize_address)
    cache = load_cache()
    if cache.empty:
        out["lat"] = None
        out["lon"] = None
        return out
    cache_ok = cache[cache["ok"] == True][["direccion_norm", "lat", "lon"]]  # noqa: E712
    return out.merge(cache_ok, on="direccion_norm", how="left")


def _geocode_one(session, query: str):
    params = {
        "q": query,
        "format": "json",
        "limit": 1,
        "countrycodes": "co",
        "viewbox": ",".join(str(v) for v in BOGOTA_VIEWBOX),
        "bounded": 1,
    }
    headers = {"User-Agent": "FarmAnalitics-Domicilios/1.0 (geocoding)"}
    resp = session.get(NOMINATIM_URL, params=params, headers=headers, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    if not data:
        return None
    return float(data[0]["lat"]), float(data[0]["lon"])


def geocode_addresses(addresses: list[str], limit: int = 1500, sleep_seconds: float = 1.1,
                      retry_failed: bool = False) -> dict:
    """Geocodifica direcciones normalizadas aún no cacheadas (orden = como llegan,
    idealmente por frecuencia). Respeta el límite de 1 req/seg de Nominatim."""
    import requests

    cache = load_cache()
    known = set(cache["direccion_norm"].dropna())
    if not retry_failed:
        pending = [a for a in addresses if a and a not in known]
    else:
        failed = set(cache.loc[cache["ok"] != True, "direccion_norm"].dropna())  # noqa: E712
        ok = set(cache.loc[cache["ok"] == True, "direccion_norm"].dropna())  # noqa: E712
        pending = [a for a in addresses if a and a not in ok and (a not in known or a in failed)]

    pending = pending[:limit]
    if not pending:
        return {"intentos": 0, "ok": 0, "fallos": 0, "total_cache": len(cache)}

    session = requests.Session()
    new_rows = []
    ok_count = 0
    for i, addr in enumerate(pending, start=1):
        query = address_to_query(addr)
        lat = lon = None
        ok = False
        try:
            res = _geocode_one(session, query)
            if res:
                lat, lon, ok = res[0], res[1], True
                ok_count += 1
        except Exception as exc:
            logger.warning("Geocode fallo para %r: %s", addr, exc)
        new_rows.append({"direccion_norm": addr, "lat": lat, "lon": lon, "ok": ok})
        if i % 50 == 0:
            logger.info("Geocodificadas %s/%s (ok=%s)", i, len(pending), ok_count)
            save_cache(pd.concat([cache, pd.DataFrame(new_rows)], ignore_index=True))
        time.sleep(sleep_seconds)

    merged = pd.concat([cache, pd.DataFrame(new_rows)], ignore_index=True)
    save_cache(merged)
    return {"intentos": len(pending), "ok": ok_count, "fallos": len(pending) - ok_count, "total_cache": len(merged)}
