import datetime
from collections import defaultdict

from app.models.schemas import DataPoint, TimeSeries

_VALID_FREQS = {"day", "week", "month", "quarter", "season"}


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


_BUCKET_FN = {
    "week": _week_bucket,
    "month": _month_bucket,
    "quarter": _quarter_bucket,
    "season": _season_bucket,
}


def resample_series(
    ts: TimeSeries,
    freq: str | None,
    method: str = "mean",
) -> TimeSeries:
    """Resample a TimeSeries to the given frequency.

    Args:
        ts: Input time series.
        freq: One of "day", "week", "month", "quarter", "season", or None.
        method: "mean" or "sum".

    Returns:
        A new TimeSeries with aggregated points.
    """
    if freq is None or freq == "day":
        return ts

    bucket_fn = _BUCKET_FN.get(freq)
    if bucket_fn is None:
        raise ValueError(
            f"Unknown resample frequency '{freq}'. Valid: {sorted(_VALID_FREQS)}"
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
