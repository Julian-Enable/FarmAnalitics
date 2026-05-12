# Farma Analytics

Aplicacion principal:

- Backend: FastAPI en `backend/`
- Frontend: Vue/Vite en `frontend/`

`app.py` es una version Streamlit de legado para referencia local. El flujo activo de desarrollo y despliegue usa FastAPI + Vue.

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

En Vercel configura `VITE_API_URL` con la URL publica del backend en Railway.
