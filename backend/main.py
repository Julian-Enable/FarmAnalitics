# =============================================================================
# backend/main.py — FastAPI entry point
# =============================================================================
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.routers.analytics import router

app = FastAPI(
    title="Dashboard Farmacéutico API",
    version="1.0.0",
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


@app.get("/")
def root():
    return {"message": "Dashboard Farmacéutico API", "docs": "/docs"}
