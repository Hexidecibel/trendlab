import datetime

import httpx

from app.data.base import DataAdapter
from app.models.schemas import DataPoint, FormField, TimeSeries

COINGECKO_URL = "https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"


class CoinGeckoAdapter(DataAdapter):
    name = "crypto"
    description = "Cryptocurrency price history (USD, last 180 days)"

    def form_fields(self) -> list[FormField]:
        return [
            FormField(
                name="query",
                label="Coin ID",
                field_type="text",
                placeholder="bitcoin",
            )
        ]

    async def fetch(
        self,
        query: str,
        start: datetime.date | None = None,
        end: datetime.date | None = None,
    ) -> TimeSeries:
        url = COINGECKO_URL.format(coin_id=query)
        params = {"vs_currency": "usd", "days": "180", "interval": "daily"}

        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params)
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError:
                if response.status_code in (400, 404):
                    raise ValueError(f"Coin '{query}' not found on CoinGecko") from None
                raise

        raw_prices = response.json()["prices"]

        # Convert timestamps to dates, deduplicate (last value per date wins)
        daily: dict[datetime.date, float] = {}
        for timestamp_ms, price in raw_prices:
            dt = datetime.datetime.fromtimestamp(
                timestamp_ms / 1000, tz=datetime.timezone.utc
            )
            daily[dt.date()] = price

        points = [DataPoint(date=d, value=v) for d, v in sorted(daily.items())]

        if start:
            points = [p for p in points if p.date >= start]
        if end:
            points = [p for p in points if p.date <= end]

        return TimeSeries(
            source=self.name,
            query=query,
            points=points,
        )
