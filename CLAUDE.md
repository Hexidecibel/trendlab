# trendlab

A python and fast API ai trend building lab. Connect data sources to real world data sets and start visualizing

## Tech Stack
- Python 3.11+
- FastAPI for async web framework
- Pydantic for data validation
- Uvicorn for ASGI server

## Project Structure
```
app/
├── __init__.py
├── main.py          # FastAPI app setup
├── routers/         # API route handlers
│   └── api.py
├── models/          # Pydantic schemas
│   └── schemas.py
└── services/        # Business logic
tests/
└── test_main.py     # API tests
```

## Commands
- `uv run uvicorn app.main:app --reload` - Start dev server
- `uv run pytest` - Run tests
- `uv run ruff check .` - Lint code
- `uv run ruff format .` - Format code

## API Docs
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Development Notes
- Add routes in `app/routers/`
- Add Pydantic models in `app/models/`
- Add business logic in `app/services/`
- Environment variables in `.env`