# TrendLab Plugins

Drop custom data adapter `.py` files here. They will be auto-loaded on server startup.

## Quick Start

Create a file like `my_adapter.py`:

```python
import datetime
from app.data.base import DataAdapter
from app.models.schemas import DataPoint, TimeSeries

class MyDataAdapter(DataAdapter):
    name = "my_source"
    description = "My custom data source"

    async def fetch(self, query: str, start=None, end=None) -> TimeSeries:
        # Your data fetching logic here
        return TimeSeries(
            source=self.name,
            query=query,
            points=[DataPoint(date=datetime.date.today(), value=42.0)],
        )
```

Restart the server and check `/api/sources` to verify it loaded.

## Optional: Custom Resample Periods

If your data source has domain-specific time periods (sports seasons, fiscal years, etc.), you can define custom resample options:

```python
from app.models.schemas import ResamplePeriod

class MyDataAdapter(DataAdapter):
    # ... name, description, fetch() ...

    def custom_resample_periods(self) -> list[ResamplePeriod]:
        return [
            ResamplePeriod(
                value="my_period",
                label="My Custom Period",
                description="Aggregates data by my custom time period",
            ),
        ]

    def custom_resample(self, series: TimeSeries, period: str) -> TimeSeries:
        if period != "my_period":
            raise NotImplementedError(f"Unknown period: {period}")

        # Your aggregation logic here
        # Group series.points by your custom buckets
        # Return a new TimeSeries with aggregated points

        return TimeSeries(
            source=series.source,
            query=series.query,
            points=aggregated_points,
            metadata={**series.metadata, "resample": period},
        )
```

Custom periods will appear in the Resample dropdown when your source is selected.

See the main README.md for full documentation.
