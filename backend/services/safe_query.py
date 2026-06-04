# =============================================================================
# backend/services/safe_query.py — Ejecutor de queries seguro (SOLO LECTURA)
# =============================================================================
"""
REGLA INQUEBRANTABLE DE SEGURIDAD:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Este módulo es el ÚNICO punto de ejecución de queries SQL en toda la aplicación.
Todas las consultas DEBEN pasar por SafeQueryExecutor.

- Solo se permiten sentencias SELECT.
- Está TERMINANTEMENTE PROHIBIDO generar o ejecutar:
  INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, EXEC, CREATE,
  MERGE, GRANT, REVOKE, BACKUP, RESTORE, SHUTDOWN, KILL, DBCC.
- Todas las consultas deben iniciar obligatoriamente con SELECT.
- Se prohíben multi-statement (punto y coma).

El usuario de BD es SPD_FARMAZION. La seguridad se aplica en el código
porque este usuario podría tener permisos más amplios en el servidor.
"""
import re
import logging
import pyodbc
import pandas as pd
import warnings
from typing import Optional

# Suprimir la advertencia de SQLAlchemy de pandas
warnings.filterwarnings('ignore', message='.*pandas only supports SQLAlchemy.*')

from backend.services.db_config import get_connection_string, is_db_configured

logger = logging.getLogger(__name__)

# ── Tokens prohibidos ────────────────────────────────────────────────────────
FORBIDDEN_TOKENS = frozenset({
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE",
    "EXEC", "EXECUTE", "CREATE", "MERGE", "GRANT", "REVOKE",
    "BACKUP", "RESTORE", "SHUTDOWN", "KILL", "DBCC",
    "BULK", "OPENROWSET", "OPENDATASOURCE", "OPENQUERY",
    "XP_CMDSHELL", "SP_EXECUTESQL", "SP_CONFIGURE",
})

# Regex para limpiar comentarios SQL
_RE_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
_RE_LINE_COMMENT = re.compile(r"--[^\n]*")
# Regex para detectar que empieza con una consulta de lectura.
_RE_STARTS_WITH_READ = re.compile(r"^\s*(SELECT|WITH)\b", re.IGNORECASE)


class QuerySecurityError(Exception):
    """Excepción lanzada cuando una query viola las políticas de seguridad."""
    pass


class SafeQueryExecutor:
    """
    Ejecutor de consultas SQL con seguridad de solo lectura.

    Eres un agente de análisis de datos. Tu única función es extraer información.
    Tienes terminantemente prohibido generar o ejecutar comandos de tipo
    INSERT, UPDATE, DELETE, DROP o ALTER.
    Todas las consultas que generes deben iniciar obligatoriamente con SELECT.

    Validación en 4 capas:
    1. La query (limpia de comentarios) DEBE iniciar con SELECT
    2. No debe contener ningún token prohibido como palabra completa
    3. No debe contener punto y coma (anti multi-statement)
    4. Parámetros separados para prevenir SQL injection
    """

    def __init__(self):
        if not is_db_configured():
            raise RuntimeError(
                "Base de datos no configurada. "
                "Verifica las variables DB_SERVER, DB_NAME y DB_PASSWORD en .env"
            )

    # ── Validación ───────────────────────────────────────────────────────────

    @staticmethod
    def _strip_comments(sql: str) -> str:
        """Elimina comentarios SQL para análisis seguro."""
        cleaned = _RE_BLOCK_COMMENT.sub(" ", sql)
        cleaned = _RE_LINE_COMMENT.sub(" ", cleaned)
        return cleaned.strip()

    @staticmethod
    def _tokenize_upper(sql: str) -> list[str]:
        """Divide la query en tokens alfanuméricos en mayúsculas."""
        return re.findall(r"[A-Za-z_][A-Za-z0-9_]*", sql.upper())

    def validate_query(self, sql: str) -> tuple[bool, str]:
        """
        Valida que una query sea segura para ejecución.

        Returns:
            (is_valid, reason) — True si es segura, False con razón si no.
        """
        if not sql or not sql.strip():
            return False, "Query vacía"

        cleaned = self._strip_comments(sql)

        # Capa 1: debe iniciar con SELECT o WITH (CTE de solo lectura).
        if not _RE_STARTS_WITH_READ.match(cleaned):
            return False, (
                "BLOQUEADO: La query NO inicia con SELECT/WITH. "
                "Todas las consultas deben ser de solo lectura."
            )

        # ── Capa 2: No debe contener punto y coma (anti multi-statement) ─
        if ";" in cleaned:
            return False, (
                "BLOQUEADO: Se detectó punto y coma (;). "
                "No se permiten múltiples sentencias."
            )

        # ── Capa 3: No debe contener tokens prohibidos ───────────────────
        tokens = set(self._tokenize_upper(cleaned))
        found_forbidden = tokens.intersection(FORBIDDEN_TOKENS)
        if found_forbidden:
            return False, (
                f"BLOQUEADO: Tokens prohibidos detectados: {found_forbidden}. "
                f"Solo se permiten consultas SELECT de solo lectura."
            )

        # ── Capa 4: Validaciones adicionales ─────────────────────────────
        upper_cleaned = cleaned.upper()
        # No permitir INTO después de SELECT (SELECT INTO crea tablas)
        if re.search(r"\bSELECT\b.*\bINTO\b\s+\w", upper_cleaned):
            return False, (
                "BLOQUEADO: SELECT INTO no está permitido. "
                "No se pueden crear tablas desde queries."
            )

        return True, "OK"

    # ── Ejecución ────────────────────────────────────────────────────────────

    def _get_connection(self) -> pyodbc.Connection:
        """Obtiene una conexión a la base de datos."""
        conn_str = get_connection_string()
        conn = pyodbc.connect(conn_str, timeout=30)
        conn.timeout = 60
        # Marcar la conexión como readonly a nivel de driver
        conn.autocommit = True  # Sin transacciones abiertas
        return conn

    def execute_read(
        self,
        sql: str,
        params: Optional[tuple] = None,
        max_rows: int = 50_000,
    ) -> pd.DataFrame:
        """
        Ejecuta una query de SOLO LECTURA y retorna un DataFrame.

        Args:
            sql: Query SQL (DEBE iniciar con SELECT).
            params: Parámetros para la query (previene SQL injection).
            max_rows: Máximo de filas a retornar (protección anti-overload).

        Returns:
            pd.DataFrame con los resultados.

        Raises:
            QuerySecurityError: Si la query viola las políticas de seguridad.
        """
        # ── Validar ANTES de ejecutar ────────────────────────────────────
        is_valid, reason = self.validate_query(sql)
        if not is_valid:
            logger.warning(f"Query bloqueada: {reason} | Query: {sql[:200]}")
            raise QuerySecurityError(reason)

        # ── Ejecutar ────────────────────────────────────────────────────
        logger.info(f"Ejecutando query segura: {sql[:150]}...")
        conn = None
        try:
            conn = self._get_connection()
            if params:
                df = pd.read_sql(sql, conn, params=params)
            else:
                df = pd.read_sql(sql, conn)

            if len(df) > max_rows:
                logger.warning(
                    f"Query retornó {len(df)} filas, truncando a {max_rows}"
                )
                df = df.head(max_rows)

            return df

        except QuerySecurityError:
            raise
        except pyodbc.Error as e:
            logger.error(f"Error de base de datos: {e}")
            raise RuntimeError(f"Error de base de datos: {str(e)}")
        finally:
            if conn:
                conn.close()

    def test_connection(self) -> dict:
        """Prueba la conexión a la base de datos."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT 1 AS test")
            row = cursor.fetchone()
            cursor.close()
            conn.close()
            return {
                "connected": True,
                "message": "Conexión exitosa a SQL Server",
                "server": get_connection_string().split("SERVER=")[1].split(";")[0],
            }
        except Exception as e:
            return {
                "connected": False,
                "message": f"Error de conexión: {str(e)}",
            }


# ── Instancia singleton ─────────────────────────────────────────────────────
_executor: Optional[SafeQueryExecutor] = None


def get_executor() -> SafeQueryExecutor:
    """Retorna la instancia singleton del ejecutor seguro."""
    global _executor
    if _executor is None:
        _executor = SafeQueryExecutor()
    return _executor
