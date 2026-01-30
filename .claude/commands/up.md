# Start TrendLab Dev Server

Start the FastAPI dev server with hot reload.

## Steps

1. Kill any existing uvicorn processes:
```bash
pkill -f "uvicorn app.main:app" 2>/dev/null; sleep 1
```

2. Start the dev server:
```bash
cd /Users/chriscushman/local/src/trendlab && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Run commands in sequence. The server runs in foreground with hot reload on port 8000.

API docs available at http://localhost:8000/docs
