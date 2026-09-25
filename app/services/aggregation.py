import datetime
from collections import defaultdict
from typing import TYPE_CHECKING

from app.models.schemas import DataPoint, TimeSeries

if TYPE_CHECKING:
    from app.data.base import DataAdapter

_STANDARD_FREQS = {"day", "week", "month", "quarter", "year"}

# Legacy values that map onto a standard frequency. "season" used to be its own
# option but produced buckets identical to "year".
_FREQ_ALIASES = {"season": "year", "seasonal": "year"}


def _week_bucket(d: datetime.date) -> datetime.date:
    """ISO week start (Monday)."""
    return d - datetime.timedelta(days=d.weekday())


def _month_bucket(d: datetime.date) -> datetime.date:
    return d.replace(day=1)


def _quarter_bucket(d: datetime.date) -> datetime.date:
    q_month = ((d.month - 1) // 3) * 3 + 1
    return datetime.date(d.year, q_month, 1)


def _year_bucket(d: datetime.date) -> datetime.date:
    return datetime.date(d.year, 1, 1)


def _next_bucket(freq: str, start: datetime.date) -> datetime.date:
    """First day of the bucket following the one starting at ``start``."""
    if freq == "week":
        return start + datetime.timedelta(days=7)
    if freq == "year":
        return datetime.date(start.year + 1, 1, 1)
    months = 3 if freq == "quarter" else 1
    m = start.month - 1 + months
    return datetime.date(start.year + m // 12, m % 12 + 1, 1)


# A summed bucket at either end of the series is dropped when the data covers
# less than this share of its calendar period (see _drop_partial_edges). A
# sum falls in proportion to missing days, so even a 4-of-7-day week reads as
# a 43% crash; only near-complete edge buckets are kept.
MIN_EDGE_COVERAGE = 0.9


def _drop_partial_edges(
    freq: str,
    buckets: dict[datetime.date, list[float]],
    first: datetime.date,
    last: datetime.date,
    step_days: int,
) -> tuple[dict[datetime.date, list[float]], list[datetime.date]]:
    """Drop a first/last bucket that the data only partly covers.

    Summing daily counts into e.g. months makes a March with 5 days of data
    look like a collapse (or, at the start, a series that "explodes" into its
    first full month). Only the two edge buckets can be partial: coverage is
    measured on the calendar -- from the series' first date to the bucket end,
    and from the bucket start to the last date plus one native step (so a
    monthly source dated on the 1st still covers its whole month). Gaps inside
    the data are not counted against coverage, so sparse sources (e.g. GitHub
    stars, which only has days with a star) are not penalised.

    Dropping is preferred over scaling up: a scaled value is an estimate that
    looks like data, and a missing edge bucket is self-explanatory. Edge
    buckets are kept if dropping them would leave fewer than 2 buckets.
    """
    keys = sorted(buckets)
    if len(keys) < 3:
        return buckets, []

    def coverage(start: datetime.date, lo: datetime.date, hi: datetime.date) -> float:
        end = _next_bucket(freq, start)
        period = (end - start).days
        covered = (min(hi, end) - max(lo, start)).days
        return covered / period if period > 0 else 1.0

    last_excl = last + datetime.timedelta(days=max(1, step_days))
    drop: list[datetime.date] = []
    if coverage(keys[0], first, last_excl) < MIN_EDGE_COVERAGE:
        drop.append(keys[0])
    if coverage(keys[-1], first, last_excl) < MIN_EDGE_COVERAGE:
        drop.append(keys[-1])
    if not drop or len(keys) - len(drop) < 2:
        return buckets, []
    return {k: v for k, v in buckets.items() if k not in drop}, drop


_BUCKET_FN = {
    "week": _week_bucket,
    "month": _month_bucket,
    "quarter": _quarter_bucket,
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
        freq: Standard frequency ("day", "week", "month", "quarter", "year")
              or adapter-specific custom period. The legacy value "season"
              (or "seasonal") is treated as "year".
        method: "mean" or "sum".
        adapter: Optional adapter for custom resample periods.

    Returns:
        A new TimeSeries with aggregated points.
    """
    if freq is None or freq == "day":
        return ts

    freq = _FREQ_ALIASES.get(freq, freq)

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
        raise ValueError(f"Unknown resample frequency '{freq}'. Valid: {valid}")

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

    dropped: list[datetime.date] = []
    if method == "sum":
        dates = [p.date for p in ts.points]
        gaps = sorted((b - a).days for a, b in zip(dates, dates[1:]) if b > a)
        step_days = gaps[len(gaps) // 2] if gaps else 1
        buckets, dropped = _drop_partial_edges(
            freq, buckets, min(dates), max(dates), step_days
        )

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
        metadata={
            **ts.metadata,
            "resample": freq,
            **(
                {"partial_buckets_dropped": [d.isoformat() for d in dropped]}
                if dropped
                else {}
            ),
        },
    )
