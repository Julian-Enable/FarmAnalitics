# =============================================================================
# backend/services/data_store.py
# Almacén en memoria de los DataFrames procesados (sesión única)
# =============================================================================
import pandas as pd

# Almacén global — se reemplaza en cada upload
_store: dict[str, pd.DataFrame | None] = {
    "ventas": None,
    "compras": None,
    "inventario": None,
}


def set_df(key: str, df: pd.DataFrame) -> None:
    _store[key] = df


def get_df(key: str) -> pd.DataFrame | None:
    return _store.get(key)


def get_status() -> dict:
    return {k: (v is not None and len(v) > 0) for k, v in _store.items()}


def clear_all() -> None:
    for k in _store:
        _store[k] = None
