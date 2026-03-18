"""Google Trends adapter — search interest over time."""

import asyncio
import datetime

from app.data.base import DataAdapter
from app.logging_config import get_logger
from app.models.schemas import (
    DataPoint,
    FormField,
    FormFieldOption,
    TimeSeries,
)

logger = get_logger(__name__)

# Module-level semaphore to avoid Google rate limits
_semaphore = asyncio.Semaphore(1)

# Available timeframes
TIMEFRAMES = [
    ("today 12-m", "Past 12 Months"),
    ("today 5-y", "Past 5 Years"),
    ("today 3-m", "Past 3 Months"),
    ("today 1-m", "Past Month"),
    ("all", "All Time (2004-present)"),
]


class GoogleTrendsAdapter(DataAdapter):
    name = "google_trends"
    description = "Google Trends search interest"
    aggregation_method = "mean"

    def form_fields(self) -> list[FormField]:
        return [
            FormField(
                name="keyword",
                label="Keyword",
                field_type="text",
                placeholder="machine learning",
            ),
            FormField(
                name="timeframe",
                label="Timeframe",
                field_type="select",
                options=[
                    FormFieldOption(value=v, label=lbl) for v, lbl in TIMEFRAMES
                ],
            ),
            FormField(
                name="geo",
                label="Region",
                field_type="text",
                placeholder="US, GB, etc. (blank for worldwide)",
            ),
        ]

    async def fetch(
        self,
        query: str,
        start: datetime.date | None = None,
        end: datetime.date | None = None,
    ) -> TimeSeries:
        """Fetch search interest data from Google Trends.

        Query format: keyword:timeframe:geo
        Example: machine learning:today 12-m:US
        """
        parts = query.split(":")
        if len(parts) < 1 or not parts[0].strip():
            raise ValueError(
                "Missing keyword. Query format: 'keyword:timeframe:geo' "
                "(e.g. 'machine learning:today 12-m:US')"
            )

        keyword = parts[0].strip()
        timeframe = (
            parts[1].strip()
            if len(parts) > 1 and parts[1].strip()
            else "today 12-m"
        )
        geo = parts[2].strip() if len(parts) > 2 and parts[2].strip() else ""

        # Validate timeframe
        valid_timeframes = [t[0] for t in TIMEFRAMES]
        if timeframe not in valid_timeframes:
            raise ValueError(
                f"Invalid timeframe: '{timeframe}'. "
                f"Valid: {', '.join(valid_timeframes)}"
            )

        async with _semaphore:
            try:
                df = await asyncio.to_thread(
                    self._fetch_sync, keyword, timeframe, geo
                )
            except Exception as exc:
                # Check for rate limit errors
                exc_type = type(exc).__name__
                if exc_type == "TooManyRequestsError" or "429" in str(exc):
                    raise ValueError(
                        "Google Trends rate limit exceeded. "
                        "Please wait and try again."
                    ) from exc
                raise

        # Convert DataFrame to DataPoints
        points = []
        for date_idx, row in df.iterrows():
            dt = date_idx.date() if hasattr(date_idx, "date") else date_idx
            value = float(row[keyword])
            points.append(DataPoint(date=dt, value=value))

        # Apply date filters
        if start:
            points = [p for p in points if p.date >= start]
        if end:
            points = [p for p in points if p.date <= end]

        points.sort(key=lambda p: p.date)

        return TimeSeries(
            source=self.name,
            query=query,
            points=points,
            metadata={
                "keyword": keyword,
                "timeframe": timeframe,
                "geo": geo or "worldwide",
            },
        )

    def _fetch_sync(self, keyword: str, timeframe: str, geo: str):
        """Synchronous pytrends call, run via asyncio.to_thread."""
        from pytrends.request import TrendReq

        pytrends = TrendReq(hl="en-US", tz=360)
        pytrends.build_payload([keyword], timeframe=timeframe, geo=geo)
        df = pytrends.interest_over_time()

        if df.empty:
            raise ValueError(
                f"No Google Trends data found for '{keyword}' "
                f"with timeframe '{timeframe}'"
            )

        # Drop the 'isPartial' column if present
        if "isPartial" in df.columns:
            df = df.drop(columns=["isPartial"])

        return df
