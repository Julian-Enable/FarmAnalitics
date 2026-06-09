# FarmAnalitics

Dashboard analitico para POS farmaceutico. La app actual usa un frontend Vue 3
desplegado en Vercel y un backend FastAPI desplegado en Railway. Los datos se
consumen desde historicos Parquet sincronizados desde SmartPOS y, cuando la red
lo permite, desde SQL Server en modo solo lectura.

## Produccion

- Frontend: https://farm-analitics.vercel.app
- API: https://farmanalitics-production.up.railway.app/docs

## Arquitectura

```text
SmartPOS SQL Server
        |
        | sincronizacion local programada
        v
data/historico/*.parquet
        |
        | subida al volumen de Railway
        v
FastAPI en Railway
        |
        v
Vue 3 en Vercel
```

## Estructura principal

```text
backend/                         API FastAPI y servicios analiticos
frontend/                        App Vue 3 + Vite
data/historico/                  Historico local ignorado por Git y Docker
scripts/dev/                     Scripts para iniciar/cerrar la app local
scripts/sync/                    Scripts del agente y sincronizacion SmartPOS
scripts/legacy/                  Scripts antiguos conservados como respaldo
descargar_historico.py           Descarga/mezcla datos SmartPOS
sincronizar_smartpos_railway.py  Actualiza historico y sube a Railway
Dockerfile                       Build del backend en Railway
railway.json                     Configuracion de deploy Railway
requirements.txt                 Dependencias Python del backend/sync
```

## Desarrollo local

```powershell
.\scripts\dev\iniciar_app.bat
```

Servicios locales:

- Frontend: http://localhost:5173
- Backend: http://localhost:8002/docs

Para cerrar:

```powershell
.\scripts\dev\cerrar_app.bat
```

## Sincronizacion

Ejecutar sincronizacion manual:

```powershell
.\scripts\sync\sincronizar_ahora.bat
```

Habilitar actualizacion desde la web usando este PC:

```powershell
.\scripts\sync\iniciar_agente_sync.bat
```

Con esa ventana abierta, el boton `Actualizar desde este PC` en Vercel llama a
`http://127.0.0.1:8765`, ejecuta `sincronizar_smartpos_railway.py`, sube el
historico actualizado al volumen de Railway y espera a que el backend vuelva a
responder. Para cerrarlo:

```powershell
.\scripts\sync\cerrar_agente_sync.bat
```

Programar sincronizacion diaria:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\sync\programar_sync_railway.ps1
```

## Deploy

Railway usa `railway.json` con builder `DOCKERFILE` y arranca:

```bash
python -m backend.serve
```

Vercel debe usar:

```text
Root Directory: frontend
Build Command: npm run build
Output Directory: dist
Environment: VITE_API_URL=https://farmanalitics-production.up.railway.app
```

## Notas

- `.env`, `.venv`, `frontend/node_modules`, `frontend/dist`, logs y Parquet
  locales no se suben al repo.
- `data/historico/_backups` conserva respaldos locales recientes para rollback.
- `config.py` se mantiene porque el backend aun importa constantes de negocio.
