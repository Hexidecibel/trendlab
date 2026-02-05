"""Open-Meteo weather adapter — historical weather data for any location."""

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

# Open-Meteo APIs (free, no auth required)
OPEN_METEO_HISTORICAL = "https://archive-api.open-meteo.com/v1/archive"
OPEN_METEO_GEOCODING = "https://geocoding-api.open-meteo.com/v1/search"

# Weather metrics (daily aggregations)
DAILY_METRICS = [
    ("temperature_2m_max", "Max Temperature", "°C"),
    ("temperature_2m_min", "Min Temperature", "°C"),
    ("temperature_2m_mean", "Mean Temperature", "°C"),
    ("precipitation_sum", "Precipitation", "mm"),
    ("rain_sum", "Rain", "mm"),
    ("snowfall_sum", "Snowfall", "cm"),
    ("precipitation_hours", "Precipitation Hours", "hours"),
    ("windspeed_10m_max", "Max Wind Speed", "km/h"),
    ("windgusts_10m_max", "Max Wind Gusts", "km/h"),
    ("winddirection_10m_dominant", "Dominant Wind Direction", "°"),
    ("shortwave_radiation_sum", "Solar Radiation", "MJ/m²"),
    ("et0_fao_evapotranspiration", "Evapotranspiration", "mm"),
]

# Temperature units
TEMP_UNITS = [
    ("celsius", "Celsius (°C)"),
    ("fahrenheit", "Fahrenheit (°F)"),
]

# Wind speed units
WIND_UNITS = [
    ("kmh", "km/h"),
    ("mph", "mph"),
    ("ms", "m/s"),
    ("kn", "knots"),
]

# Precipitation units
PRECIP_UNITS = [
    ("mm", "Millimeters"),
    ("inch", "Inches"),
]

METRIC_LABELS = {m[0]: m[1] for m in DAILY_METRICS}
METRIC_UNITS = {m[0]: m[2] for m in DAILY_METRICS}


class WeatherAdapter(DataAdapter):
    name = "weather"
    description = "Historical weather data for any location (Open-Meteo)"
    aggregation_method = "mean"

    def form_fields(self) -> list[FormField]:
        return [
            FormField(
                name="location",
                label="Location",
                field_type="autocomplete",
                placeholder="New York, London, Tokyo...",
            ),
            FormField(
                name="metric",
                label="Metric",
                field_type="select",
                options=[
                    FormFieldOption(value=m, label=lbl) for m, lbl, _ in DAILY_METRICS
                ],
            ),
            FormField(
                name="temp_unit",
                label="Temperature Unit",
                field_type="select",
                options=[FormFieldOption(value=v, label=lbl) for v, lbl in TEMP_UNITS],
            ),
            FormField(
                name="wind_unit",
                label="Wind Speed Unit",
                field_type="select",
                options=[FormFieldOption(value=v, label=lbl) for v, lbl in WIND_UNITS],
            ),
            FormField(
                name="precip_unit",
                label="Precipitation Unit",
                field_type="select",
                options=[
                    FormFieldOption(value=v, label=lbl) for v, lbl in PRECIP_UNITS
                ],
            ),
        ]

    async def lookup(self, lookup_type: str, **kwargs: str) -> list[LookupItem]:
        """Search for locations using Open-Meteo geocoding."""
        if lookup_type != "location":
            return []

        search_term = kwargs.get("search", kwargs.get("location", ""))
        if not search_term or len(search_term) < 2:
            return []

        params = {
            "name": search_term,
            "count": 10,
            "language": "en",
            "format": "json",
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(
                OPEN_METEO_GEOCODING,
                params=params,
                timeout=10.0,
            )
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError:
                logger.warning("Geocoding failed: %s", response.status_code)
                return []

        data = response.json()
        results = data.get("results", [])

        items = []
        for r in results:
            name = r.get("name", "")
            admin1 = r.get("admin1", "")  # State/province
            country = r.get("country", "")
            lat = r.get("latitude")
            lon = r.get("longitude")

            if lat is None or lon is None:
                continue

            # Format: lat,lon as value (used for API call)
            value = f"{lat},{lon}"

            # Format label with location hierarchy
            parts = [name]
            if admin1:
                parts.append(admin1)
            if country:
                parts.append(country)
            label = ", ".join(parts)

            items.append(LookupItem(value=value, label=label))

        return items

    async def fetch(
        self,
        query: str,
        start: datetime.date | None = None,
        end: datetime.date | None = None,
    ) -> TimeSeries:
        """Fetch historical weather data from Open-Meteo.

        Query format: lat,lon:metric:temp_unit:wind_unit:precip_unit
        Example: 40.7128,-74.006:temperature_2m_max:celsius:kmh:mm
        """
        parts = query.split(":")
        if len(parts) != 5:
            raise ValueError(
                f"Invalid query format: '{query}'. "
                "Expected 'lat,lon:metric:temp_unit:wind_unit:precip_unit' "
                "(e.g. '40.7128,-74.006:temperature_2m_max:celsius:kmh:mm')"
            )

        location, metric, temp_unit, wind_unit, precip_unit = parts

        # Parse coordinates
        try:
            lat_str, lon_str = location.split(",")
            lat = float(lat_str)
            lon = float(lon_str)
        except (ValueError, AttributeError):
            raise ValueError(
                f"Invalid coordinates: '{location}'. "
                "Expected 'latitude,longitude' (e.g. '40.7128,-74.006')"
            )

        # Validate metric
        valid_metrics = [m[0] for m in DAILY_METRICS]
        if metric not in valid_metrics:
            raise ValueError(
                f"Invalid metric: '{metric}'. Valid: {', '.join(valid_metrics)}"
            )

        # Validate units
        valid_temp = [t[0] for t in TEMP_UNITS]
        if temp_unit not in valid_temp:
            raise ValueError(
                f"Invalid temp unit: '{temp_unit}'. Valid: {', '.join(valid_temp)}"
            )

        valid_wind = [w[0] for w in WIND_UNITS]
        if wind_unit not in valid_wind:
            raise ValueError(
                f"Invalid wind unit: '{wind_unit}'. Valid: {', '.join(valid_wind)}"
            )

        valid_precip = [p[0] for p in PRECIP_UNITS]
        if precip_unit not in valid_precip:
            raise ValueError(
                f"Invalid precip unit: '{precip_unit}'. "
                f"Valid: {', '.join(valid_precip)}"
            )

        # Default date range: last 2 years (Open-Meteo has data from 1940)
        if not end:
            # Historical API has ~5 day delay
            end = datetime.date.today() - datetime.timedelta(days=5)
        if not start:
            start = end - datetime.timedelta(days=730)  # ~2 years

        # Build API request
        params = {
            "latitude": lat,
            "longitude": lon,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "daily": metric,
            "temperature_unit": temp_unit,
            "windspeed_unit": wind_unit,
            "precipitation_unit": precip_unit,
            "timezone": "auto",
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(
                OPEN_METEO_HISTORICAL,
                params=params,
                timeout=30.0,
            )
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError:
                if response.status_code == 400:
                    error_data = response.json()
                    reason = error_data.get("reason", "Invalid request")
                    raise ValueError(f"Weather API error: {reason}") from None
                raise

        data = response.json()
        daily = data.get("daily", {})
        dates = daily.get("time", [])
        values = daily.get(metric, [])

        if not dates or not values:
            return TimeSeries(
                source=self.name,
                query=query,
                points=[],
                metadata={
                    "latitude": lat,
                    "longitude": lon,
                    "metric": metric,
                    "metric_label": METRIC_LABELS.get(metric, metric),
                    "unit": METRIC_UNITS.get(metric, ""),
                },
            )

        # Build points
        points = []
        for date_str, val in zip(dates, values):
            if val is None:
                continue
            dt = datetime.date.fromisoformat(date_str)
            points.append(DataPoint(date=dt, value=float(val)))

        # Apply date filters (in case API returned extra data)
        if start:
            points = [p for p in points if p.date >= start]
        if end:
            points = [p for p in points if p.date <= end]

        points.sort(key=lambda p: p.date)

        # Get location info from response
        timezone = data.get("timezone", "")
        elevation = data.get("elevation", 0)

        return TimeSeries(
            source=self.name,
            query=query,
            points=points,
            metadata={
                "latitude": lat,
                "longitude": lon,
                "metric": metric,
                "metric_label": METRIC_LABELS.get(metric, metric),
                "unit": METRIC_UNITS.get(metric, ""),
                "temp_unit": temp_unit,
                "wind_unit": wind_unit,
                "precip_unit": precip_unit,
                "timezone": timezone,
                "elevation": elevation,
            },
        )
