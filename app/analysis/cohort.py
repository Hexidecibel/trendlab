"""Cohort comparison analysis: normalize, compute stats, and rank members."""

import math

from app.models.schemas import CohortMember, DataPoint, TimeSeries


def _daily_returns(points: list[DataPoint]) -> list[float]:
    """Compute daily percentage returns from a list of data points."""
    returns = []
    for i in range(1, len(points)):
        prev = points[i - 1].value
        if prev != 0:
            returns.append((points[i].value - prev) / prev * 100)
        else:
            returns.append(0.0)
    return returns


def _total_return(points: list[DataPoint]) -> float:
    """Percentage change from first to last value."""
    if not points or points[0].value == 0:
        return 0.0
    return (points[-1].value / points[0].value - 1) * 100


def _max_drawdown(points: list[DataPoint]) -> float:
    """Max peak-to-trough decline as a percentage (returned as negative)."""
    if len(points) < 2:
        return 0.0
    peak = points[0].value
    max_dd = 0.0
    for p in points:
        if p.value > peak:
            peak = p.value
        if peak != 0:
            dd = (p.value - peak) / peak * 100
            if dd < max_dd:
                max_dd = dd
    return max_dd


def _volatility(points: list[DataPoint]) -> float:
    """Standard deviation of daily returns."""
    returns = _daily_returns(points)
    if len(returns) < 2:
        return 0.0
    mean = sum(returns) / len(returns)
    variance = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
    return math.sqrt(variance)


def _normalize_points(points: list[DataPoint]) -> list[DataPoint]:
    """Normalize points to percentage change from day 1."""
    if not points or points[0].value == 0:
        return points
    first = points[0].value
    return [
        DataPoint(date=p.date, value=(p.value / first - 1) * 100)
        for p in points
    ]


def analyze_cohort(
    series_list: list[TimeSeries],
    normalize: bool = True,
) -> list[CohortMember]:
    """Analyze a cohort of time series and return ranked members."""
    members: list[CohortMember] = []

    for ts in series_list:
        points = ts.points
        total = _total_return(points)
        drawdown = _max_drawdown(points)
        vol = _volatility(points)
        normalized = _normalize_points(points) if normalize else points

        members.append(
            CohortMember(
                source=ts.source,
                query=ts.query,
                total_return=round(total, 4),
                max_drawdown=round(drawdown, 4),
                volatility=round(vol, 4),
                rank=0,  # placeholder, assigned after sorting
                normalized_points=normalized,
            )
        )

    # Rank by total_return descending
    members.sort(key=lambda m: m.total_return, reverse=True)
    for i, m in enumerate(members):
        m.rank = i + 1

    return members
