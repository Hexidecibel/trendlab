# TrendLab

AI-powered trend analysis platform for time-series data visualization and forecasting.

## Features

- **Multi-source data adapters** — PyPI downloads, crypto prices, GitHub stars, soccer stats
- **Trend analysis** — Detect momentum, seasonality, anomalies, and structural breaks
- **Forecasting** — Compare statistical models (Naive, Drift, ETS, ARIMA) with evaluation metrics
- **Natural language queries** — Describe what you want in plain English
- **Series comparison** — Overlay multiple series with normalization and transforms
- **Correlation analysis** — Pearson/Spearman coefficients with lag analysis
- **AI insights** — LLM-generated commentary via streaming SSE

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Frontend (React)                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐ │
│  │  Charts  │  │  Forms   │  │ Analysis │  │   AI Commentary  │ │
│  │(Chart.js)│  │(Dynamic) │  │  Panels  │  │    (SSE Stream)  │ │
│  └──────────┘  └──────────┘  └──────────┘  └──────────────────┘ │
└─────────────────────────────┬───────────────────────────────────┘
                              │ REST API
┌─────────────────────────────▼───────────────────────────────────┐
│                      FastAPI Backend                             │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                      API Router                             │ │
│  │  /series  /analyze  /forecast  /compare  /correlate  /nl   │ │
│  └────────────────────────────────────────────────────────────┘ │
│                              │                                   │
│  ┌───────────┐  ┌───────────▼───────────┐  ┌─────────────────┐ │
│  │   Cache   │  │    Analysis Engine    │  │   AI Layer      │ │
│  │  (SQLite) │  │ ┌───────┐ ┌────────┐  │  │  (Anthropic)    │ │
│  └───────────┘  │ │Trends │ │Forecast│  │  └─────────────────┘ │
│                 │ └───────┘ └────────┘  │                       │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │                    Data Adapters                          │ │
│  │  ┌─────┐ ┌────────┐ ┌────────┐ ┌──────┐ ┌──────────────┐ │ │
│  │  │PyPI │ │CoinGeck│ │ GitHub │ │ ASA  │ │   Football   │ │ │
│  │  └─────┘ └────────┘ └────────┘ └──────┘ └──────────────┘ │ │
│  └───────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

## Quick Start

### Using Docker (recommended)

```bash
# Clone the repository
git clone https://github.com/yourusername/trendlab.git
cd trendlab

# Copy environment template
cp .env.example .env
# Edit .env to add your API keys (optional)

# Start with docker-compose
docker-compose up --build
```

Visit http://localhost:8000

### Local Development

```bash
# Install uv (Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
uv sync

# Start backend
uv run uvicorn app.main:app --reload

# In another terminal, start frontend
cd frontend && npm install && npm run dev
```

- Backend: http://localhost:8000
- Frontend dev server: http://localhost:5173
- API docs: http://localhost:8000/docs

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | For AI features | Claude API key for natural language and insights |
| `GITHUB_TOKEN` | For GitHub adapter | GitHub personal access token |
| `FOOTBALL_DATA_TOKEN` | For football adapter | Football-Data.org API key |
| `RATE_LIMIT_ENABLED` | No | Enable rate limiting (default: true) |
| `RATE_LIMIT_PER_MINUTE` | No | Requests per minute (default: 60) |
| `LOG_LEVEL` | No | Logging level (default: INFO) |
| `LOG_FORMAT` | No | Log format: json or text (default: json) |

## Data Sources

| Source | Description | Auth Required |
|--------|-------------|---------------|
| `pypi` | Python package daily downloads | No |
| `coingecko` | Cryptocurrency price history | No |
| `github_stars` | Repository star history | Yes (token) |
| `asa` | American Soccer Analysis (MLS, NWSL, USL) | No |
| `football` | European football match data | Yes (token) |
| `weather` | Historical weather data (Open-Meteo) | No |
| `wikipedia` | Article page views | No |
| `stocks` | Stock/ETF prices (Yahoo Finance) | No |
| `npm` | npm package downloads | No |
| `csv` | Custom CSV uploads | No |

## Resampling

All endpoints support a `resample` parameter for time aggregation:

**Standard periods** (all sources):
- `week` — Weekly aggregation
- `month` — Monthly aggregation
- `quarter` — Quarterly aggregation
- `year` — Yearly aggregation

**Custom periods** (source-specific):
| Source | Period | Description |
|--------|--------|-------------|
| `asa` | `mls_season` | MLS/NWSL/USL season (calendar year) |
| `weather` | `meteorological_season` | Winter/Spring/Summer/Fall |
| `football` | `football_season` | European season (Aug-May) |

Custom periods appear in the Resample dropdown when their source is selected.

## API Endpoints

### Data
- `GET /api/sources` — List available data sources
- `GET /api/series` — Fetch time-series data
- `GET /api/lookup` — Get autocomplete values

### Analysis
- `GET /api/analyze` — Trend analysis with anomaly detection
- `GET /api/forecast` — Multi-model forecasting

### Comparison
- `POST /api/compare` — Compare 2-3 series side by side
- `POST /api/correlate` — Correlation analysis between series

### AI
- `POST /api/natural-query` — Parse natural language to query params
- `GET /api/insight` — Stream AI commentary (SSE)

### Views
- `POST /api/views` — Save a view configuration
- `GET /api/views` — List saved views
- `GET /api/views/{hash}` — Load a saved view

Full API documentation at `/docs` (Swagger UI) or `/redoc`.

## Development

```bash
# Run tests
uv run pytest

# Lint
uv run ruff check .

# Format
uv run ruff format .

# Build frontend
cd frontend && npm run build
```

## Custom Plugins

TrendLab supports community-contributed data adapters via a simple plugin system. Drop a `.py` file into the `plugins/` directory and it will be auto-loaded on startup.

### Creating a Plugin

Create a file in `plugins/` (e.g., `plugins/my_adapter.py`):

```python
import datetime
from app.data.base import DataAdapter
from app.models.schemas import DataPoint, TimeSeries

class MyDataAdapter(DataAdapter):
    name = "my_source"  # Unique identifier (used in API calls)
    description = "My custom data source"
    aggregation_method = "mean"  # or "sum" for cumulative data

    async def fetch(
        self,
        query: str,
        start: datetime.date | None = None,
        end: datetime.date | None = None,
    ) -> TimeSeries:
        # Fetch your data here (use httpx for async HTTP calls)
        # Return a TimeSeries with DataPoints

        points = [
            DataPoint(date=datetime.date(2024, 1, 1), value=100.0),
            DataPoint(date=datetime.date(2024, 1, 2), value=105.0),
        ]

        return TimeSeries(
            source=self.name,
            query=query,
            points=points,
        )
```

### Plugin Requirements

- File must be in `plugins/` directory
- File must not start with `_` (underscore files are ignored)
- Must define exactly one class extending `DataAdapter`
- Class must have `name` and `description` attributes
- Must implement the `async def fetch()` method

### Optional: Custom Form Fields

For adapters with structured queries (dropdowns, autocomplete):

```python
from app.models.schemas import FormField, FormFieldOption

class MyDataAdapter(DataAdapter):
    # ... name, description, fetch() ...

    def form_fields(self) -> list[FormField]:
        return [
            FormField(
                name="category",
                label="Category",
                field_type="select",
                options=[
                    FormFieldOption(value="a", label="Option A"),
                    FormFieldOption(value="b", label="Option B"),
                ],
            ),
            FormField(
                name="item",
                label="Item",
                field_type="text",
                placeholder="Enter item name...",
            ),
        ]
```

### Example: Simple API Adapter

```python
import datetime
import httpx
from app.data.base import DataAdapter
from app.models.schemas import DataPoint, TimeSeries

class WeatherHistoryAdapter(DataAdapter):
    name = "weather_history"
    description = "Historical weather data"
    aggregation_method = "mean"

    async def fetch(
        self,
        query: str,  # e.g., "london:temperature"
        start: datetime.date | None = None,
        end: datetime.date | None = None,
    ) -> TimeSeries:
        location, metric = query.split(":")

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://api.example.com/weather/{location}",
                params={"metric": metric, "start": str(start), "end": str(end)},
            )
            response.raise_for_status()
            data = response.json()

        points = [
            DataPoint(date=datetime.date.fromisoformat(d["date"]), value=d["value"])
            for d in data["points"]
        ]

        return TimeSeries(source=self.name, query=query, points=points)
```

Restart the server after adding plugins. Check `/api/sources` to verify your adapter is loaded.

## Project Structure

```
trendlab/
├── app/
│   ├── main.py              # FastAPI app setup
│   ├── config.py            # Settings from environment
│   ├── routers/api.py       # API endpoints
│   ├── models/schemas.py    # Pydantic models
│   ├── data/
│   │   ├── adapters/        # Built-in data source adapters
│   │   └── registry.py      # Adapter registry
│   ├── analysis/            # Trend detection modules
│   ├── forecasting/         # Forecasting models
│   ├── ai/                  # LLM integration
│   ├── services/            # Cache, transforms, aggregation
│   ├── db/                  # SQLite persistence
│   └── middleware/          # Logging, rate limiting
├── plugins/                 # Community adapter plugins (auto-loaded)
├── frontend/                # React + Vite + MUI
├── tests/                   # 378+ tests
├── Dockerfile
├── docker-compose.yml
└── pyproject.toml
```

## License

MIT
