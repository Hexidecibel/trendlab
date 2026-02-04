# Stop TrendLab Dev Server

Stop the FastAPI backend and Vite frontend dev servers.

## Steps

1. Kill all server processes:
```bash
pkill -f "uvicorn app.main:app" 2>/dev/null; pkill -f "vite" 2>/dev/null
```

Run to stop both dev servers.
