# Farma Analytics

Aplicacion principal:

- Backend: FastAPI en `backend/`
- Frontend: Vue/Vite en `frontend/`

La app Streamlit de `app.py` queda como version legado/local para referencia. Para despliegue en Railway y Vercel usar FastAPI + Vue.

## Backend

```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

## Frontend

```bash
cd frontend
npm install
npm run dev
```

En Vercel configurar `VITE_API_URL` con la URL publica del backend en Railway.
