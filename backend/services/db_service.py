import pandas as pd
import logging
import json
import numpy as np
from typing import Optional
from datetime import datetime
from dateutil.relativedelta import relativedelta
import time

from backend.services.db_config import is_db_configured
from backend.services.safe_query import get_executor, QuerySecurityError
from backend.services.historical_store import get_historical_store

logger = logging.getLogger(__name__)


class DatabaseService:
    def __init__(self):
        self._executor = get_executor()
        self._historical_store = get_historical_store()
        self._lookups_loaded = False
        self._punto_venta_map = {}
        self._laboratorio_map = {}
        self._nivel_map = {}
        self._proveedor_map = {}

        self._cache = {}
        self._cache_ttl = 300  # 5 minutos

    def _get_cached(self, key, fetch_fn):
        now = time.time()
        if key in self._cache:
            data, timestamp = self._cache[key]
            if now - timestamp < self._cache_ttl:
                return data.copy() if data is not None else None

        df = fetch_fn()
        self._cache[key] = (df, now)
        return df.copy() if df is not None else None

    def _ensure_lookups(self):
        """Carga en cachÃ© los diccionarios de mapeo estÃ¡ticos."""
        if self._lookups_loaded:
            return

        try:
            # Puntos de Venta
            df_pv = self._executor.execute_read("SELECT ID, Nombre FROM PUNTO_VENTA")
            self._punto_venta_map = dict(zip(df_pv["ID"], df_pv["Nombre"]))

            # Laboratorios
            df_lab = self._executor.execute_read("SELECT ID, Nombre FROM LABORATORIOS")
            self._laboratorio_map = dict(zip(df_lab["ID"], df_lab["Nombre"]))

            # Niveles
            df_niv = self._executor.execute_read("SELECT ID, Nombre FROM NIVELES")
            self._nivel_map = dict(zip(df_niv["ID"], df_niv["Nombre"]))

            # Proveedores
            df_prov = self._executor.execute_read("SELECT ID, Nombre FROM PROVEEDORES")
            self._proveedor_map = dict(zip(df_prov["ID"], df_prov["Nombre"]))

            self._lookups_loaded = True
            logger.info("Lookups de BD cargados en cachÃ©")
        except Exception as e:
            logger.error(f"Error cargando lookups: {e}")

    @staticmethod
    def _default_fecha_ini(fecha_ini=None, fecha_fin=None):
        if not fecha_ini and not fecha_fin:
            return (datetime.now() - relativedelta(days=30)).strftime('%Y-%m-%d')
        return fecha_ini

    @staticmethod
    def _records(df: pd.DataFrame) -> list[dict]:
        if df is None or df.empty:
            return []
        return json.loads(df.to_json(orient="records"))

    def _ventas_historicas_filtradas(self, fecha_ini=None, fecha_fin=None, sede="Todas", nivel="Todos", laboratorio="Todos") -> pd.DataFrame:
        fecha_ini = self._default_fecha_ini(fecha_ini, fecha_fin)
        df = self.get_ventas(fecha_ini, fecha_fin, sede=sede)
        if df.empty:
            return df
        if nivel and nivel != "Todos" and "Nivel" in df.columns:
            df = df[df["Nivel"] == nivel]
        if laboratorio and laboratorio != "Todos" and "Laboratorio" in df.columns:
            df = df[df["Laboratorio"] == laboratorio]
        return df.copy()

    def test_connection(self) -> dict:
        return self._executor.test_connection()

    def get_punto_venta(self) -> list[dict]:
        self._ensure_lookups()
        return [{"id": k, "nombre": v} for k, v in self._punto_venta_map.items()]

    def get_ventas(self, fecha_ini=None, fecha_fin=None, sede=None, limit=None) -> pd.DataFrame:
        if self._historical_store.available():
            return self._historical_store.get_ventas(fecha_ini, fecha_fin, sede, limit)

        cache_key = f"ventas_{fecha_ini}_{fecha_fin}_{sede}_{limit}"

        def _fetch():
            self._ensure_lookups()

            where_clauses = ["f.Enabled = 1", "f.Anulada = 'N/A'"]
            params = []

            if fecha_ini:
                where_clauses.append("f.FechaFactura >= ?")
                params.append(fecha_ini)
            if fecha_fin:
                where_clauses.append("f.FechaFactura <= ?")
                params.append(fecha_fin)

            # Siempre aplicar un filtro de fecha para evitar 3M+ registros en memoria si no envÃ­an nada
            if not fecha_ini and not fecha_fin and not limit:
                # Por defecto Ãºltimos 30 dÃ­as
                dias_atras = (datetime.now() - relativedelta(days=30)).strftime('%Y-%m-%d')
                where_clauses.append("f.FechaFactura >= ?")
                params.append(dias_atras)

            if sede and sede != "Todas":
                where_clauses.append("f.ID_PuntoVenta = ?")
                params.append(sede)

            where_str = " AND ".join(where_clauses)
            top_str = f"TOP {limit}" if limit else ""

            sql = f"""
            SELECT {top_str}
                fp.Referencia,
                fp.Descripcion,
                fp.Cantidad AS Cant,
                fp.PrecioVenta AS [Precio Venta],
                fp.Costo,
                r.ID_Laboratorio,
                f.FechaFactura AS Fecha,
                f.ID_PuntoVenta,
                f.Factura,
                f.Creada,
                u.Nombre AS NombreVendedor,
                r.ID_Nivel,
                fp.Cantidad * fp.PrecioVenta AS Ingreso
            FROM FACTURAS f
            INNER JOIN FACTURAS_PRODUCTOS fp ON f.ID = fp.ID_Factura
            LEFT JOIN REFERENCIAS r ON fp.Referencia = r.Referencia
            LEFT JOIN USUARIOS u ON f.Creada = u.Login
            WHERE {where_str}
            """

            df = self._executor.execute_read(sql, params=tuple(params) if params else None)

            if not df.empty:
                df["Punto Venta"] = df["ID_PuntoVenta"].map(self._punto_venta_map).fillna(df["ID_PuntoVenta"])
                df["Laboratorio"] = df["ID_Laboratorio"].map(self._laboratorio_map).fillna("Sin Laboratorio")
                df["Nivel"] = df["ID_Nivel"].map(self._nivel_map).fillna("Sin Nivel")
                df = df.drop(columns=["ID_PuntoVenta", "ID_Laboratorio", "ID_Nivel"])

                # Excluir servicios
                es_servicio = (
                    (df.get("Nivel", pd.Series(dtype=str)).astype(str).str.upper() == "SERVICIOS") | 
                    (df.get("Descripcion", pd.Series(dtype=str)).astype(str).str.contains("DOMICILIO|INYECTOLOGIA|FLETE|TARIFA DE SERVICIO", case=False, na=False))
                )
                df = df[~es_servicio].copy()

            return df

        return self._get_cached(cache_key, _fetch)

    def get_compras(self, fecha_ini=None, fecha_fin=None) -> pd.DataFrame:
        if self._historical_store.available():
            return self._historical_store.get_compras(fecha_ini, fecha_fin)

        cache_key = f"compras_{fecha_ini}_{fecha_fin}"

        def _fetch():
            self._ensure_lookups()

            if fecha_ini or fecha_fin:
                where_clauses = ["c.Enabled = 1"]
                params = []

                if fecha_ini:
                    where_clauses.append("c.Fecha >= ?")
                    params.append(fecha_ini)
                if fecha_fin:
                    where_clauses.append("c.Fecha <= ?")
                    params.append(fecha_fin)

                where_str = " AND ".join(where_clauses)

                sql = f"""
                SELECT
                    c.Fecha AS FECHA,
                    c.ID_Proveedor,
                    cp.Referencia AS REFERENCIA,
                    cp.Descripcion AS DESCRIPCION,
                    r.ID_Laboratorio,
                    cp.PrecioCompra AS PRECIO,
                    cp.Cantidad AS CANT,
                    c.ID_PuntoVenta,
                    cp.Cantidad * cp.PrecioCompra AS [Costo Total]
                FROM COMPRAS c
                INNER JOIN COMPRAS_PRODUCTOS cp ON c.ID = cp.ID_Compra
                LEFT JOIN REFERENCIAS r ON cp.Referencia = r.Referencia
                WHERE {where_str}
                """

                df = self._executor.execute_read(sql, params=tuple(params) if params else None)

                if not df.empty:
                    df["PROVEEDOR"] = df["ID_Proveedor"].map(self._proveedor_map).fillna(df["ID_Proveedor"])
                    df["SEDE"] = df["ID_PuntoVenta"].map(self._punto_venta_map).fillna(df["ID_PuntoVenta"])
                    df["LABORATORIO"] = df["ID_Laboratorio"].map(self._laboratorio_map).fillna("Sin Laboratorio")

                    df = df.drop(columns=["ID_Proveedor", "ID_PuntoVenta", "ID_Laboratorio"])

                return df

            # CARGA O ACTUALIZACIÃ“N INCREMENTAL DEL MAESTRO
            if not hasattr(self, '_master_compras'):
                self._master_compras = None

            where_clauses = ["c.Enabled = 1"]
            params = []

            if self._master_compras is None or self._master_compras.empty:
                dias_atras = (datetime.now() - relativedelta(days=30)).strftime('%Y-%m-%d')
                where_clauses.append("c.Fecha >= ?")
                params.append(dias_atras)
            else:
                max_date = pd.to_datetime(self._master_compras["FECHA"]).max()
                safe_date = (max_date - relativedelta(days=1)).strftime('%Y-%m-%d')
                where_clauses.append("c.Fecha >= ?")
                params.append(safe_date)

            where_str = " AND ".join(where_clauses)

            # Incorporamos c.ID AS CompraID para poder deduplicar exactamente por compra y referencia
            sql = f"""
            SELECT
                c.ID AS CompraID,
                c.Fecha AS FECHA,
                c.ID_Proveedor,
                cp.Referencia AS REFERENCIA,
                cp.Descripcion AS DESCRIPCION,
                r.ID_Laboratorio,
                cp.PrecioCompra AS PRECIO,
                cp.Cantidad AS CANT,
                c.ID_PuntoVenta,
                cp.Cantidad * cp.PrecioCompra AS [Costo Total]
            FROM COMPRAS c
            INNER JOIN COMPRAS_PRODUCTOS cp ON c.ID = cp.ID_Compra
            LEFT JOIN REFERENCIAS r ON cp.Referencia = r.Referencia
            WHERE {where_str}
            """

            new_df = self._executor.execute_read(sql, params=tuple(params) if params else None)

            if not new_df.empty:
                new_df["PROVEEDOR"] = new_df["ID_Proveedor"].map(self._proveedor_map).fillna(new_df["ID_Proveedor"])
                new_df["SEDE"] = new_df["ID_PuntoVenta"].map(self._punto_venta_map).fillna(new_df["ID_PuntoVenta"])
                new_df["LABORATORIO"] = new_df["ID_Laboratorio"].map(self._laboratorio_map).fillna("Sin Laboratorio")
                new_df = new_df.drop(columns=["ID_Proveedor", "ID_PuntoVenta", "ID_Laboratorio"])

            if self._master_compras is None or self._master_compras.empty:
                self._master_compras = new_df
            elif not new_df.empty:
                combined = pd.concat([self._master_compras, new_df])
                # Deduplicar basado en CompraID y Referencia
                self._master_compras = combined.drop_duplicates(subset=['CompraID', 'REFERENCIA'], keep='last')

            # Retornamos sin CompraID para no romper el contrato esperado
            if self._master_compras is not None and not self._master_compras.empty and 'CompraID' in self._master_compras.columns:
                return self._master_compras.drop(columns=['CompraID']).copy()
            return self._master_compras.copy() if self._master_compras is not None else pd.DataFrame()

        return self._get_cached(cache_key, _fetch)

    def get_inventario(self) -> pd.DataFrame:
        if self._historical_store.inventory_available():
            return self._historical_store.get_inventario()

        cache_key = "inventario"

        def _fetch():
            self._ensure_lookups()

            # En el dataset real PdeV llega hasta PdeV19
            pdev_cols = [f"i.PdeV{i}" for i in range(20)]
            pdev_select = ", ".join(pdev_cols)

            sql = f"""
            SELECT
                i.Referencia,
                r.Descripcion1 AS Descripcion,
                r.ID_Laboratorio,
                i.Cantidad AS Total,
                r.PrecioCompra AS [Precio Compra],
                r.PrecioVenta AS [Precio Venta],
                r.StockMinimo AS [Stock Minimo],
                r.StockMaximo AS [Stock Maximo],
                r.ID_Nivel,
                r.Comision,
                r.Utilidad,
                r.Codigo,
                {pdev_select}
            FROM INVENTARIO i
            INNER JOIN REFERENCIAS r ON i.Referencia = r.Referencia
            WHERE r.Enabled = 1
            """

            df = self._executor.execute_read(sql)

            if not df.empty:
                df["Laboratorio"] = df["ID_Laboratorio"].map(self._laboratorio_map).fillna("Sin Laboratorio")
                df["Nivel"] = df["ID_Nivel"].map(self._nivel_map).fillna("Sin Nivel")
                df = df.drop(columns=["ID_Laboratorio", "ID_Nivel"])

                # Renombrar columnas PdeVX a los nombres reales de las sedes
                rename_dict = {}
                for col in df.columns:
                    if col.startswith("PdeV"):
                        sede_nombre = self._punto_venta_map.get(col)
                        if sede_nombre:
                            rename_dict[col] = sede_nombre
                        else:
                            pass

                df = df.rename(columns=rename_dict)
                cols_to_drop = [c for c in df.columns if c.startswith("PdeV")]
                if cols_to_drop:
                    df = df.drop(columns=cols_to_drop)

            return df

        return self._get_cached(cache_key, _fetch)

    def get_notas_credito(self, fecha_ini=None, fecha_fin=None) -> pd.DataFrame:
        if self._historical_store.available():
            return self._historical_store.get_notas_credito(fecha_ini, fecha_fin)

        cache_key = f"notas_credito_{fecha_ini}_{fecha_fin}"

        def _fetch():
            self._ensure_lookups()

            if fecha_ini or fecha_fin:
                where_clauses = ["nc.Enabled = 1"]
                params = []

                if fecha_ini:
                    where_clauses.append("nc.Fecha >= ?")
                    params.append(fecha_ini)
                if fecha_fin:
                    where_clauses.append("nc.Fecha <= ?")
                    params.append(fecha_fin)

                where_str = " AND ".join(where_clauses)

                sql = f"""
                SELECT
                    nc.Fecha,
                    nc.ID AS NotaCredito,
                    nc.ID_PuntoVenta,
                    nc.Total,
                    nc.SubTotal,
                    nc.IVA,
                    nc.Saldo,
                    nc.Observaciones,
                    nc.Creada,
                    u.Nombre AS NombreVendedor
                FROM NOTAS_CREDITO nc
                LEFT JOIN USUARIOS u ON nc.Creada = u.Login
                WHERE {where_str}
                """

                df = self._executor.execute_read(sql, params=tuple(params) if params else None)

                if not df.empty:
                    df['Punto Venta'] = df['ID_PuntoVenta'].map(self._punto_venta_map).fillna(df['ID_PuntoVenta'])
                    df['PuntoVenta'] = df['Punto Venta']
                    if 'Total' in df.columns:
                        df = df.rename(columns={'Total': 'Total Neto'})
                    df = df.drop(columns=["ID_PuntoVenta"])

                return df

            # CARGA O ACTUALIZACIÃ“N INCREMENTAL DEL MAESTRO
            if not hasattr(self, '_master_notas_credito'):
                self._master_notas_credito = None

            where_clauses = ["nc.Enabled = 1"]
            params = []

            if self._master_notas_credito is None or self._master_notas_credito.empty:
                dias_atras = (datetime.now() - relativedelta(days=30)).strftime('%Y-%m-%d')
                where_clauses.append("nc.Fecha >= ?")
                params.append(dias_atras)
            else:
                max_date = pd.to_datetime(self._master_notas_credito["Fecha"]).max()
                safe_date = (max_date - relativedelta(days=1)).strftime('%Y-%m-%d')
                where_clauses.append("nc.Fecha >= ?")
                params.append(safe_date)

            where_str = " AND ".join(where_clauses)

            sql = f"""
            SELECT
                nc.Fecha,
                nc.ID AS NotaCredito,
                nc.ID_PuntoVenta,
                nc.Total,
                nc.SubTotal,
                nc.IVA,
                nc.Saldo,
                nc.Observaciones,
                nc.Creada,
                u.Nombre AS NombreVendedor
            FROM NOTAS_CREDITO nc
            LEFT JOIN USUARIOS u ON nc.Creada = u.Login
            WHERE {where_str}
            """

            new_df = self._executor.execute_read(sql, params=tuple(params) if params else None)

            if not new_df.empty:
                new_df['Punto Venta'] = new_df['ID_PuntoVenta'].map(self._punto_venta_map).fillna(new_df['ID_PuntoVenta'])
                new_df['PuntoVenta'] = new_df['Punto Venta']
                if 'Total' in new_df.columns:
                    new_df = new_df.rename(columns={'Total': 'Total Neto'})
                new_df = new_df.drop(columns=["ID_PuntoVenta"])

            if self._master_notas_credito is None or self._master_notas_credito.empty:
                self._master_notas_credito = new_df
            elif not new_df.empty:
                combined = pd.concat([self._master_notas_credito, new_df])
                self._master_notas_credito = combined.drop_duplicates(subset=['NotaCredito'], keep='last')

            return self._master_notas_credito.copy() if self._master_notas_credito is not None else pd.DataFrame()

        return self._get_cached(cache_key, _fetch)

    # â”€â”€ Resumen Agregado (Optimizado) â”€â”€

    def get_resumen_kpis(self, fecha_ini=None, fecha_fin=None) -> dict:
        if self._historical_store.available():
            if not fecha_ini and not fecha_fin:
                fecha_ini = (datetime.now() - relativedelta(days=30)).strftime('%Y-%m-%d')
            df = self.get_ventas(fecha_ini, fecha_fin)
            if df.empty:
                return {"ingresos": 0, "unidades": 0, "facturas": 0}
            factura_col = "FacturaID" if "FacturaID" in df.columns else "Factura"
            return {
                "ingresos": float(df["Ingreso"].sum()),
                "unidades": float(df["Cant"].sum()),
                "facturas": int(df[factura_col].nunique()) if factura_col in df.columns else int(len(df)),
            }

        self._ensure_lookups()
        where_clauses = ["f.Enabled = 1", "f.Anulada = 'N/A'"]
        params = []
        if fecha_ini:
            where_clauses.append("f.FechaFactura >= ?")
            params.append(fecha_ini)
        if fecha_fin:
            where_clauses.append("f.FechaFactura <= ?")
            params.append(fecha_fin)
        if not fecha_ini and not fecha_fin:
            dias_atras = (datetime.now() - relativedelta(days=30)).strftime('%Y-%m-%d')
            where_clauses.append("f.FechaFactura >= ?")
            params.append(dias_atras)

        where_str = " AND ".join(where_clauses)
        sql = f"""
        SELECT
            ISNULL(SUM(fp.Cantidad * fp.PrecioVenta), 0) AS ingresos,
            ISNULL(SUM(fp.Cantidad), 0) AS unidades,
            COUNT(DISTINCT f.ID) AS facturas
        FROM FACTURAS f
        INNER JOIN FACTURAS_PRODUCTOS fp ON f.ID = fp.ID_Factura
        WHERE {where_str}
        """
        df = self._executor.execute_read(sql, params=tuple(params) if params else None)
        return df.iloc[0].to_dict() if not df.empty else {"ingresos": 0, "unidades": 0, "facturas": 0}

    def get_resumen_costo_utilidad(self, fecha_ini=None, fecha_fin=None) -> dict:
        if self._historical_store.available():
            fecha_ini = self._default_fecha_ini(fecha_ini, fecha_fin)
            ventas = self.get_ventas(fecha_ini, fecha_fin)
            try:
                inventario = self.get_inventario()
            except Exception as e:
                logger.warning("No se pudo consultar inventario para costo historico: %s", e)
                return {"costo_total": None}
            if ventas.empty or inventario.empty or "Precio Compra" not in inventario.columns:
                return {"costo_total": None}
            costos = inventario[["Referencia", "Precio Compra"]].drop_duplicates("Referencia")
            df = ventas.merge(costos, on="Referencia", how="left")
            df["Precio Compra"] = pd.to_numeric(df["Precio Compra"], errors="coerce")
            if df["Precio Compra"].notna().sum() == 0:
                return {"costo_total": None}
            df["Precio Compra"] = df["Precio Compra"].fillna(0)
            return {"costo_total": float((df["Cant"] * df["Precio Compra"]).sum())}

        where_clauses = ["f.Enabled = 1", "f.Anulada = 'N/A'"]
        params = []
        if fecha_ini:
            where_clauses.append("f.FechaFactura >= ?")
            params.append(fecha_ini)
        if fecha_fin:
            where_clauses.append("f.FechaFactura <= ?")
            params.append(fecha_fin)
        if not fecha_ini and not fecha_fin:
            dias_atras = (datetime.now() - relativedelta(days=30)).strftime('%Y-%m-%d')
            where_clauses.append("f.FechaFactura >= ?")
            params.append(dias_atras)

        where_str = " AND ".join(where_clauses)
        sql = f"""
        SELECT
            ISNULL(SUM(fp.Cantidad * r.PrecioCompra), 0) AS costo_total
        FROM FACTURAS f
        INNER JOIN FACTURAS_PRODUCTOS fp ON f.ID = fp.ID_Factura
        INNER JOIN REFERENCIAS r ON fp.Referencia = r.Referencia
        WHERE {where_str} AND r.Enabled = 1
        """
        df = self._executor.execute_read(sql, params=tuple(params) if params else None)
        return df.iloc[0].to_dict() if not df.empty else {"costo_total": 0}

    def get_resumen_tendencia(self, fecha_ini=None, fecha_fin=None) -> list:
        if self._historical_store.available():
            df = self._ventas_historicas_filtradas(fecha_ini, fecha_fin)
            if df.empty:
                return []
            out = (
                df.assign(fecha=pd.to_datetime(df["Fecha"], errors="coerce").dt.date)
                .dropna(subset=["fecha"])
                .groupby("fecha", as_index=False)["Ingreso"]
                .sum()
                .sort_values("fecha")
                .rename(columns={"Ingreso": "ingreso"})
            )
            out["fecha"] = out["fecha"].astype(str)
            return self._records(out)

        where_clauses = ["f.Enabled = 1", "f.Anulada = 'N/A'"]
        params = []
        if fecha_ini:
            where_clauses.append("f.FechaFactura >= ?")
            params.append(fecha_ini)
        if fecha_fin:
            where_clauses.append("f.FechaFactura <= ?")
            params.append(fecha_fin)
        if not fecha_ini and not fecha_fin:
            dias_atras = (datetime.now() - relativedelta(days=30)).strftime('%Y-%m-%d')
            where_clauses.append("f.FechaFactura >= ?")
            params.append(dias_atras)

        where_str = " AND ".join(where_clauses)
        sql = f"""
        SELECT
            CAST(f.FechaFactura AS DATE) AS fecha,
            ISNULL(SUM(fp.Cantidad * fp.PrecioVenta), 0) AS ingreso
        FROM FACTURAS f
        INNER JOIN FACTURAS_PRODUCTOS fp ON f.ID = fp.ID_Factura
        WHERE {where_str}
        GROUP BY CAST(f.FechaFactura AS DATE)
        ORDER BY fecha
        """
        df = self._executor.execute_read(sql, params=tuple(params) if params else None)
        if df.empty: return []
        df['fecha'] = df['fecha'].astype(str)
        return df.to_dict(orient="records")

    def get_resumen_ranking(self, tipo: str, fecha_ini=None, fecha_fin=None, limit=5) -> list:
        if self._historical_store.available():
            df = self._ventas_historicas_filtradas(fecha_ini, fecha_fin)
            if df.empty:
                return []

            if tipo == "producto":
                group_cols = ["Descripcion"]
                name_col = "nombre"
                source_col = "Descripcion"
            elif tipo == "sede":
                group_cols = ["Punto Venta"] if "Punto Venta" in df.columns else ["ID_PuntoVenta"]
                name_col = "sede"
                source_col = group_cols[0]
            elif tipo == "laboratorio":
                group_cols = ["Laboratorio"] if "Laboratorio" in df.columns else ["ID_Laboratorio"]
                name_col = "laboratorio"
                source_col = group_cols[0]
            elif tipo == "vendedor":
                group_cols = ["NombreVendedor"] if "NombreVendedor" in df.columns else ["Creada"]
                name_col = "vendedor"
                source_col = group_cols[0]
            else:
                return []

            out = (
                df.groupby(group_cols, as_index=False)["Ingreso"]
                .sum()
                .nlargest(int(limit), "Ingreso")
                .rename(columns={"Ingreso": "ingreso", source_col: name_col})
            )
            return self._records(out)

        self._ensure_lookups()
        where_clauses = ["f.Enabled = 1", "f.Anulada = 'N/A'"]
        params = []
        if fecha_ini:
            where_clauses.append("f.FechaFactura >= ?")
            params.append(fecha_ini)
        if fecha_fin:
            where_clauses.append("f.FechaFactura <= ?")
            params.append(fecha_fin)
        if not fecha_ini and not fecha_fin:
            dias_atras = (datetime.now() - relativedelta(days=30)).strftime('%Y-%m-%d')
            where_clauses.append("f.FechaFactura >= ?")
            params.append(dias_atras)

        where_str = " AND ".join(where_clauses)

        select_group = ""
        join_clause = ""

        if tipo == "producto":
            select_group = "fp.Descripcion AS nombre"
            group_col = "fp.Descripcion"
        elif tipo == "sede":
            select_group = "f.ID_PuntoVenta AS id_sede"
            group_col = "f.ID_PuntoVenta"
        elif tipo == "laboratorio":
            select_group = "r.ID_Laboratorio AS id_lab"
            join_clause = "LEFT JOIN REFERENCIAS r ON fp.Referencia = r.Referencia"
            group_col = "r.ID_Laboratorio"
        elif tipo == "vendedor":
            return []

        sql = f"""
        SELECT TOP {limit}
            {select_group},
            ISNULL(SUM(fp.Cantidad * fp.PrecioVenta), 0) AS ingreso
        FROM FACTURAS f
        INNER JOIN FACTURAS_PRODUCTOS fp ON f.ID = fp.ID_Factura
        {join_clause}
        WHERE {where_str}
        GROUP BY {group_col}
        ORDER BY ingreso DESC
        """

        df = self._executor.execute_read(sql, params=tuple(params) if params else None)
        if df.empty: return []

        if tipo == "sede":
            df["sede"] = df["id_sede"].map(self._punto_venta_map).fillna(df["id_sede"])
            df = df.drop(columns=["id_sede"])
        elif tipo == "laboratorio":
            df["laboratorio"] = df["id_lab"].map(self._laboratorio_map).fillna("Sin Laboratorio")
            df = df.drop(columns=["id_lab"])

        return df.to_dict(orient="records")

    def get_resumen_alertas_df(self, fecha_ini=None, fecha_fin=None) -> pd.DataFrame:
        fecha_ini = self._default_fecha_ini(fecha_ini, fecha_fin)
        dias_atras_rotacion = fecha_ini or (datetime.now() - relativedelta(days=30)).strftime('%Y-%m-%d')
        try:
            inv = self.get_inventario()
        except Exception as e:
            logger.warning("No se pudo consultar inventario para alertas: %s", e)
            return pd.DataFrame(columns=["Referencia", "Total", "cant_vend", "ultima_venta", "PrecioCompra"])

        if inv is None or inv.empty:
            return pd.DataFrame(columns=["Referencia", "Total", "cant_vend", "ultima_venta", "PrecioCompra"])

        base_cols = ["Referencia", "Total", "Precio Compra"]
        base = inv[[c for c in base_cols if c in inv.columns]].copy()
        base = base.rename(columns={"Precio Compra": "PrecioCompra"})

        if self._historical_store.available():
            ventas = self.get_ventas(fecha_ini=dias_atras_rotacion, fecha_fin=fecha_fin)
            if ventas.empty:
                base["cant_vend"] = 0
                base["ultima_venta"] = pd.NaT
                return base
            rotacion = ventas.groupby("Referencia", as_index=False).agg(
                cant_vend=("Cant", "sum"),
                ultima_venta=("Fecha", "max"),
            )
            out = base.merge(rotacion, on="Referencia", how="left")
            out["cant_vend"] = out["cant_vend"].fillna(0)
            return out

        sql = """
        SELECT
            fp.Referencia,
            SUM(fp.Cantidad) AS cant_vend,
            MAX(f.FechaFactura) AS ultima_venta
        FROM FACTURAS f
        INNER JOIN FACTURAS_PRODUCTOS fp ON f.ID = fp.ID_Factura
        WHERE f.Enabled = 1 AND f.Anulada = 'N/A' AND f.FechaFactura >= ?
        GROUP BY fp.Referencia
        """
        rotacion = self._executor.execute_read(sql, params=(dias_atras_rotacion,))

        if rotacion is None or rotacion.empty:
            base["cant_vend"] = 0
            base["ultima_venta"] = pd.NaT
            return base

        out = base.merge(rotacion, on="Referencia", how="left")
        out["cant_vend"] = out["cant_vend"].fillna(0)
        return out

    # â”€â”€ AnÃ¡lisis Avanzado de Ventas â”€â”€
    def get_analisis_ventas_sql(self, fecha_ini=None, fecha_fin=None, sede="Todas", nivel="Todos", laboratorio="Todos") -> dict:
        if self._historical_store.available():
            df = self._ventas_historicas_filtradas(fecha_ini, fecha_fin, sede, nivel, laboratorio)
            full_df = self.get_ventas()

            sedes_opts = sorted(full_df.get("Punto Venta", pd.Series(dtype=str)).dropna().astype(str).unique().tolist())
            niveles_opts = sorted(full_df.get("Nivel", pd.Series(dtype=str)).dropna().astype(str).unique().tolist())
            labs_opts = sorted(full_df.get("Laboratorio", pd.Series(dtype=str)).dropna().astype(str).unique().tolist())

            empty_response = {
                "registros": 0,
                "ingreso_total": 0,
                "promedio_diario": 0,
                "dias_periodo": 1,
                "top_productos": [],
                "top_labs": [],
                "por_categoria": [],
                "vendedores": [],
                "tendencia_mensual": [],
                "detalle_productos": [],
                "filtros": {"sedes": sedes_opts, "niveles": niveles_opts, "laboratorios": labs_opts},
            }
            if df.empty:
                return empty_response

            df = df.copy()
            df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce")
            factura_col = "FacturaID" if "FacturaID" in df.columns else "Factura"
            ing_total = float(df["Ingreso"].sum())
            min_fecha = df["Fecha"].min()
            max_fecha = df["Fecha"].max()
            dias_periodo = max((max_fecha - min_fecha).days + 1, 1) if pd.notna(min_fecha) and pd.notna(max_fecha) else 1
            promedio_diario = round(ing_total / dias_periodo, 0)

            df_prod = (
                df.groupby(["Referencia"], as_index=False)
                .agg(Descripcion=("Descripcion", "last"), Cant=("Cant", "sum"))
                .nlargest(15, "Cant")
                .sort_values("Cant", ascending=True)
            )
            df_prod["nombre"] = df_prod["Descripcion"].fillna("").astype(str).str[:35]

            df_labs = (
                df.groupby("Laboratorio", as_index=False)["Ingreso"]
                .sum()
                .nlargest(10, "Ingreso")
                .sort_values("Ingreso", ascending=True)
            ) if "Laboratorio" in df.columns else pd.DataFrame()
            if not df_labs.empty:
                df_labs["lab"] = df_labs["Laboratorio"].fillna("Sin Laboratorio").astype(str).str[:28]

            df_cat = (
                df.groupby("Nivel", as_index=False)["Ingreso"]
                .sum()
                .sort_values("Ingreso", ascending=True)
            ) if "Nivel" in df.columns else pd.DataFrame()

            vendedor_col = "NombreVendedor" if "NombreVendedor" in df.columns else "Creada"
            df_vend = (
                df.groupby(vendedor_col, as_index=False)
                .agg(unidades=("Cant", "sum"), ingresos=("Ingreso", "sum"), facturas=(factura_col, "nunique"))
                .rename(columns={vendedor_col: "vendedor"})
                .sort_values("ingresos", ascending=False)
            ) if vendedor_col in df.columns and factura_col in df.columns else pd.DataFrame()

            tendencia_mensual = []
            monthly = (
                df.dropna(subset=["Fecha"])
                .set_index("Fecha")
                .resample("ME")["Ingreso"]
                .sum()
                .reset_index()
            )
            for _, row in monthly.iterrows():
                tendencia_mensual.append({"mes": row["Fecha"].strftime("%b %Y"), "ingreso": round(float(row["Ingreso"]), 0)})

            df_det = (
                df.groupby("Referencia", as_index=False)
                .agg(
                    Descripcion=("Descripcion", "last"),
                    Laboratorio=("Laboratorio", "last") if "Laboratorio" in df.columns else ("Referencia", "last"),
                    unidades=("Cant", "sum"),
                    ingreso=("Ingreso", "sum"),
                )
                .sort_values("ingreso", ascending=False)
            )
            if "Laboratorio" not in df.columns and "Laboratorio" not in df_det.columns:
                df_det["Laboratorio"] = "Sin Laboratorio"

            return {
                "registros": int(len(df)),
                "ingreso_total": round(ing_total, 0),
                "promedio_diario": promedio_diario,
                "dias_periodo": dias_periodo,
                "top_productos": self._records(df_prod),
                "top_labs": self._records(df_labs),
                "por_categoria": self._records(df_cat),
                "vendedores": self._records(df_vend),
                "tendencia_mensual": tendencia_mensual,
                "detalle_productos": self._records(df_det),
                "filtros": {"sedes": sedes_opts, "niveles": niveles_opts, "laboratorios": labs_opts},
            }

        self._ensure_lookups()

        where_clauses = ["f.Enabled = 1", "f.Anulada = 'N/A'"]
        params = []

        if fecha_ini:
            where_clauses.append("f.FechaFactura >= ?")
            params.append(fecha_ini)
        if fecha_fin:
            where_clauses.append("f.FechaFactura <= ?")
            params.append(fecha_fin)

        if not fecha_ini and not fecha_fin:
            dias_atras = (datetime.now() - relativedelta(days=30)).strftime('%Y-%m-%d')
            where_clauses.append("f.FechaFactura >= ?")
            params.append(dias_atras)

        if sede and sede != "Todas":
            where_clauses.append("pv.Nombre = ?")
            params.append(sede)

        if nivel and nivel != "Todos":
            where_clauses.append("niv.Nombre = ?")
            params.append(nivel)

        if laboratorio and laboratorio != "Todos":
            where_clauses.append("lab.Nombre = ?")
            params.append(laboratorio)

        # Excluir servicios
        where_clauses.append("(niv.Nombre IS NULL OR UPPER(niv.Nombre) != 'SERVICIOS')")
        where_clauses.append("(fp.Descripcion NOT LIKE '%DOMICILIO%' AND fp.Descripcion NOT LIKE '%INYECTOLOGIA%' AND fp.Descripcion NOT LIKE '%FLETE%' AND fp.Descripcion NOT LIKE '%TARIFA DE SERVICIO%')")

        where_str = " AND ".join(where_clauses)

        # Base FROM and JOINs
        base_from = """
        FROM FACTURAS_PRODUCTOS fp
        INNER JOIN FACTURAS f ON fp.ID_Factura = f.ID
        LEFT JOIN REFERENCIAS r ON fp.Referencia = r.Referencia
        LEFT JOIN PUNTO_VENTA pv ON f.ID_PuntoVenta = pv.ID
        LEFT JOIN NIVELES niv ON r.ID_Nivel = niv.ID
        LEFT JOIN LABORATORIOS lab ON r.ID_Laboratorio = lab.ID
        LEFT JOIN USUARIOS u ON f.Creada = u.Login
        """

        # 1. KPIs
        sql_kpis = f"""
        SELECT
            COUNT(DISTINCT f.ID) AS facturas,
            SUM(fp.Cantidad * fp.PrecioVenta) AS ingreso_total,
            MIN(f.FechaFactura) as min_fecha,
            MAX(f.FechaFactura) as max_fecha,
            COUNT(*) AS registros
        {base_from}
        WHERE {where_str}
        """
        df_kpis = self._executor.execute_read(sql_kpis, params)
        kpis = df_kpis.iloc[0].to_dict() if not df_kpis.empty else {"facturas": 0, "ingreso_total": 0, "min_fecha": None, "max_fecha": None, "registros": 0}
        ing_total = float(kpis.get("ingreso_total") or 0)

        dias_periodo = 1
        if kpis.get("min_fecha") and kpis.get("max_fecha") and pd.notna(kpis["min_fecha"]) and pd.notna(kpis["max_fecha"]):
            dias_periodo = max((kpis["max_fecha"] - kpis["min_fecha"]).days + 1, 1)
        promedio_diario = round(ing_total / dias_periodo, 0)

        # 2. Top Productos (Unidades)
        sql_top_prod = f"""
        SELECT TOP 15
            fp.Referencia,
            MAX(fp.Descripcion) AS Descripcion,
            SUM(fp.Cantidad) AS Cant
        {base_from}
        WHERE {where_str}
        GROUP BY fp.Referencia
        ORDER BY Cant DESC
        """
        df_prod = self._executor.execute_read(sql_top_prod, params)
        df_prod["nombre"] = df_prod["Descripcion"].str[:35] if not df_prod.empty else []
        top_productos = json.loads(df_prod.sort_values("Cant", ascending=True).to_json(orient="records")) if not df_prod.empty else []

        # 3. Top Laboratorios (Ingresos)
        sql_top_labs = f"""
        SELECT TOP 10
            ISNULL(lab.Nombre, 'Sin Laboratorio') AS Laboratorio,
            SUM(fp.Cantidad * fp.PrecioVenta) AS Ingreso
        {base_from}
        WHERE {where_str}
        GROUP BY lab.Nombre
        ORDER BY Ingreso DESC
        """
        df_labs = self._executor.execute_read(sql_top_labs, params)
        df_labs["lab"] = df_labs["Laboratorio"].str[:28] if not df_labs.empty else []
        top_labs = json.loads(df_labs.sort_values("Ingreso", ascending=True).to_json(orient="records")) if not df_labs.empty else []

        # 4. Por Categoria (Nivel)
        sql_cat = f"""
        SELECT
            ISNULL(niv.Nombre, 'Sin Nivel') AS Nivel,
            SUM(fp.Cantidad * fp.PrecioVenta) AS Ingreso
        {base_from}
        WHERE {where_str}
        GROUP BY niv.Nombre
        ORDER BY Ingreso DESC
        """
        df_cat = self._executor.execute_read(sql_cat, params)
        por_categoria = json.loads(df_cat.sort_values("Ingreso", ascending=True).to_json(orient="records")) if not df_cat.empty else []

        # 5. Vendedores
        sql_vend = f"""
        SELECT
            COALESCE(NULLIF(LTRIM(RTRIM(u.Nombre)), ''), f.Creada) AS vendedor,
            SUM(fp.Cantidad) AS unidades,
            SUM(fp.Cantidad * fp.PrecioVenta) AS ingresos,
            COUNT(DISTINCT f.ID) AS facturas
        {base_from}
        WHERE {where_str}
        GROUP BY COALESCE(NULLIF(LTRIM(RTRIM(u.Nombre)), ''), f.Creada)
        ORDER BY ingresos DESC
        """
        df_vend = self._executor.execute_read(sql_vend, params)
        vendedores = json.loads(df_vend.to_json(orient="records")) if not df_vend.empty else []

        # 6. Tendencia Mensual
        sql_tend = f"""
        SELECT
            YEAR(f.FechaFactura) AS yyyy,
            MONTH(f.FechaFactura) AS mm,
            SUM(fp.Cantidad * fp.PrecioVenta) AS ingreso
        {base_from}
        WHERE {where_str}
        GROUP BY YEAR(f.FechaFactura), MONTH(f.FechaFactura)
        ORDER BY yyyy ASC, mm ASC
        """
        df_tend = self._executor.execute_read(sql_tend, params)
        tendencia_mensual = []
        if not df_tend.empty:
            for _, r in df_tend.iterrows():
                try:
                    mes_nombre = datetime(int(r["yyyy"]), int(r["mm"]), 1).strftime("%b %Y")
                    tendencia_mensual.append({"mes": mes_nombre, "ingreso": round(r["ingreso"], 0)})
                except: pass

        # 7. Detalle Tabla
        sql_det = f"""
        SELECT
            fp.Referencia,
            MAX(fp.Descripcion) AS Descripcion,
            ISNULL(MAX(lab.Nombre), 'Sin Laboratorio') AS Laboratorio,
            SUM(fp.Cantidad) AS unidades,
            SUM(fp.Cantidad * fp.PrecioVenta) AS ingreso
        {base_from}
        WHERE {where_str}
        GROUP BY fp.Referencia
        ORDER BY ingreso DESC
        """
        df_det = self._executor.execute_read(sql_det, params)
        detalle_tabla = json.loads(df_det.to_json(orient="records")) if not df_det.empty else []

        # 8. Filtros Disponibles (Opciones Ãºnicas en toda la BD)
        sedes_opts = sorted(list(self._punto_venta_map.values()))
        niveles_opts = sorted(list(self._nivel_map.values()))
        labs_opts = sorted(list(self._laboratorio_map.values()))

        return {
            "registros": int(kpis.get("registros") or 0),
            "ingreso_total": round(ing_total, 0),
            "promedio_diario": promedio_diario,
            "dias_periodo": dias_periodo,
            "top_productos": top_productos,
            "top_labs": top_labs,
            "por_categoria": por_categoria,
            "vendedores": vendedores,
            "tendencia_mensual": tendencia_mensual,
            "detalle_productos": detalle_tabla,
            "filtros": {
                "sedes": sedes_opts,
                "niveles": niveles_opts,
                "laboratorios": labs_opts,
            },
        }

    def get_analisis_rentabilidad_sql(self, fecha_ini=None, fecha_fin=None) -> dict:
        if self._historical_store.available():
            ventas = self._ventas_historicas_filtradas(fecha_ini, fecha_fin)
            if ventas.empty:
                return None
            try:
                inventario = self.get_inventario()
            except Exception as e:
                logger.warning("No se pudo consultar inventario para rentabilidad: %s", e)
                return None
            if inventario.empty or "Precio Compra" not in inventario.columns:
                return None

            ventas = ventas.copy()
            ventas["Fecha"] = pd.to_datetime(ventas["Fecha"], errors="coerce")
            df_base = (
                ventas.groupby("Referencia", as_index=False)
                .agg(
                    nombre=("Descripcion", "last"),
                    cant_vend=("Cant", "sum"),
                    ingreso_total=("Ingreso", "sum"),
                    lab=("Laboratorio", "last") if "Laboratorio" in ventas.columns else ("Referencia", "last"),
                )
            )
            df_base = df_base[df_base["cant_vend"] > 0]
            if df_base.empty:
                return None

            costos = (
                inventario[["Referencia", "Precio Compra"]]
                .copy()
                .rename(columns={"Precio Compra": "precio_compra"})
                .drop_duplicates("Referencia")
            )
            costos["precio_compra"] = pd.to_numeric(costos["precio_compra"], errors="coerce").fillna(0)
            df_base = df_base.merge(costos, on="Referencia", how="left")
            df_base["precio_compra"] = df_base["precio_compra"].fillna(0)
            df_base["precio_venta"] = df_base["ingreso_total"] / df_base["cant_vend"]
            df_base["utilidad_unit"] = df_base["precio_venta"] - df_base["precio_compra"]
            df_base["utilidad_total"] = df_base["utilidad_unit"] * df_base["cant_vend"]
            df_base["margen_pct"] = np.where(
                df_base["precio_venta"] > 0,
                (df_base["utilidad_unit"] / df_base["precio_venta"]) * 100,
                0,
            ).round(2)

            min_fecha = ventas["Fecha"].min()
            max_fecha = ventas["Fecha"].max()
            dias = max((max_fecha - min_fecha).days + 1, 1) if pd.notna(min_fecha) and pd.notna(max_fecha) else 1
            df_base["rotacion_diaria"] = df_base["cant_vend"] / dias

            utilidad_total = float(df_base["utilidad_total"].sum())
            ingreso_total = float(df_base["ingreso_total"].sum())
            margen_global = round((utilidad_total / ingreso_total * 100), 2) if ingreso_total > 0 else 0
            alta_rotacion_min = df_base["cant_vend"].quantile(0.8) if len(df_base) > 0 else 0
            if alta_rotacion_min < 5:
                alta_rotacion_min = 5

            bajo_margen_df = df_base[(df_base["margen_pct"] < 5) & (df_base["cant_vend"] >= alta_rotacion_min)]
            bajo_margen = self._records(bajo_margen_df.sort_values("margen_pct", ascending=True))
            top_rentables = self._records(df_base.nlargest(15, "utilidad_total"))

            por_lab_df = (
                df_base.groupby("lab", as_index=False)["utilidad_total"]
                .sum()
                .nlargest(15, "utilidad_total")
            )

            matriz_df = df_base.sort_values("ingreso_total", ascending=False).copy()
            matriz_df["cum_ing"] = matriz_df["ingreso_total"].cumsum()
            total_ing = matriz_df["ingreso_total"].sum()
            matriz_df["pct_ing"] = matriz_df["cum_ing"] / total_ing if total_ing > 0 else 0
            matriz_df["abc_ventas"] = np.where(matriz_df["pct_ing"] <= 0.8, "A", np.where(matriz_df["pct_ing"] <= 0.95, "B", "C"))

            matriz_df = matriz_df.sort_values("utilidad_total", ascending=False)
            matriz_df["cum_uti"] = matriz_df["utilidad_total"].cumsum()
            total_uti = matriz_df["utilidad_total"].sum()
            if total_uti > 0:
                matriz_df["pct_uti"] = matriz_df["cum_uti"] / total_uti
                matriz_df["abc_margen"] = np.where(matriz_df["pct_uti"] <= 0.8, "A", np.where(matriz_df["pct_uti"] <= 0.95, "B", "C"))
            else:
                matriz_df["abc_margen"] = "C"
            matriz_df["matriz_abc"] = matriz_df["abc_ventas"] + "-" + matriz_df["abc_margen"]

            return {
                "kpis": {
                    "utilidad_total": round(utilidad_total, 0),
                    "ingreso_total": round(ingreso_total, 0),
                    "margen_global": margen_global,
                    "productos": int(len(df_base)),
                    "bajo_margen_count": int(len(bajo_margen_df)),
                    "bajo_margen_umbral_pct": 5,
                    "alta_rotacion_min_unidades": round(float(alta_rotacion_min), 0),
                    "dias_periodo": dias,
                },
                "top_rentables": top_rentables,
                "bajo_margen": bajo_margen,
                "matriz_abc": self._records(matriz_df),
                "por_laboratorio": self._records(por_lab_df),
            }

        self._ensure_lookups()

        where_clauses = ["f.Enabled = 1", "f.Anulada = 'N/A'"]
        params = []

        if fecha_ini:
            where_clauses.append("f.FechaFactura >= ?")
            params.append(fecha_ini)
        if fecha_fin:
            where_clauses.append("f.FechaFactura <= ?")
            params.append(fecha_fin)
        if not fecha_ini and not fecha_fin:
            dias_atras = (datetime.now() - relativedelta(days=30)).strftime('%Y-%m-%d')
            where_clauses.append("f.FechaFactura >= ?")
            params.append(dias_atras)

        where_str = " AND ".join(where_clauses)

        base_from = """
        FROM FACTURAS_PRODUCTOS fp
        INNER JOIN FACTURAS f ON fp.ID_Factura = f.ID
        LEFT JOIN REFERENCIAS r ON fp.Referencia = r.Referencia
        LEFT JOIN LABORATORIOS lab ON r.ID_Laboratorio = lab.ID
        """

        # 1. AgrupaciÃ³n base por Referencia (para Matriz ABC y Bajo Margen)
        sql_base = f"""
        SELECT
            fp.Referencia,
            MAX(fp.Descripcion) AS nombre,
            SUM(fp.Cantidad) AS cant_vend,
            SUM(fp.Cantidad * fp.PrecioVenta) AS ingreso_total,
            SUM(fp.Cantidad * (fp.PrecioVenta - ISNULL(r.PrecioCompra, 0))) AS utilidad_total,
            MAX(ISNULL(r.PrecioCompra, 0)) as precio_compra,
            ISNULL(MAX(lab.Nombre), 'Sin Laboratorio') as lab
        {base_from}
        WHERE {where_str}
        GROUP BY fp.Referencia
        HAVING SUM(fp.Cantidad) > 0
        """
        df_base = self._executor.execute_read(sql_base, params)

        if df_base.empty:
            return None

        # Calcular campos adicionales en Pandas (es muy rÃ¡pido una vez agrupado)
        df_base["precio_venta"] = df_base["ingreso_total"] / df_base["cant_vend"]
        df_base["utilidad_unit"] = df_base["precio_venta"] - df_base["precio_compra"]
        df_base["margen_pct"] = np.where(df_base["precio_venta"] > 0,
                                        (df_base["utilidad_unit"] / df_base["precio_venta"]) * 100,
                                        0).round(2)

        # DÃ­as periodo
        sql_fechas = f"SELECT MIN(FechaFactura) as min_fecha, MAX(FechaFactura) as max_fecha FROM FACTURAS f WHERE {where_str}"
        df_f = self._executor.execute_read(sql_fechas, params)
        dias = 1
        if not df_f.empty and pd.notna(df_f.iloc[0]["min_fecha"]):
            dias = max((df_f.iloc[0]["max_fecha"] - df_f.iloc[0]["min_fecha"]).days + 1, 1)

        df_base["rotacion_diaria"] = df_base["cant_vend"] / dias

        # KPIs
        utilidad_total = float(df_base["utilidad_total"].sum())
        ingreso_total = float(df_base["ingreso_total"].sum())
        margen_global = round((utilidad_total / ingreso_total * 100), 2) if ingreso_total > 0 else 0
        productos = len(df_base)

        alta_rotacion_min = df_base["cant_vend"].quantile(0.8) if len(df_base) > 0 else 0
        if alta_rotacion_min < 5: alta_rotacion_min = 5

        bajo_margen_df = df_base[(df_base["margen_pct"] < 5) & (df_base["cant_vend"] >= alta_rotacion_min)]
        bajo_margen = json.loads(bajo_margen_df.sort_values("margen_pct", ascending=True).to_json(orient="records"))

        top_rentables = json.loads(df_base.nlargest(15, "utilidad_total").to_json(orient="records"))

        # Laboratorios
        por_lab = df_base.groupby("lab", as_index=False).agg(utilidad_total=("utilidad_total", "sum"))
        por_lab = json.loads(por_lab.nlargest(15, "utilidad_total").to_json(orient="records"))

        # Matriz ABC
        df_base = df_base.sort_values("ingreso_total", ascending=False)
        df_base["cum_ing"] = df_base["ingreso_total"].cumsum()
        df_base["pct_ing"] = df_base["cum_ing"] / df_base["ingreso_total"].sum()
        df_base["abc_ventas"] = np.where(df_base["pct_ing"] <= 0.8, "A", np.where(df_base["pct_ing"] <= 0.95, "B", "C"))

        df_base = df_base.sort_values("utilidad_total", ascending=False)
        df_base["cum_uti"] = df_base["utilidad_total"].cumsum()
        tot_uti = df_base["utilidad_total"].sum()
        if tot_uti > 0:
            df_base["pct_uti"] = df_base["cum_uti"] / tot_uti
            df_base["abc_margen"] = np.where(df_base["pct_uti"] <= 0.8, "A", np.where(df_base["pct_uti"] <= 0.95, "B", "C"))
        else:
            df_base["abc_margen"] = "C"

        df_base["matriz_abc"] = df_base["abc_ventas"] + "-" + df_base["abc_margen"]

        matriz = json.loads(df_base.to_json(orient="records"))

        kpis = {
            "utilidad_total": round(utilidad_total, 0),
            "ingreso_total": round(ingreso_total, 0),
            "margen_global": margen_global,
            "productos": productos,
            "bajo_margen_count": len(bajo_margen_df),
            "bajo_margen_umbral_pct": 5,
            "alta_rotacion_min_unidades": round(alta_rotacion_min, 0),
            "dias_periodo": dias
        }

        return {
            "kpis": kpis,
            "top_rentables": top_rentables,
            "bajo_margen": bajo_margen,
            "matriz_abc": matriz,
            "por_laboratorio": por_lab
        }

    # â”€â”€ Explorador de BD (Solo tablas de la vista actual) â”€â”€

    def get_tables_info(self) -> list[dict]:
        """Obtiene la lista de tablas usando INFORMATION_SCHEMA."""
        sql = """
        SELECT TABLE_SCHEMA, TABLE_NAME, TABLE_TYPE
        FROM INFORMATION_SCHEMA.TABLES
        WHERE TABLE_TYPE = 'BASE TABLE' AND TABLE_SCHEMA = 'dbo'
        ORDER BY TABLE_NAME
        """
        df = self._executor.execute_read(sql)
        return df.to_dict(orient="records")

    def get_table_columns(self, table_name: str) -> list[dict]:
        """Obtiene las columnas de una tabla validando contra INFORMATION_SCHEMA."""
        sql = """
        SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH, IS_NULLABLE
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = 'dbo' AND TABLE_NAME = ?
        ORDER BY ORDINAL_POSITION
        """
        df = self._executor.execute_read(sql, params=(table_name,))
        if df.empty:
            return []
        return df.to_dict(orient="records")

    def get_table_preview(self, table_name: str, max_rows: int = 50) -> list[dict]:
        """Retorna filas de ejemplo validando la tabla previamente."""
        # ValidaciÃ³n de seguridad adicional (aunque SafeQuery ya lo protege)
        cols = self.get_table_columns(table_name)
        if not cols:
            raise ValueError(f"Tabla no encontrada o invÃ¡lida: {table_name}")

        # Construir de manera segura
        sql = f"SELECT TOP {max_rows} * FROM [dbo].[{table_name}]"
        df = self._executor.execute_read(sql)
        # Convertir a records manejando correctamente los valores NaN
        import json
        return json.loads(df.to_json(orient="records"))


# Instancia Ãºnica del servicio
_db_service: Optional[DatabaseService] = None

def get_db_service() -> Optional[DatabaseService]:
    global _db_service
    if not is_db_configured():
        return None
    if _db_service is None:
        _db_service = DatabaseService()
    return _db_service
