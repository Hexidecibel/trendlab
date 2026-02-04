# Start TrendLab Dev Server

Start the FastAPI backend and Vite frontend dev servers with hot reload.

## Steps

1. Kill any existing server processes:
```bash
pkill -f "uvicorn app.main:app" 2>/dev/null; pkill -f "vite" 2>/dev/null; sleep 1
```

2. Start the backend dev server (background):
```bash
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

3. Start the frontend dev server (background):
```bash
cd frontend && npm run dev
```

Run step 1 first, then start both servers in the background. Confirm both are running before reporting back.

- Backend API docs: http://localhost:8000/docs
- Frontend: http://localhost:5173/
