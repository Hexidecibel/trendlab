import re

from app.models.schemas import DataPoint, TimeSeries


def _rolling_avg(ts: TimeSeries, window: int) -> TimeSeries:
    """N-point rolling average, dropping leading incomplete windows."""
    if window > len(ts.points):
        return TimeSeries(
            source=ts.source, query=ts.query, points=[], metadata=dict(ts.metadata)
        )

    points: list[DataPoint] = []
    values = [p.value for p in ts.points]
    for i in range(window - 1, len(values)):
        avg = sum(values[i - window + 1 : i + 1]) / window
        points.append(DataPoint(date=ts.points[i].date, value=avg))

    return TimeSeries(
        source=ts.source, query=ts.query, points=points, metadata=dict(ts.metadata)
    )


def _pct_change(ts: TimeSeries) -> TimeSeries:
    """Period-over-period percentage change, dropping zero-division points."""
    points: list[DataPoint] = []
    for i in range(1, len(ts.points)):
        prev = ts.points[i - 1].value
        if prev == 0.0:
            continue
        change = (ts.points[i].value - prev) / prev * 100.0
        points.append(DataPoint(date=ts.points[i].date, value=change))

    return TimeSeries(
        source=ts.source, query=ts.query, points=points, metadata=dict(ts.metadata)
    )


def _cumulative(ts: TimeSeries) -> TimeSeries:
    """Running cumulative sum."""
    total = 0.0
    points: list[DataPoint] = []
    for p in ts.points:
        total += p.value
        points.append(DataPoint(date=p.date, value=total))

    return TimeSeries(
        source=ts.source, query=ts.query, points=points, metadata=dict(ts.metadata)
    )


def _normalize(ts: TimeSeries) -> TimeSeries:
    """Min-max normalize to [0, 1]."""
    if not ts.points:
        return ts

    values = [p.value for p in ts.points]
    lo, hi = min(values), max(values)
    span = hi - lo

    if span == 0.0:
        points = [DataPoint(date=p.date, value=0.0) for p in ts.points]
    else:
        points = [
            DataPoint(date=p.date, value=(p.value - lo) / span) for p in ts.points
        ]

    return TimeSeries(
        source=ts.source, query=ts.query, points=points, metadata=dict(ts.metadata)
    )


def _diff(ts: TimeSeries) -> TimeSeries:
    """First difference."""
    points = [
        DataPoint(
            date=ts.points[i].date,
            value=ts.points[i].value - ts.points[i - 1].value,
        )
        for i in range(1, len(ts.points))
    ]

    return TimeSeries(
        source=ts.source, query=ts.query, points=points, metadata=dict(ts.metadata)
    )


_ROLLING_RE = re.compile(r"^rolling_avg_(\d+)d$")

_SIMPLE_TRANSFORMS: dict[str, callable] = {
    "pct_change": _pct_change,
    "cumulative": _cumulative,
    "normalize": _normalize,
    "diff": _diff,
}


def _resolve_transform(name: str):
    """Resolve a transform name to a callable."""
    if name in _SIMPLE_TRANSFORMS:
        return _SIMPLE_TRANSFORMS[name]

    m = _ROLLING_RE.match(name)
    if m:
        window = int(m.group(1))
        return lambda ts: _rolling_avg(ts, window)

    raise ValueError(f"Unknown transform '{name}'. Valid: {sorted(_SIMPLE_TRANSFORMS)}")


def apply_transforms(ts: TimeSeries, apply_str: str) -> TimeSeries:
    """Parse pipe-delimited transform string and apply in order."""
    if not apply_str:
        return ts

    names = [s.strip() for s in apply_str.split("|") if s.strip()]
    if not names:
        return ts

    for name in names:
        fn = _resolve_transform(name)
        ts = fn(ts)

    ts = TimeSeries(
        source=ts.source,
        query=ts.query,
        points=ts.points,
        metadata={**ts.metadata, "transforms": names},
    )
    return ts
