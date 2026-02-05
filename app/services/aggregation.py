import datetime
from collections import defaultdict
from typing import TYPE_CHECKING

from app.models.schemas import DataPoint, TimeSeries

if TYPE_CHECKING:
    from app.data.base import DataAdapter

_STANDARD_FREQS = {"day", "week", "month", "quarter", "season", "year"}


def _week_bucket(d: datetime.date) -> datetime.date:
    """ISO week start (Monday)."""
    return d - datetime.timedelta(days=d.weekday())


def _month_bucket(d: datetime.date) -> datetime.date:
    return d.replace(day=1)


def _quarter_bucket(d: datetime.date) -> datetime.date:
    q_month = ((d.month - 1) // 3) * 3 + 1
    return datetime.date(d.year, q_month, 1)


def _season_bucket(d: datetime.date) -> datetime.date:
    return datetime.date(d.year, 1, 1)


def _year_bucket(d: datetime.date) -> datetime.date:
    return datetime.date(d.year, 1, 1)


_BUCKET_FN = {
    "week": _week_bucket,
    "month": _month_bucket,
    "quarter": _quarter_bucket,
    "season": _season_bucket,
    "year": _year_bucket,
}


def resample_series(
    ts: TimeSeries,
    freq: str | None,
    method: str = "mean",
    adapter: "DataAdapter | None" = None,
) -> TimeSeries:
    """Resample a TimeSeries to the given frequency.

    Args:
        ts: Input time series.
        freq: Standard frequency ("day", "week", "month", "quarter", "season", "year")
              or adapter-specific custom period.
        method: "mean" or "sum".
        adapter: Optional adapter for custom resample periods.

    Returns:
        A new TimeSeries with aggregated points.
    """
    if freq is None or freq == "day":
        return ts

    # Check if it's a standard frequency
    bucket_fn = _BUCKET_FN.get(freq)

    if bucket_fn is None:
        # Not a standard freq - check for adapter custom resample
        if adapter is not None:
            custom_periods = {p.value for p in adapter.custom_resample_periods()}
            if freq in custom_periods:
                return adapter.custom_resample(ts, freq)

        # Build helpful error message
        valid = sorted(_STANDARD_FREQS)
        if adapter is not None:
            custom = [p.value for p in adapter.custom_resample_periods()]
            if custom:
                valid = valid + custom
        raise ValueError(
            f"Unknown resample frequency '{freq}'. Valid: {valid}"
        )

    if not ts.points:
        return TimeSeries(
            source=ts.source,
            query=ts.query,
            points=[],
            metadata={**ts.metadata, "resample": freq},
        )

    # Group by bucket
    buckets: dict[datetime.date, list[float]] = defaultdict(list)
    for p in ts.points:
        key = bucket_fn(p.date)
        buckets[key].append(p.value)

    # Aggregate
    agg_fn = sum if method == "sum" else lambda vals: sum(vals) / len(vals)
    points = [
        DataPoint(date=bucket_date, value=agg_fn(values))
        for bucket_date, values in sorted(buckets.items())
    ]

    return TimeSeries(
        source=ts.source,
        query=ts.query,
        points=points,
        metadata={**ts.metadata, "resample": freq},
    )
