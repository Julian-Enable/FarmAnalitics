# =============================================================================
# backend/main.py — FastAPI entry point
# =============================================================================
import logging
from dotenv import load_dotenv

# Cargar variables de entorno ANTES de importar módulos que las usen
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.routers.analytics import router
from backend.services.db_config import is_db_configured

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Dashboard Farmacéutico API",
    version="2.0.0",
    description="API con conexión directa a SQL Server — Solo lectura",
    docs_url="/docs",
)

# CORS — permite peticiones del frontend (Producción + Local)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://farm-analitics.vercel.app",
        "https://farmanalitics-production.up.railway.app",
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.on_event("startup")
async def startup_event():
    """Verifica la conexión a BD al iniciar."""
    if is_db_configured():
        try:
            from backend.services.db_service import get_db_service
            db = get_db_service()
            if db:
                result = db.test_connection()
                if result["connected"]:
                    logger.info("✅ Conexión a SQL Server exitosa")
                else:
                    logger.warning(f"⚠️ BD configurada pero no conecta: {result['message']}")
        except Exception as e:
            logger.warning(f"⚠️ Error verificando BD: {e}")
    else:
        logger.info("ℹ️ BD no configurada — modo archivos activo")


@app.get("/")
def root():
    return {
        "message": "Dashboard Farmacéutico API",
        "version": "2.0.0",
        "db_configured": is_db_configured(),
        "docs": "/docs",
    }
