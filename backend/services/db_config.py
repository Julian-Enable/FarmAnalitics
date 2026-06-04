# =============================================================================
# backend/services/db_config.py — Configuración de conexión a SQL Server
# =============================================================================
"""
Centraliza la configuración de conexión a la base de datos SQL Server.
Las credenciales se leen exclusivamente de variables de entorno (.env).
"""
import os

# ── Credenciales (desde .env) ────────────────────────────────────────────────
DB_SERVER = os.getenv("DB_SERVER", "")
DB_PORT = os.getenv("DB_PORT", "1433")
DB_NAME = os.getenv("DB_NAME", "")
DB_USER = os.getenv("DB_USER", "SPD_FARMAZION")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

# ── Driver ODBC ──────────────────────────────────────────────────────────────
# Intenta detectar el driver instalado. Azure SQL requiere ODBC Driver 17+.
ODBC_DRIVER = os.getenv("DB_ODBC_DRIVER", "")
DB_ENCRYPT = os.getenv("DB_ENCRYPT", "yes")
DB_TRUST_SERVER_CERTIFICATE = os.getenv("DB_TRUST_SERVER_CERTIFICATE", "yes")


def _detect_odbc_driver() -> str:
    """Detecta automáticamente el mejor driver ODBC disponible."""
    if ODBC_DRIVER:
        return ODBC_DRIVER
    try:
        import pyodbc
        drivers = pyodbc.drivers()
        # Preferir la versión más reciente del driver de SQL Server
        for preferred in [
            "ODBC Driver 18 for SQL Server",
            "ODBC Driver 17 for SQL Server",
            "ODBC Driver 13.1 for SQL Server",
            "ODBC Driver 13 for SQL Server",
            "SQL Server Native Client 11.0",
            "SQL Server",
        ]:
            if preferred in drivers:
                return preferred
    except Exception:
        pass
    return "ODBC Driver 17 for SQL Server"


def get_connection_string() -> str:
    """Genera el connection string para pyodbc."""
    driver = _detect_odbc_driver()
    conn_str = (
        f"DRIVER={{{driver}}};"
        f"SERVER={DB_SERVER},{DB_PORT};"
        f"DATABASE={DB_NAME};"
        f"UID={DB_USER};"
        f"PWD={DB_PASSWORD};"
        f"Encrypt={DB_ENCRYPT};"
        f"TrustServerCertificate={DB_TRUST_SERVER_CERTIFICATE};"
        f"Connection Timeout=30;"
    )
    return conn_str


def is_db_configured() -> bool:
    """Retorna True si las credenciales mínimas están configuradas."""
    return bool(DB_SERVER and DB_NAME and DB_PASSWORD)
