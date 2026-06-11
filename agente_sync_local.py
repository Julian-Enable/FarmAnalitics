import os
import subprocess
import sys
import threading
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field


ROOT_DIR = Path(__file__).resolve().parent
DEFAULT_ORIGINS = [
    "https://farm-analitics.vercel.app",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]


def _allowed_origins() -> list[str]:
    raw = os.getenv("LOCAL_SYNC_ALLOWED_ORIGINS", "")
    if not raw.strip():
        return DEFAULT_ORIGINS
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


ALLOWED_ORIGINS = _allowed_origins()
LOCAL_TOKEN = os.getenv("LOCAL_SYNC_TOKEN", "").strip()
LOG_TAIL: deque[str] = deque(maxlen=80)
STATE_LOCK = threading.Lock()
STATE: dict[str, Any] = {
    "running": False,
    "started_at": None,
    "finished_at": None,
    "last_success": None,
    "last_exit_code": None,
    "last_message": "Agente local listo",
    "command": None,
}


class SyncRequest(BaseModel):
    recent_days: int = Field(default=35, ge=1, le=120)
    mode: str = Field(default="incremental", pattern="^(incremental|month)$")
    skip_validate: bool = True
    skip_upload: bool = False


app = FastAPI(title="Farma Analytics Local Sync Agent")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_private_network_header(request: Request, call_next):
    response = await call_next(request)
    origin = request.headers.get("origin")
    if origin in ALLOWED_ORIGINS:
        response.headers["Access-Control-Allow-Private-Network"] = "true"
    return response


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _set_state(**kwargs) -> None:
    with STATE_LOCK:
        STATE.update(kwargs)


def _snapshot() -> dict[str, Any]:
    with STATE_LOCK:
        state = dict(STATE)
    state["ok"] = True
    state["log_tail"] = list(LOG_TAIL)
    state["token_required"] = bool(LOCAL_TOKEN)
    return state


def _check_token(request: Request) -> None:
    if not LOCAL_TOKEN:
        return
    if request.headers.get("x-farma-agent-token") != LOCAL_TOKEN:
        raise HTTPException(status_code=401, detail="Token local invalido")


def _append_log(line: str) -> None:
    clean = line.rstrip()
    if clean:
        LOG_TAIL.append(clean)
        friendly = _friendly_message(clean)
        if friendly:
            _set_state(last_message=friendly)


def _friendly_message(line: str) -> str | None:
    text = line.lower()
    if "iniciando sincronizacion local" in text:
        return "Preparando actualizacion desde SmartPOS..."
    if "sincronizando smartpos incremental" in text:
        return "Buscando la ultima actualizacion local..."
    if "sincronizando smartpos mes actual" in text:
        return "Reprocesando informacion del mes actual..."
    if "sincronizando smartpos desde" in text:
        return "Consultando ventas, compras y devoluciones recientes..."
    if "descargando tablas de apoyo" in text:
        return "Actualizando catalogos de sedes, productos y vendedores..."
    if "descargando inventario actual" in text:
        return "Actualizando inventario actual..."
    if "actualizando historicos recientes" in text:
        return "Actualizando historicos recientes..."
    if "desde ultima fecha local" in text:
        return "Consultando SmartPOS solo desde la ultima actualizacion..."
    if "desde inicio del mes actual" in text:
        return "Consultando SmartPOS desde el primer dia del mes..."
    if "sin historico local" in text:
        return "No hay historico local para una tabla; consultando ventana inicial..."
    if "consultando historico_ventas" in text:
        return "Consultando ventas recientes..."
    if "consultando historico_compras" in text:
        return "Consultando compras recientes..."
    if "consultando historico_notas_credito" in text:
        return "Consultando devoluciones recientes..."
    if "mezclando" in text:
        return "Guardando informacion en la base historica local..."
    if "geocodificando" in text:
        return "Ubicando direcciones de domicilios en el mapa..."
    if "subiendo" in text and "railway" in text:
        return "Subiendo informacion actualizada a Railway..."
    if "subida terminada" in text:
        return "Archivo subido, continuando con la sincronizacion..."
    if "reiniciando servicio en railway" in text:
        return "Reiniciando el backend para publicar los datos..."
    if "sincronizacion completa" in text:
        return "Actualizacion completa. Refrescando datos..."
    if "fallo" in text or "error" in text:
        return "La actualizacion fallo. Revisa el detalle del agente local."
    return None


def _run_sync(req: SyncRequest) -> None:
    command = [
        sys.executable,
        str(ROOT_DIR / "sincronizar_smartpos_railway.py"),
        "--recent-days",
        str(req.recent_days),
        "--mode",
        req.mode,
    ]
    if req.skip_validate:
        command.append("--skip-validate")
    if req.skip_upload:
        command.append("--skip-upload")

    _set_state(
        running=True,
        started_at=_now(),
        finished_at=None,
        last_success=None,
        last_exit_code=None,
        command=" ".join(command),
        last_message="Iniciando sincronizacion local",
    )
    LOG_TAIL.clear()
    _append_log("Iniciando sincronizacion local SmartPOS -> Railway")

    exit_code = 1
    try:
        process = subprocess.Popen(
            command,
            cwd=ROOT_DIR,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        assert process.stdout is not None
        for line in process.stdout:
            _append_log(line)
        exit_code = process.wait()
        success = exit_code == 0
        message = "Sincronizacion completa" if success else f"Sincronizacion fallo con codigo {exit_code}"
        _append_log(message)
        _set_state(last_success=success, last_exit_code=exit_code, last_message=message)
    except Exception as exc:
        _append_log(f"Error ejecutando sincronizacion: {exc}")
        _set_state(last_success=False, last_exit_code=exit_code, last_message=str(exc))
    finally:
        _set_state(running=False, finished_at=_now())


@app.get("/health")
def health():
    return _snapshot()


@app.get("/sync/status")
def sync_status():
    return _snapshot()


@app.post("/sync")
def sync(req: SyncRequest, request: Request):
    _check_token(request)
    if _snapshot()["running"]:
        raise HTTPException(status_code=409, detail="Ya hay una sincronizacion en curso")

    _set_state(
        running=True,
        started_at=_now(),
        finished_at=None,
        last_success=None,
        last_exit_code=None,
        last_message="Preparando sincronizacion local",
    )
    thread = threading.Thread(target=_run_sync, args=(req,), daemon=True)
    thread.start()
    return _snapshot()


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("LOCAL_SYNC_AGENT_PORT", "8765"))
    print("============================================================")
    print(" FARMA ANALYTICS - Agente local de sincronizacion")
    print("============================================================")
    print(f"URL local: http://127.0.0.1:{port}")
    print("Origenes permitidos:")
    for origin in ALLOWED_ORIGINS:
        print(f"  - {origin}")
    print("Deja esta ventana abierta para actualizar desde la web.")
    print("Cierra con Ctrl+C.")
    uvicorn.run(app, host="127.0.0.1", port=port)
