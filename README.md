# trendlab

A python and fast API ai trend building lab. Connect data sources to real world data sets and start visualizing

## Getting Started

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Install dependencies
pip install -e ".[dev]"

# Run server
uvicorn app.main:app --reload
```

Server will start at http://localhost:8000

API docs available at http://localhost:8000/docs

## Scripts

- `uvicorn app.main:app --reload` - Development server
- `pytest` - Run tests
- `ruff check .` - Lint code
- `ruff format .` - Format code