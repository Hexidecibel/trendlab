import datetime
from collections import defaultdict

import httpx

from app.data.base import DataAdapter
from app.models.schemas import DataPoint, FormField, TimeSeries

PYPI_STATS_URL = "https://pypistats.org/api/packages/{package}/overall"


class PyPIAdapter(DataAdapter):
    name = "pypi"
    description = "PyPI package download counts (last 180 days)"
    aggregation_method = "sum"

    def form_fields(self) -> list[FormField]:
        return [
            FormField(
                name="query",
                label="Package Name",
                field_type="text",
                placeholder="fastapi",
            )
        ]

    async def fetch(
        self,
        query: str,
        start: datetime.date | None = None,
        end: datetime.date | None = None,
    ) -> TimeSeries:
        url = PYPI_STATS_URL.format(package=query)

        async with httpx.AsyncClient() as client:
            response = await client.get(url, params={"mirrors": "false"})
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError:
                if response.status_code == 404:
                    raise ValueError(f"Package '{query}' not found on PyPI") from None
                raise

        raw_data = response.json()["data"]

        daily_totals: dict[str, float] = defaultdict(float)
        for row in raw_data:
            daily_totals[row["date"]] += row["downloads"]

        points = [
            DataPoint(date=datetime.date.fromisoformat(d), value=v)
            for d, v in sorted(daily_totals.items())
        ]

        if start:
            points = [p for p in points if p.date >= start]
        if end:
            points = [p for p in points if p.date <= end]

        return TimeSeries(
            source=self.name,
            query=query,
            points=points,
        )
