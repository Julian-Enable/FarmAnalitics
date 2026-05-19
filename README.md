![FarmAnalítics Dashboard](assets/banner.png)

<h1 align="center">FarmAnalítics</h1>

<p align="center">
  Carga tus archivos. Ve tus números. Toma decisiones.
</p>

<p align="center">
  <a href="https://farm-analitics.vercel.app">
    <img src="https://img.shields.io/badge/demo-live-22c55e?style=flat-square&labelColor=0f172a" />
  </a>
  <img src="https://img.shields.io/badge/python-3.11-3b82f6?style=flat-square&labelColor=0f172a" />
  <img src="https://img.shields.io/badge/fastapi-0.110-06b6d4?style=flat-square&labelColor=0f172a" />
  <img src="https://img.shields.io/badge/vue-3.5-42d392?style=flat-square&labelColor=0f172a" />
  <img src="https://img.shields.io/badge/pandas-2.2-150458?style=flat-square&labelColor=0f172a" />
</p>

---

Antes de FarmAnalítics, sacar métricas de una cadena de farmacias significaba exportar desde el POS, abrir Excel, cruzar tablas manualmente y rezar para que los datos del mes anterior todavía sirvieran. **FarmAnalítics reemplaza ese proceso completo**: sube tus archivos CSV o Excel de ventas, compras, inventario y notas de crédito, y en segundos tienes KPIs, alertas de stock, análisis de rentabilidad por producto, proyecciones de metas y un análisis completo de devoluciones — sin instalar nada, sin base de datos, sin configuración.

**Stack:** FastAPI · Pandas · Vue 3 · Pinia · ApexCharts · Railway · Vercel  
**Producción:** https://farm-analitics.vercel.app · API: https://farmanalitics-production.up.railway.app/docs

---

## Cómo está construido

Sin base de datos. Sin persistencia. Todo vive en RAM indexado por `session_id`. El frontend genera un UUID en el primer acceso, lo guarda en `localStorage` y lo envía como header en cada request. El backend mantiene un dict global de sesiones con TTL de 24h y limpieza automática.

```
Browser                          FastAPI (Railway)
  │                                     │
  │  POST /api/upload                   │
  │  X-Session-Id: <uuid>               │
  │  multipart: ventas[], inventario?   │
  ├────────────────────────────────────►│
  │                                     ├─► _read_upload()
  │                                     │     valida extensión + tamaño (≤50MB)
  │                                     │
  │                                     ├─► leer_bytes()
  │                                     │     xlsx: detecta hojas con col REFERENCIA
  │                                     │     excluye hojas "reporte"/"reportes"
  │                                     │     concat si hay múltiples archivos
  │                                     │
  │                                     ├─► procesar_ventas()
  │                                     │     normaliza aliases de columnas
  │                                     │     tipado: Cant, Precio → numeric
  │                                     │     Fecha → datetime
  │                                     │     Ingreso = origen ?? Cant × Precio
  │                                     │
  │                                     ├─► _ensure_required_columns()
  │                                     │     HTTP 400 si faltan columnas clave
  │                                     │
  │                                     └─► set_df(session_id, "ventas", df)
  │                                               _sessions[id]["data"]["ventas"] = df
  │◄────────────────────────────────────│         last_accessed = time.time()
  │  {ok: true, filas: {ventas: 45230}} │
  │                                     │
  │  GET /api/resumen?fecha_ini=...      │
  ├────────────────────────────────────►│
  │                                     ├─► get_df(session_id, "ventas")
  │                                     ├─► _apply_date_filter(df, "Fecha", ...)
  │                                     ├─► KPIs: sum, nunique, mean
  │                                     ├─► variación: divide período en 2 mitades
  │                                     ├─► si hay inventario:
  │                                     │     _sales_profit_frame() → margen %
  │                                     │     cobertura_dias = Total / rot_diaria
  │                                     │     capital_quieto = stock × costo (>60d)
  │                                     ├─► tendencia: resample("W")["Ingreso"].sum()
  │                                     └─► top 5 productos, vendedores, labs
  │◄────────────────────────────────────│
  │  JSON → Pinia store → ApexCharts   │
```

---

## Módulos

| Ruta | Requiere | Qué muestra |
| :--- | :--- | :--- |
| `/` | ventas | Health score, 7 KPIs con variación, alertas de stock, tendencia semanal, tops |
| `/ventas` | ventas | Top productos/labs, rendimiento por vendedor, tendencia mensual, tabla detalle |
| `/rentabilidad` | ventas + inventario | Margen % y utilidad bruta por producto, alto margen vs baja rotación |
| `/inventario` | inventario (ventas opcional) | Cobertura en días, productos críticos, capital inmovilizado |
| `/compras` | compras | Costo por proveedor y sede, comparativa vs ventas |
| `/sedes` | ventas | Ingresos, ticket y facturas comparados entre puntos de venta |
| `/devoluciones` | notas\_credito | Tasa de devolución, motivos clasificados automáticamente, productos más devueltos |
| `/metas` | ventas | Proyección por sede y vendedor en 3 escenarios de crecimiento |

### Health Score

El Centro de Comando calcula un índice de salud del negocio (0–100) que se actualiza con cada carga:

```python
score = 100
score -= min(alertas.sin_stock,   20) * 2.0   # hasta -40  por quiebres de stock activos
score -= min(alertas.criticos_7d, 10) * 1.5   # hasta -15  por cobertura < 7 días
if kpis.variacion_ing < 0:  score -= 10        # tendencia negativa en el período
if kpis.margen_pct    < 10: score -= 10        # margen bruto bajo umbral
score = max(0, min(100, round(score)))
```

### Proyección de Metas

Combina el rendimiento reciente con el comportamiento estacional del año anterior:

```python
# Por sede
idp               = ventas_mes_anterior / dias_mes_anterior        # ingreso diario promedio
proyeccion_base   = idp * dias_totales_proy

inc_hist          = (venta_hist_obj / venta_hist_prev) - 1.0       # variación año anterior
inc_hist          = max(min(inc_hist, 0.35), -0.20)                # clamp: evita outliers
meta_sede         = proyeccion_base * (1 + inc_hist + (factor - 1))

# factor: conservador=1.02  normal=1.05  agresivo=1.10
# vendedores con < 5% de aporte de la sede son excluidos de la distribución individual
```

### Clasificador de Motivos (Devoluciones)

```python
_MOTIVO_RULES = [
    ("Error de Facturación",  ["error de facturaci", "error factur"]),
    ("Error del Vendedor",    ["error del vendedor", "error vendedor"]),
    ("Solicitud del Cliente", ["error del cliente", "cliente pide",
                               "cliente no", "cliente realiza", "cliente quiere"]),
    ("Cambio de Producto",    ["cambio", "cambi"]),
    ("Problema de Entrega",   ["domicilio", "entrega", "demora"]),
]
# El valor de cada nota se distribuye proporcionalmente entre los ítems
# de la factura original para identificar los productos más devueltos.
```

---

## API

Prefijo `/api`. Sesión por header `X-Session-Id` (default: `"default-session"`).

### Upload

```bash
# Uno o varios archivos de ventas + inventario opcional
curl -X POST https://farmanalitics-production.up.railway.app/api/upload \
  -H "X-Session-Id: mi-sesion" \
  -F "ventas=@ventas_enero.xlsx" \
  -F "ventas=@ventas_febrero.xlsx" \
  -F "inventario=@inventario.csv"
```

```json
{
  "ok": true,
  "filas": { "ventas": 45230, "inventario": 3841 },
  "diagnostico": {
    "ventas": { "filas": 45230, "faltantes": [], "ok": true }
  }
}
```

**Errores:** `400` extensión inválida · archivo vacío · columnas faltantes — `413` supera 50 MB

### Endpoints disponibles

```
POST   /api/upload                              Carga de archivos
GET    /api/status                              Qué datos tiene la sesión activa
GET    /api/schema                              Columnas requeridas y umbrales
DELETE /api/reset                               Limpia la sesión

GET    /api/resumen?fecha_ini&fecha_fin
GET    /api/ventas?sede&nivel&laboratorio&fecha_ini&fecha_fin
GET    /api/rentabilidad?fecha_ini&fecha_fin
GET    /api/inventario?quieto_dias&min_dias&max_dias
GET    /api/compras?fecha_ini&fecha_fin&sede
GET    /api/sedes?fecha_ini&fecha_fin
GET    /api/notas-credito?fecha_ini&fecha_fin
GET    /api/metas?agresividad&fecha_ini&fecha_fin
```

Documentación interactiva completa: `/docs`

---

## Esquema de archivos

El sistema acepta `.csv`, `.xlsx` y `.xls` (máximo 50 MB por archivo). En Excel con múltiples hojas, se procesan automáticamente las que tienen columna `REFERENCIA`. Las hojas llamadas `"reporte"` o `"reportes"` se ignoran.

<details>
<summary>Ver columnas requeridas y aliases por tipo de archivo</summary>

**Ventas**

| Columna esperada | Alias aceptados | Calculada si falta |
| :--- | :--- | :--- |
| `Referencia` | `REFERENCIA` | |
| `Descripcion` | `DESCRIPCION` | |
| `Cant` | `CANT` | |
| `Precio Venta` | `Precio`, `PRECIO` | |
| `Laboratorio` | `LABORATORIO` | |
| `Fecha` | `FECHA` | |
| `Punto Venta` | `SEDE` | |
| `Ingreso` | | `Cant × Precio Venta` |
| `Factura` | `FACTURA` | opcional |
| `Creada` | | opcional (vendedor) |
| `Nivel` | `NIVEL` | opcional (categoría) |

**Compras** — requeridas: `FECHA`, `PROVEEDOR`, `REFERENCIA`, `DESCRIPCION`, `LABORATORIO`, `PRECIO`, `CANT`, `SEDE`. Calculada: `Costo Total = CANT × PRECIO`.

**Inventario** — requeridas: `Referencia`, `Descripcion`, `Laboratorio`. Si no hay columna `Total`, se suma el stock de todas las columnas numéricas que no estén en `EXCLUDED_INVENTORY_COLUMNS`.

**Notas de Crédito** — requeridas: `Fecha`, `NotaCredito`, `PuntoVenta`, `Total`. Calculadas: `Total Neto = Total − IVA`, `Motivo = classify(Observaciones)`.

</details>

---

## Configuración

Todos los umbrales de negocio están centralizados en `config.py`:

| Constante | Valor | Descripción |
| :--- | :--- | :--- |
| `MAX_UPLOAD_SIZE` | 50 MB | Límite por archivo |
| `INV_MIN_DIAS` | 25 | Días de cobertura mínima (umbral de alerta) |
| `INV_MAX_DIAS` | 40 | Días de cobertura objetivo |
| `LOW_MARGIN_PCT` | 5.0 | Margen bajo el cual un producto se marca como crítico (%) |
| `HIGH_ROTATION_QUANTILE` | 0.80 | Percentil para clasificar alta rotación |
| `QUIETO_DIAS_DEFAULT` | 60 | Días sin movimiento → capital inmovilizado |
| `SEDES_INVENTARIO` | `[PRINCIPAL, SUCURSAL, MORATO, VARDI, CEDI, OFICINA 805]` | Sedes reconocidas en inventario |

---

## Estructura

```
.
├── config.py                      # Constantes globales y parámetros de negocio
├── requirements.txt               # Python deps
├── Procfile                       # Railway: uvicorn backend.main:app
├── assets/
│   └── banner.png
│
├── backend/
│   ├── main.py                    # FastAPI app + CORS middleware
│   ├── routers/
│   │   └── analytics.py          # Todos los endpoints /api/* (~1300 LOC)
│   └── services/
│       ├── processing.py         # ETL: parse, normalize, derive
│       └── data_store.py         # Session store in-memory (TTL 24h)
│
└── frontend/
    ├── vite.config.js             # Dev proxy /api → :8000
    └── src/
        ├── main.js                # Bootstrap app
        ├── stores/dashboard.js    # Pinia: estado global + fetchers
        ├── views/                 # Una vista por módulo (8 total)
        └── components/
            ├── AppSidebar.vue     # Upload + navegación
            ├── charts/            # Wrappers ApexCharts
            └── ui/                # Componentes genéricos
```

---

## Setup local

```bash
# Backend
python -m venv .venv
.venv\Scripts\activate       # Windows
pip install -r requirements.txt
uvicorn backend.main:app --reload --port 8000
# → http://localhost:8000/docs

# Frontend (otra terminal)
cd frontend
npm install
npm run dev
# → http://localhost:5173
```

---

## Deploy

**Backend → Railway**

```
web: uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}
```

Variable opcional `DEFAULT_VENTAS_2025_PATH`: ruta a un CSV preexistente para activar modo demo (el endpoint `/api/metas` puede usarlo sin que el usuario suba archivos).

**Frontend → Vercel**

```
Root:    frontend/
Build:   npm run build
Output:  dist/
Env:     VITE_API_URL=https://<tu-backend>.up.railway.app
```

---

## Notas técnicas

- Los valores `NaN` e `Inf` de Pandas se serializan como `null` usando `json.loads(df.to_json(...))` en lugar de `.to_dict()` — evita errores de serialización JSON estándar.
- La sesión de demos (`get_default_ventas()`) carga el CSV una sola vez y lo cachea en `_default_ventas_cache` para no releer disco en cada llamada a `/api/metas`.
- El cruce de notas de crédito con ventas para identificar productos devueltos asigna el valor de cada nota proporcionalmente al peso de cada ítem dentro de la factura original (`peso = ingreso_item / ingreso_factura`).

---

## Licencia

MIT
