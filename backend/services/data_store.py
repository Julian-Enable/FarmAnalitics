# =============================================================================
# backend/services/data_store.py
# Almacén en memoria de los DataFrames procesados (sesión única)
# =============================================================================
import pandas as pd
import time

# Almacén global de sesiones
# _sessions: { session_id: { "data": { "ventas": df, ... }, "last_accessed": timestamp } }
_sessions = {}

# Tiempo de vida de la sesión (24 horas en segundos)
SESSION_TTL = 24 * 60 * 60

def _init_session(session_id: str):
    if session_id not in _sessions:
        _sessions[session_id] = {
            "data": {
                "ventas": None,
                "compras": None,
                "inventario": None,
            },
            "last_accessed": time.time()
        }
    else:
        _sessions[session_id]["last_accessed"] = time.time()

def _cleanup_old_sessions():
    now = time.time()
    to_delete = []
    for sid, sdata in _sessions.items():
        if now - sdata["last_accessed"] > SESSION_TTL:
            to_delete.append(sid)
    for sid in to_delete:
        del _sessions[sid]

def set_df(session_id: str, key: str, df: pd.DataFrame) -> None:
    _cleanup_old_sessions()
    _init_session(session_id)
    _sessions[session_id]["data"][key] = df

def get_df(session_id: str, key: str) -> pd.DataFrame | None:
    _cleanup_old_sessions()
    if session_id not in _sessions:
        return None
    _sessions[session_id]["last_accessed"] = time.time()
    return _sessions[session_id]["data"].get(key)

def get_status(session_id: str) -> dict:
    if session_id not in _sessions:
        return {"ventas": False, "compras": False, "inventario": False}
    _sessions[session_id]["last_accessed"] = time.time()
    data = _sessions[session_id]["data"]
    return {k: (v is not None and len(v) > 0) for k, v in data.items()}

def clear_all(session_id: str) -> None:
    if session_id in _sessions:
        for k in _sessions[session_id]["data"]:
            _sessions[session_id]["data"][k] = None
