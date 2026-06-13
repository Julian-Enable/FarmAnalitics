import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Callable

import pandas as pd
from dateutil.relativedelta import relativedelta

from backend.services.processing import _categorizar_motivo


logger = logging.getLogger(__name__)


class HistoricalStore:
    """Local parquet-backed store for data that does not need live POS reads."""

    def __init__(self, data_dir: str | None = None):
        root = Path(__file__).resolve().parents[2]
        configured_dir = data_dir or os.getenv("HISTORICAL_DATA_DIR")
        self.data_dir = Path(configured_dir) if configured_dir else root / "data" / "historico"
        self._cache: dict[str, pd.DataFrame] = {}

    def available(self) -> bool:
        return self._path("HISTORICO_VENTAS").exists()

    def inventory_available(self) -> bool:
        return self._path("INVENTARIO_ACTUAL").exists()

    def _path(self, name: str) -> Path:
        parquet_path = self.data_dir / f"{name}.parquet"
        if parquet_path.exists():
            return parquet_path
        return self.data_dir / f"{name}.csv"

    def _read(self, name: str) -> pd.DataFrame:
        if name in self._cache:
            return self._cache[name].copy()

        path = self._path(name)
        if not path.exists():
            return pd.DataFrame()

        if path.suffix.lower() == ".parquet":
            with open(path, "rb") as f:
                df = pd.read_parquet(f)
        else:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                df = pd.read_csv(f)

        df = self._normalize(name, df)
        self._cache[name] = df
        return df.copy()

    def _write(self, name: str, df: pd.DataFrame) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        path = self._path(name)
        if path.suffix.lower() == ".parquet":
            df.to_parquet(path, index=False)
        else:
            df.to_csv(path, index=False)
        self._cache[name] = self._normalize(name, df)

    def _lookup_map(self, name: str) -> dict:
        df = self._read(name)
        if df.empty or "ID" not in df.columns or "Nombre" not in df.columns:
            return {}
        ids = df["ID"].astype(str).str.strip()
        values = df["Nombre"].astype(str).str.strip()
        return dict(zip(ids, values))

    def _normalize(self, name: str, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()

        if name == "HISTORICO_VENTAS":
            for col in ["Fecha"]:
                if col in df.columns:
                    df[col] = pd.to_datetime(df[col], errors="coerce")
            for col in ["Cant", "Precio Venta", "Ingreso", "Total"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

            sedes = self._lookup_map("LOOKUP_PUNTO_VENTA")
            labs = self._lookup_map("LOOKUP_LABORATORIOS")
            niveles = self._lookup_map("LOOKUP_NIVELES")

            if "ID_PuntoVenta" in df.columns:
                df["Punto Venta"] = df["ID_PuntoVenta"].astype(str).str.strip().map(sedes).fillna(df["ID_PuntoVenta"])
            if "ID_Laboratorio" in df.columns:
                df["Laboratorio"] = df["ID_Laboratorio"].astype(str).str.strip().map(labs).fillna("Sin Laboratorio")
            if "ID_Nivel" in df.columns:
                df["Nivel"] = df["ID_Nivel"].astype(str).str.strip().map(niveles).fillna("Sin Nivel")
            return df

        if name == "HISTORICO_COMPRAS":
            if "FECHA" in df.columns:
                df["FECHA"] = pd.to_datetime(df["FECHA"], errors="coerce")
            for col in ["CANT", "PRECIO", "Costo Total"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

            sedes = self._lookup_map("LOOKUP_PUNTO_VENTA")
            labs = self._lookup_map("LOOKUP_LABORATORIOS")
            proveedores = self._lookup_map("LOOKUP_PROVEEDORES")

            if "ID_Proveedor" in df.columns:
                df["PROVEEDOR"] = df["ID_Proveedor"].astype(str).str.strip().map(proveedores).fillna(df["ID_Proveedor"])
            if "ID_PuntoVenta" in df.columns:
                df["SEDE"] = df["ID_PuntoVenta"].astype(str).str.strip().map(sedes).fillna(df["ID_PuntoVenta"])
            if "ID_Laboratorio" in df.columns:
                df["LABORATORIO"] = df["ID_Laboratorio"].astype(str).str.strip().map(labs).fillna("Sin Laboratorio")
            return df

        if name == "HISTORICO_NOTAS_CREDITO":
            if "Fecha" in df.columns:
                df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce")
            for col in [
                "Cantidad", "PrecioVenta", "IVAProducto", "TotalProducto",
                "SubTotalNota", "IVANota", "TotalNota", "Saldo",
            ]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

            sedes = self._lookup_map("LOOKUP_PUNTO_VENTA")
            labs = self._lookup_map("LOOKUP_LABORATORIOS")
            if "ID_PuntoVenta" in df.columns:
                df["Punto Venta"] = df["ID_PuntoVenta"].astype(str).str.strip().map(sedes).fillna(df["ID_PuntoVenta"])
                df["PuntoVenta"] = df["Punto Venta"]
            if "ID_Laboratorio" in df.columns:
                df["Laboratorio"] = df["ID_Laboratorio"].astype(str).str.strip().map(labs).fillna("Sin Laboratorio")
            if "TotalNota" in df.columns:
                df["Total Neto"] = df["TotalNota"]
            if "NotaCreditoID" in df.columns:
                df["NotaCredito"] = df["NotaCreditoID"]
            if "Observaciones" in df.columns:
                df["Motivo"] = df["Observaciones"].apply(_categorizar_motivo)
            else:
                df["Motivo"] = "Sin observacion"
            if "NotaCreditoID" in df.columns and "ID_PuntoVenta" in df.columns:
                df["NotaCreditoKey"] = (
                    df["ID_PuntoVenta"].astype(str).str.strip()
                    + "-"
                    + df["NotaCreditoID"].astype(str).str.strip()
                )
            return df

        if name == "HISTORICO_AJUSTES":
            if "Fecha" in df.columns:
                df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce")
            for col in ["Cantidad", "PrecioCompra", "PrecioVenta", "ValorCosto"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
            sedes = self._lookup_map("LOOKUP_PUNTO_VENTA")
            niveles = self._lookup_map("LOOKUP_NIVELES")
            if "ID_PuntoVenta" in df.columns:
                df["Punto Venta"] = df["ID_PuntoVenta"].astype(str).str.strip().map(sedes).fillna(df["ID_PuntoVenta"])
            if "ID_Nivel" in df.columns:
                df["Nivel"] = df["ID_Nivel"].astype(str).str.strip().map(niveles).fillna("Sin Nivel")
            if "Motivo" in df.columns:
                df["Motivo"] = df["Motivo"].astype(str).str.strip().replace({"": "Sin motivo", "nan": "Sin motivo"})
            return df

        if name == "HISTORICO_DESCUENTOS":
            if "Fecha" in df.columns:
                df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce")
            for col in ["PrecioVenta", "Valor"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
            sedes = self._lookup_map("LOOKUP_PUNTO_VENTA")
            if "ID_PuntoVenta" in df.columns:
                df["Punto Venta"] = df["ID_PuntoVenta"].astype(str).str.strip().map(sedes).fillna(df["ID_PuntoVenta"])
            nombre = df["NombreVendedor"].astype(str).str.strip() if "NombreVendedor" in df.columns else pd.Series("", index=df.index)
            creada = df["Creada"].astype(str).str.strip() if "Creada" in df.columns else pd.Series("", index=df.index)
            invalid = {"", "nan", "none"}
            df["Cajero"] = nombre.where(~nombre.str.lower().isin(invalid), creada).str.strip()
            if "Plan" in df.columns:
                # Limpiar prefijos repetitivos del nombre del plan
                df["Plan"] = (df["Plan"].astype(str)
                              .str.replace(r"^Informaci[oó]n\s+", "", regex=True)
                              .str.replace(r"\s*\(Todos los medios de pago\)\s*$", "", regex=True)
                              .str.strip())
            return df

        if name == "HISTORICO_COMISIONES":
            if "Fecha" in df.columns:
                df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce")
            for col in ["Cant", "Precio Venta", "Ingreso", "Comision"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
            sedes = self._lookup_map("LOOKUP_PUNTO_VENTA")
            if "ID_PuntoVenta" in df.columns:
                df["Punto Venta"] = df["ID_PuntoVenta"].astype(str).str.strip().map(sedes).fillna(df["ID_PuntoVenta"])
            # Vendedor: nombre comercial, con respaldo en Creada
            nombre = df["NombreVendedor"].astype(str).str.strip() if "NombreVendedor" in df.columns else pd.Series("", index=df.index)
            creada = df["Creada"].astype(str).str.strip() if "Creada" in df.columns else pd.Series("", index=df.index)
            invalid = {"", "nan", "none"}
            df["Vendedor"] = nombre.where(~nombre.str.lower().isin(invalid), creada).str.strip()
            return df

        if name == "HISTORICO_DOMICILIOS":
            for col in ["Fecha", "FechaDespacho", "FechaEntrega"]:
                if col in df.columns:
                    df[col] = pd.to_datetime(df[col], errors="coerce")
            if "Total" in df.columns:
                df["Total"] = pd.to_numeric(df["Total"], errors="coerce").fillna(0)
            sedes = self._lookup_map("LOOKUP_PUNTO_VENTA")
            if "ID_PuntoVenta" in df.columns:
                df["Punto Venta"] = df["ID_PuntoVenta"].astype(str).str.strip().map(sedes).fillna(df["ID_PuntoVenta"])
            for col in ["Mensajero", "Estado", "Direccion", "Cliente", "Tipo"]:
                if col in df.columns:
                    df[col] = df[col].astype(str).str.strip()
            return df

        if name == "INVENTARIO_ACTUAL":
            for col in [
                "Total", "Precio Compra", "Precio Venta", "Stock Minimo",
                "Stock Maximo", "Comision", "Utilidad",
            ]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

            sedes = self._lookup_map("LOOKUP_PUNTO_VENTA")
            labs = self._lookup_map("LOOKUP_LABORATORIOS")
            niveles = self._lookup_map("LOOKUP_NIVELES")

            rename_dict = {col: sedes[col] for col in df.columns if col in sedes}
            if rename_dict:
                df = df.rename(columns=rename_dict)

            if "ID_Laboratorio" in df.columns:
                df["Laboratorio"] = df["ID_Laboratorio"].astype(str).str.strip().map(labs).fillna("Sin Laboratorio")
            if "ID_Nivel" in df.columns:
                df["Nivel"] = df["ID_Nivel"].astype(str).str.strip().map(niveles).fillna("Sin Nivel")

            for col in df.columns:
                if col not in {
                    "Referencia", "Descripcion", "Laboratorio", "Nivel",
                    "ID_Laboratorio", "ID_Nivel", "Codigo",
                }:
                    numeric = pd.to_numeric(df[col], errors="coerce")
                    if numeric.notna().any():
                        df[col] = numeric.fillna(0)
            return df

        return df

    @staticmethod
    def _filter_dates(df: pd.DataFrame, column: str, fecha_ini=None, fecha_fin=None) -> pd.DataFrame:
        if df.empty or column not in df.columns:
            return df
        out = df
        if fecha_ini:
            out = out[out[column] >= pd.Timestamp(fecha_ini)]
        if fecha_fin:
            end = pd.Timestamp(fecha_fin)
            if isinstance(fecha_fin, str) and len(fecha_fin) == 10:
                out = out[out[column] < end + pd.Timedelta(days=1)]
            else:
                out = out[out[column] <= end]
        return out

    def get_ventas(self, fecha_ini=None, fecha_fin=None, sede=None, limit=None) -> pd.DataFrame:
        df = self._filter_dates(self._read("HISTORICO_VENTAS"), "Fecha", fecha_ini, fecha_fin)
        if sede and sede != "Todas":
            if sede in set(df.get("Punto Venta", pd.Series(dtype=str)).dropna().unique()):
                df = df[df["Punto Venta"] == sede]
            elif "ID_PuntoVenta" in df.columns:
                df = df[df["ID_PuntoVenta"] == sede]
        if limit:
            df = df.head(int(limit))
        return df.copy()

    def get_compras(self, fecha_ini=None, fecha_fin=None) -> pd.DataFrame:
        return self._filter_dates(self._read("HISTORICO_COMPRAS"), "FECHA", fecha_ini, fecha_fin).copy()

    def get_notas_credito(self, fecha_ini=None, fecha_fin=None) -> pd.DataFrame:
        return self._filter_dates(self._read("HISTORICO_NOTAS_CREDITO"), "Fecha", fecha_ini, fecha_fin).copy()

    def get_inventario(self) -> pd.DataFrame:
        return self._read("INVENTARIO_ACTUAL").copy()

    def domicilios_available(self) -> bool:
        return self._path("HISTORICO_DOMICILIOS").exists()

    def comisiones_available(self) -> bool:
        return self._path("HISTORICO_COMISIONES").exists()

    def get_comisiones(self, fecha_ini=None, fecha_fin=None) -> pd.DataFrame:
        return self._filter_dates(self._read("HISTORICO_COMISIONES"), "Fecha", fecha_ini, fecha_fin).copy()

    def ajustes_available(self) -> bool:
        return self._path("HISTORICO_AJUSTES").exists()

    def get_ajustes(self, fecha_ini=None, fecha_fin=None) -> pd.DataFrame:
        return self._filter_dates(self._read("HISTORICO_AJUSTES"), "Fecha", fecha_ini, fecha_fin).copy()

    def descuentos_available(self) -> bool:
        return self._path("HISTORICO_DESCUENTOS").exists()

    def get_descuentos(self, fecha_ini=None, fecha_fin=None) -> pd.DataFrame:
        return self._filter_dates(self._read("HISTORICO_DESCUENTOS"), "Fecha", fecha_ini, fecha_fin).copy()

    def get_clientes(self) -> pd.DataFrame:
        return self._read("LOOKUP_CLIENTES").copy()

    def ventas_available(self) -> bool:
        return self.available()

    def get_domicilios(self, fecha_ini=None, fecha_fin=None) -> pd.DataFrame:
        return self._filter_dates(self._read("HISTORICO_DOMICILIOS"), "Fecha", fecha_ini, fecha_fin).copy()

    def max_date(self, name: str, column: str) -> pd.Timestamp | None:
        df = self._read(name)
        if df.empty or column not in df.columns:
            return None
        value = pd.to_datetime(df[column], errors="coerce").max()
        return None if pd.isna(value) else value

    def merge_and_save(self, name: str, new_df: pd.DataFrame, subset: list[str]) -> int:
        if new_df is None or new_df.empty:
            return 0
        old_df = self._read(name)
        combined = pd.concat([old_df, new_df], ignore_index=True) if not old_df.empty else new_df.copy()
        before = len(combined)
        combined = combined.drop_duplicates(subset=[c for c in subset if c in combined.columns], keep="last")
        self._write(name, combined)
        return before - len(old_df)

    def refresh_recent(
        self,
        executor,
        ventas_fetcher: Callable[[str], pd.DataFrame],
        compras_fetcher: Callable[[str], pd.DataFrame],
        notas_fetcher: Callable[[str], pd.DataFrame],
        lookups_fetcher: Callable[[], dict[str, pd.DataFrame]],
        days: int = 35,
    ) -> dict:
        cutoff = (datetime.now() - relativedelta(days=days)).strftime("%Y-%m-%d")
        result = {"cutoff": cutoff, "ventas": 0, "compras": 0, "notas_credito": 0, "lookups": 0}

        for lookup_name, lookup_df in lookups_fetcher().items():
            self._write(lookup_name, lookup_df)
            result["lookups"] += len(lookup_df)

        result["ventas"] = self.merge_and_save(
            "HISTORICO_VENTAS",
            ventas_fetcher(cutoff),
            ["Factura", "Referencia", "Fecha", "ID_PuntoVenta"],
        )
        result["compras"] = self.merge_and_save(
            "HISTORICO_COMPRAS",
            compras_fetcher(cutoff),
            ["CompraID", "REFERENCIA"],
        )
        result["notas_credito"] = self.merge_and_save(
            "HISTORICO_NOTAS_CREDITO",
            notas_fetcher(cutoff),
            ["NotaCreditoID", "Referencia"],
        )
        logger.info("Historical refresh completed: %s", result)
        return result


_historical_store: HistoricalStore | None = None


def get_historical_store() -> HistoricalStore:
    global _historical_store
    if _historical_store is None:
        _historical_store = HistoricalStore()
    return _historical_store
