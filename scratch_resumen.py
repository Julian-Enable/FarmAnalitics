def resumen(
    fecha_ini: str = None,
    fecha_fin: str = None,
    x_session_id: str = Header(default="default-session")
):
    db = get_db_service()
    if db:
        # SQL Native Implementation
        f_ini, f_fin = _effective_summary_range(fecha_ini, fecha_fin)
        fecha_ini_eff = f_ini.strftime("%Y-%m-%d")
        fecha_fin_eff = f_fin.strftime("%Y-%m-%d")
        dias_periodo = max((f_fin - f_ini).days + 1, 1)

        kpis = db.get_resumen_kpis(fecha_ini_eff, fecha_fin_eff)
        ing_total = kpis.get("ingresos", 0)
        und_total = kpis.get("unidades", 0)
        n_fact = kpis.get("facturas", 0)
        ticket = ing_total / n_fact if n_fact > 0 else 0

        costos = db.get_resumen_costo_utilidad(fecha_ini_eff, fecha_fin_eff)
        costo_total = costos.get("costo_total")
        util_bruta = None
        margen_pct = None
        if costo_total is not None:
            util_bruta = ing_total - costo_total
            margen_pct = round((util_bruta / ing_total * 100), 1) if ing_total > 0 else 0

        tend = db.get_resumen_tendencia(fecha_ini_eff, fecha_fin_eff)

        top_productos_raw = db.get_resumen_ranking("producto", fecha_ini_eff, fecha_fin_eff, limit=5)
        top_sedes_raw = db.get_resumen_ranking("sede", fecha_ini_eff, fecha_fin_eff, limit=100)
        top_vendedores_raw = db.get_resumen_ranking("vendedor", fecha_ini_eff, fecha_fin_eff, limit=5)
        top_labs_raw = db.get_resumen_ranking("laboratorio", fecha_ini_eff, fecha_fin_eff, limit=5)

        def format_ranking(raw_list, name_key, max_ingreso=None):
            if not raw_list: return []
            m_ing = max_ingreso or max(r["ingreso"] for r in raw_list)
            if m_ing <= 0: m_ing = 1
            return [
                {name_key: str(r.get("nombre") or r.get("sede") or r.get("vendedor") or r.get("laboratorio"))[:32],
                 "ingreso": round(r["ingreso"], 0),
                 "pct": round(r["ingreso"] / m_ing * 100, 0)}
                for r in raw_list
            ]

        ing_max_prod = max([r["ingreso"] for r in top_productos_raw], default=1)
        top_productos = format_ranking(top_productos_raw, "nombre", ing_max_prod)

        ing_max_vend = max([r["ingreso"] for r in top_vendedores_raw], default=1)
        top_vendedores = format_ranking(top_vendedores_raw, "vendedor", ing_max_vend)

        ing_max_lab = max([r["ingreso"] for r in top_labs_raw], default=1)
        top_laboratorios = format_ranking(top_labs_raw, "laboratorio", ing_max_lab)

        total_sedes = sum(r["ingreso"] for r in top_sedes_raw)
        sedes = []
        for r in top_sedes_raw:
            sedes.append({
                "sede": r["sede"],
                "ingresos": r["ingreso"],
                "pct": round((r["ingreso"] / total_sedes * 100), 1) if total_sedes > 0 else 0
            })

        df_nc = db.get_notas_credito(fecha_ini_eff, fecha_fin_eff)
        devoluciones_resumen = None
        if df_nc is not None and not df_nc.empty:
            notas_unicas = _notas_credito_note_frame(df_nc)
            total_devuelto = float(notas_unicas["Total Neto"].sum())
            n_notas = len(notas_unicas)
            tasa_devolucion = round(total_devuelto / ing_total * 100, 2) if ing_total > 0 else 0
            ingresos_netos = round(ing_total - total_devuelto, 0)
            devoluciones_resumen = {
                "total_devuelto": round(total_devuelto, 0),
                "n_notas": n_notas,
                "tasa_pct": tasa_devolucion,
                "ingresos_netos": ingresos_netos,
            }

        capital_quieto = 0.0
        productos_sin_stock = 0
        productos_criticos_7d = 0
        productos_atencion_15d = 0

        df_a = db.get_resumen_alertas_df(fecha_ini_eff, fecha_fin_eff)
        if df_a is not None and not df_a.empty:
            max_fecha = pd.to_datetime(f_fin)
            df_a["ultima_venta"] = pd.to_datetime(df_a["ultima_venta"], unit='ms', errors="coerce")
            df_a["dias_sin_venta"] = (max_fecha - df_a["ultima_venta"]).dt.days
            df_a["dias_sin_venta"] = df_a["dias_sin_venta"].fillna(9999)

            rotacion_diaria = df_a["cant_vend"] / dias_periodo
            df_a["cobertura_dias"] = df_a["Total"] / rotacion_diaria.replace(0, np.nan)
            df_a["cobertura_dias"] = df_a["cobertura_dias"].fillna(9999)

            productos_sin_stock = int((df_a["Total"] <= 0).sum())
            productos_criticos_7d = int(((df_a["cobertura_dias"] < 7) & (df_a["Total"] > 0)).sum())
            productos_atencion_15d = int(((df_a["cobertura_dias"] >= 7) & (df_a["cobertura_dias"] < 15)).sum())
            
            # Excluir servicios del capital quieto
            es_servicio = (df_a.get("Nivel", "").astype(str).str.upper() == "SERVICIOS") | (df_a.get("Descripcion", "").astype(str).str.contains("DOMICILIO|INYECTOLOGIA|FLETE|TARIFA DE SERVICIO", case=False, na=False))
            quietos = df_a[(df_a["dias_sin_venta"] > QUIETO_DIAS_DEFAULT) & (~es_servicio)]
            capital_quieto = float((quietos["Total"] * quietos["PrecioCompra"]).sum())

        return {
            "kpis": {
                "ingresos": round(ing_total, 0),
                "unidades": int(und_total),
                "facturas": int(n_fact),
                "ticket": round(ticket, 0),
                "utilidad": round(util_bruta, 0) if util_bruta is not None else None,
                "margen_pct": margen_pct,
            },
            "tendencia": tend,
            "top_productos": top_productos,
            "top_vendedores": top_vendedores,
            "top_laboratorios": top_laboratorios,
            "sedes": sedes,
            "devoluciones": devoluciones_resumen,
            "alertas_inventario": {
                "capital_quieto": round(capital_quieto, 0),
                "productos_sin_stock": productos_sin_stock,
                "productos_criticos_7d": productos_criticos_7d,
                "productos_atencion_15d": productos_atencion_15d,
            }
        }
    
    # =========================================================================
    # Pandas / Parquet Fallback Implementation (Modo Sincronizador)
    # =========================================================================
    df_v, df_c, df_i, df_n = _management_frames(x_session_id)
    if df_v is None or df_v.empty:
        raise HTTPException(404, "No hay datos de ventas cargados")

    f_ini, f_fin = _effective_summary_range(fecha_ini, fecha_fin)
    v_filt = _apply_date_filter(df_v, f_ini.strftime("%Y-%m-%d"), f_fin.strftime("%Y-%m-%d"))
    if v_filt.empty:
        return {"kpis": {}, "tendencia": [], "top_productos": [], "top_vendedores": [], "top_laboratorios": [], "sedes": []}

    dias_periodo = max((f_fin - f_ini).days + 1, 1)

    # KPIs Principales
    ing_total = float(v_filt["Ingreso"].sum())
    und_total = int(v_filt["Cant"].sum())
    n_fact = int(v_filt["Factura"].nunique()) if "Factura" in v_filt.columns else 0
    ticket = ing_total / n_fact if n_fact > 0 else 0

    # Utilidad
    util_bruta = None
    margen_pct = None
    if df_i is not None and not df_i.empty:
        # Cruce con inventario para obtener costo
        v_agg = v_filt.groupby("Referencia", as_index=False)["Cant"].sum()
        if "Precio Compra" in df_i.columns:
            m = v_agg.merge(df_i[["Referencia", "Precio Compra"]], on="Referencia", how="inner")
            m["Costo_Total"] = m["Cant"] * pd.to_numeric(m["Precio Compra"], errors="coerce").fillna(0)
            costo_total = float(m["Costo_Total"].sum())
            util_bruta = ing_total - costo_total
            margen_pct = round(util_bruta / ing_total * 100, 1) if ing_total > 0 else 0

    # Tendencia
    tend = []
    if "Fecha" in v_filt.columns and not v_filt.empty:
        v_filt["Fecha_dt"] = pd.to_datetime(v_filt["Fecha"], errors="coerce")
        s = v_filt.set_index("Fecha_dt").resample("W")["Ingreso"].sum().reset_index()
        tend = [{"fecha": str(r["Fecha_dt"].date()), "ingreso": round(r["Ingreso"], 0)} for _, r in s.iterrows() if pd.notnull(r["Fecha_dt"])]

    # Rankings function
    def make_ranking(df_grouped, name_key, display_key, limit=5):
        if df_grouped.empty: return []
        sorted_df = df_grouped.sort_values("Ingreso", ascending=False).head(limit)
        m_ing = sorted_df["Ingreso"].max()
        if m_ing <= 0: m_ing = 1
        res = []
        for _, r in sorted_df.iterrows():
            res.append({
                name_key: str(r[display_key])[:32] if pd.notnull(r[display_key]) else "N/A",
                "ingreso": round(r["Ingreso"], 0),
                "pct": round(r["Ingreso"] / m_ing * 100, 0)
            })
        return res

    # Top Productos
    v_prod = v_filt.groupby("Descripcion", as_index=False)["Ingreso"].sum()
    top_productos = make_ranking(v_prod, "nombre", "Descripcion", 5)

    # Top Vendedores
    top_vendedores = []
    if "NombreVendedor" in v_filt.columns:
        v_vend = v_filt.groupby("NombreVendedor", as_index=False)["Ingreso"].sum()
        top_vendedores = make_ranking(v_vend, "vendedor", "NombreVendedor", 5)

    # Top Laboratorios
    top_laboratorios = []
    if "Laboratorio" in v_filt.columns:
        v_lab = v_filt.groupby("Laboratorio", as_index=False)["Ingreso"].sum()
        top_laboratorios = make_ranking(v_lab, "laboratorio", "Laboratorio", 5)

    # Sedes
    sedes = []
    if "Punto Venta" in v_filt.columns:
        v_sede = v_filt.groupby("Punto Venta", as_index=False)["Ingreso"].sum().sort_values("Ingreso", ascending=False)
        total_sedes_ing = v_sede["Ingreso"].sum()
        for _, r in v_sede.iterrows():
            sedes.append({
                "sede": str(r["Punto Venta"]),
                "ingresos": round(r["Ingreso"], 0),
                "pct": round(r["Ingreso"] / total_sedes_ing * 100, 1) if total_sedes_ing > 0 else 0
            })

    # Notas Crédito
    devoluciones_resumen = None
    if df_n is not None and not df_n.empty:
        n_filt = _apply_date_filter(df_n, f_ini.strftime("%Y-%m-%d"), f_fin.strftime("%Y-%m-%d"))
        if not n_filt.empty:
            notas_unicas = _notas_credito_note_frame(n_filt)
            total_devuelto = float(notas_unicas["Total Neto"].sum())
            n_notas_val = len(notas_unicas)
            tasa_devolucion = round(total_devuelto / ing_total * 100, 2) if ing_total > 0 else 0
            ingresos_netos = round(ing_total - total_devuelto, 0)
            devoluciones_resumen = {
                "total_devuelto": round(total_devuelto, 0),
                "n_notas": n_notas_val,
                "tasa_pct": tasa_devolucion,
                "ingresos_netos": ingresos_netos,
            }

    # Alertas Inventario
    capital_quieto = 0.0
    productos_sin_stock = 0
    productos_criticos_7d = 0
    productos_atencion_15d = 0

    if df_i is not None and not df_i.empty:
        inv = _inventory_with_total(df_i)
        # Excluir servicios
        es_servicio = (inv["Nivel"].astype(str).str.upper() == "SERVICIOS") | (inv["Descripcion"].astype(str).str.contains("DOMICILIO|INYECTOLOGIA|FLETE|TARIFA DE SERVICIO", case=False, na=False))
        inv = inv[~es_servicio]
        
        # Rotación y última venta de los 35 días (general)
        df_v_recent = df_v[df_v["Fecha"] >= pd.Timestamp.now() - pd.Timedelta(days=35)] if "Fecha" in df_v.columns else df_v
        v_agg2 = df_v_recent.groupby("Referencia", as_index=False).agg(uds_vendidas=("Cant", "sum"), ultima_venta=("Fecha", "max"))
        
        m_inv = inv.merge(v_agg2, on="Referencia", how="left")
        m_inv["uds_vendidas"] = m_inv["uds_vendidas"].fillna(0)
        
        max_fecha_v = pd.to_datetime(df_v["Fecha"].max()) if "Fecha" in df_v.columns and not df_v["Fecha"].empty else pd.Timestamp.now()
        m_inv["ultima_venta"] = pd.to_datetime(m_inv["ultima_venta"], errors="coerce")
        m_inv["dias_sin_venta"] = (max_fecha_v - m_inv["ultima_venta"]).dt.days.fillna(9999)
        
        rotacion_diaria = m_inv["uds_vendidas"] / 35
        m_inv["cobertura_dias"] = m_inv["Total"] / rotacion_diaria.replace(0, np.nan)
        m_inv["cobertura_dias"] = m_inv["cobertura_dias"].fillna(9999)
        
        productos_sin_stock = int((m_inv["Total"] <= 0).sum())
        productos_criticos_7d = int(((m_inv["cobertura_dias"] < 7) & (m_inv["Total"] > 0)).sum())
        productos_atencion_15d = int(((m_inv["cobertura_dias"] >= 7) & (m_inv["cobertura_dias"] < 15)).sum())
        
        quietos = m_inv[m_inv["dias_sin_venta"] > QUIETO_DIAS_DEFAULT]
        if "Precio Compra" in quietos.columns:
            capital_quieto = float((quietos["Total"] * pd.to_numeric(quietos["Precio Compra"], errors="coerce").fillna(0)).sum())

    return {
        "kpis": {
            "ingresos": round(ing_total, 0),
            "unidades": int(und_total),
            "facturas": int(n_fact),
            "ticket": round(ticket, 0),
            "utilidad": round(util_bruta, 0) if util_bruta is not None else None,
            "margen_pct": margen_pct,
        },
        "tendencia": tend,
        "top_productos": top_productos,
        "top_vendedores": top_vendedores,
        "top_laboratorios": top_laboratorios,
        "sedes": sedes,
        "devoluciones": devoluciones_resumen,
        "alertas_inventario": {
            "capital_quieto": round(capital_quieto, 0),
            "productos_sin_stock": productos_sin_stock,
            "productos_criticos_7d": productos_criticos_7d,
            "productos_atencion_15d": productos_atencion_15d,
        }
    }
