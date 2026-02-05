import datetime
from collections import defaultdict

import httpx

from app.data.base import DataAdapter
from app.models.schemas import DataPoint, FormField, TimeSeries

NPM_DOWNLOADS_URL = "https://api.npmjs.org/downloads/range/{start}:{end}/{package}"


class NpmAdapter(DataAdapter):
    name = "npm"
    description = "npm package download counts (last 180 days)"
    aggregation_method = "sum"

    def form_fields(self) -> list[FormField]:
        return [
            FormField(
                name="query",
                label="Package Name",
                field_type="text",
                placeholder="express",
            )
        ]

    async def fetch(
        self,
        query: str,
        start: datetime.date | None = None,
        end: datetime.date | None = None,
    ) -> TimeSeries:
        # Default to last 180 days
        if end is None:
            end = datetime.date.today()
        if start is None:
            start = end - datetime.timedelta(days=180)

        url = NPM_DOWNLOADS_URL.format(
            package=query,
            start=start.isoformat(),
            end=end.isoformat(),
        )

        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=30)
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError:
                if response.status_code == 404:
                    raise ValueError(f"Package '{query}' not found on npm") from None
                raise

        data = response.json()
        downloads = data.get("downloads", [])

        # Aggregate by date (API returns daily)
        daily_totals: dict[str, float] = defaultdict(float)
        for row in downloads:
            daily_totals[row["day"]] += row["downloads"]

        points = [
            DataPoint(date=datetime.date.fromisoformat(d), value=v)
            for d, v in sorted(daily_totals.items())
        ]

        # Apply date filters
        if start:
            points = [p for p in points if p.date >= start]
        if end:
            points = [p for p in points if p.date <= end]

        return TimeSeries(
            source=self.name,
            query=query,
            points=points,
            metadata={"package": query},
        )
