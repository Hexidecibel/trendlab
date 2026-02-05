"""Yahoo Finance adapter — stock prices and market data."""

import datetime

import httpx

from app.data.base import DataAdapter
from app.logging_config import get_logger
from app.models.schemas import (
    DataPoint,
    FormField,
    FormFieldOption,
    LookupItem,
    TimeSeries,
)

logger = get_logger(__name__)

# Yahoo Finance query API
YF_QUOTE_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
YF_SEARCH_URL = "https://query2.finance.yahoo.com/v1/finance/search"

# Available metrics from Yahoo Finance
METRICS = [
    ("close", "Close Price"),
    ("open", "Open Price"),
    ("high", "High Price"),
    ("low", "Low Price"),
    ("volume", "Volume"),
    ("adjclose", "Adjusted Close"),
]

# Data intervals
INTERVALS = [
    ("1d", "Daily"),
    ("1wk", "Weekly"),
    ("1mo", "Monthly"),
]

# Time ranges for historical data
RANGES = [
    ("1mo", "1 Month"),
    ("3mo", "3 Months"),
    ("6mo", "6 Months"),
    ("1y", "1 Year"),
    ("2y", "2 Years"),
    ("5y", "5 Years"),
    ("max", "Max Available"),
]

# Market categories for searching
MARKET_TYPES = [
    ("equity", "Stocks"),
    ("etf", "ETFs"),
    ("mutualfund", "Mutual Funds"),
    ("currency", "Currencies"),
    ("cryptocurrency", "Crypto"),
    ("index", "Indices"),
]

METRIC_LABELS = {m[0]: m[1] for m in METRICS}


class YahooFinanceAdapter(DataAdapter):
    name = "stocks"
    description = "Stock prices, ETFs, indices, and crypto via Yahoo Finance"
    aggregation_method = "mean"

    def form_fields(self) -> list[FormField]:
        return [
            FormField(
                name="symbol",
                label="Symbol",
                field_type="autocomplete",
                placeholder="AAPL, MSFT, GOOGL...",
            ),
            FormField(
                name="metric",
                label="Metric",
                field_type="select",
                options=[FormFieldOption(value=m, label=lbl) for m, lbl in METRICS],
            ),
            FormField(
                name="interval",
                label="Interval",
                field_type="select",
                options=[FormFieldOption(value=v, label=lbl) for v, lbl in INTERVALS],
            ),
            FormField(
                name="range",
                label="History",
                field_type="select",
                options=[FormFieldOption(value=v, label=lbl) for v, lbl in RANGES],
            ),
        ]

    async def lookup(self, lookup_type: str, **kwargs: str) -> list[LookupItem]:
        """Search for stock symbols."""
        if lookup_type != "symbol":
            return []

        search_term = kwargs.get("search", kwargs.get("symbol", ""))
        if not search_term or len(search_term) < 1:
            return []

        params = {
            "q": search_term,
            "quotesCount": 10,
            "newsCount": 0,
            "enableFuzzyQuery": "true",
            "quotesQueryId": "tss_match_phrase_query",
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(
                YF_SEARCH_URL,
                params=params,
                headers={
                    "User-Agent": "TrendLab/1.0",
                },
                timeout=10.0,
            )
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError:
                logger.warning("Yahoo Finance search failed: %s", response.status_code)
                return []

        data = response.json()
        quotes = data.get("quotes", [])

        results = []
        for quote in quotes:
            symbol = quote.get("symbol", "")
            name = quote.get("shortname") or quote.get("longname") or symbol
            exchange = quote.get("exchange", "")

            # Format label with exchange info
            if exchange:
                label = f"{symbol} - {name} ({exchange})"
            else:
                label = f"{symbol} - {name}"

            results.append(LookupItem(value=symbol, label=label))

        return results

    async def fetch(
        self,
        query: str,
        start: datetime.date | None = None,
        end: datetime.date | None = None,
    ) -> TimeSeries:
        """Fetch stock data from Yahoo Finance.

        Query format: symbol:metric:interval:range
        Example: AAPL:close:1d:1y
        """
        parts = query.split(":")
        if len(parts) != 4:
            raise ValueError(
                f"Invalid query format: '{query}'. "
                "Expected 'symbol:metric:interval:range' "
                "(e.g. 'AAPL:close:1d:1y')"
            )

        symbol, metric, interval, range_val = parts
        symbol = symbol.upper()

        # Validate metric
        valid_metrics = [m[0] for m in METRICS]
        if metric not in valid_metrics:
            raise ValueError(
                f"Invalid metric: '{metric}'. Valid: {', '.join(valid_metrics)}"
            )

        # Validate interval
        valid_intervals = [i[0] for i in INTERVALS]
        if interval not in valid_intervals:
            raise ValueError(
                f"Invalid interval: '{interval}'. Valid: {', '.join(valid_intervals)}"
            )

        # Validate range
        valid_ranges = [r[0] for r in RANGES]
        if range_val not in valid_ranges:
            raise ValueError(
                f"Invalid range: '{range_val}'. Valid: {', '.join(valid_ranges)}"
            )

        # Build API request
        url = YF_QUOTE_URL.format(symbol=symbol)
        params = {
            "interval": interval,
            "range": range_val,
            "includeAdjustedClose": "true",
        }

        # If custom date range provided, use period1/period2 instead of range
        if start and end:
            params.pop("range", None)
            params["period1"] = int(
                datetime.datetime.combine(
                    start, datetime.time.min, tzinfo=datetime.timezone.utc
                ).timestamp()
            )
            params["period2"] = int(
                datetime.datetime.combine(
                    end, datetime.time.max, tzinfo=datetime.timezone.utc
                ).timestamp()
            )

        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                params=params,
                headers={
                    "User-Agent": "TrendLab/1.0",
                },
                timeout=30.0,
            )
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError:
                if response.status_code == 404:
                    raise ValueError(f"Symbol '{symbol}' not found") from None
                raise

        data = response.json()

        # Navigate Yahoo Finance response structure
        chart = data.get("chart", {})
        result = chart.get("result")
        if not result:
            error = chart.get("error", {})
            msg = error.get("description", "Unknown error")
            raise ValueError(f"Yahoo Finance error: {msg}")

        result = result[0]
        timestamps = result.get("timestamp", [])
        indicators = result.get("indicators", {})
        quote_data = indicators.get("quote", [{}])[0]
        adjclose_data = indicators.get("adjclose", [{}])

        # Map metric to data array
        if metric == "adjclose" and adjclose_data:
            values = adjclose_data[0].get("adjclose", [])
        else:
            values = quote_data.get(metric, [])

        if not timestamps or not values:
            return TimeSeries(
                source=self.name,
                query=query,
                points=[],
                metadata={
                    "symbol": symbol,
                    "metric": metric,
                    "metric_label": METRIC_LABELS.get(metric, metric),
                    "interval": interval,
                    "range": range_val,
                },
            )

        # Build points
        points = []
        for ts, val in zip(timestamps, values):
            if val is None:
                continue
            dt = datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc).date()
            points.append(DataPoint(date=dt, value=float(val)))

        # Apply date filters
        if start:
            points = [p for p in points if p.date >= start]
        if end:
            points = [p for p in points if p.date <= end]

        points.sort(key=lambda p: p.date)

        # Get currency and name from meta
        meta = result.get("meta", {})
        currency = meta.get("currency", "USD")
        name = meta.get("shortName") or meta.get("longName") or symbol

        return TimeSeries(
            source=self.name,
            query=query,
            points=points,
            metadata={
                "symbol": symbol,
                "name": name,
                "metric": metric,
                "metric_label": METRIC_LABELS.get(metric, metric),
                "interval": interval,
                "range": range_val,
                "currency": currency,
            },
        )
