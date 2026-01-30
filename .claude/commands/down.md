# Stop TrendLab Dev Server

Stop the FastAPI dev server.

## Steps

1. Kill uvicorn processes:
```bash
pkill -f "uvicorn app.main:app" || true
```

Run to stop the dev server.
