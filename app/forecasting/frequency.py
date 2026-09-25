"""Series frequency inference and calendar-aware forecast date generation."""

import datetime
from dataclasses import dataclass

import numpy as np

try:  # python-dateutil ships with pandas; fall back to manual month math
    from dateutil.relativedelta import relativedelta
except ImportError:  # pragma: no cover
    relativedelta = None

# Median gap (days) ranges that snap to calendar-month steps
_MONTH_SNAPS: list[tuple[float, float, int]] = [
    (27.0, 32.0, 1),  # monthly
    (88.0, 93.0, 3),  # quarterly
    (180.0, 185.0, 6),  # half-yearly
    (360.0, 367.0, 12),  # yearly
]


@dataclass(frozen=True)
class Step:
    """A series step: either N calendar months or N days."""

    months: int = 0
    days: int = 0

    @property
    def label(self) -> str:
        if self.months == 12:
            return "year"
        if self.months == 3:
            return "quarter"
        if self.months:
            return "month" if self.months == 1 else f"{self.months} months"
        if self.days == 7:
            return "week"
        return "day" if self.days == 1 else f"{self.days} days"


def infer_step(dates: list[datetime.date]) -> Step:
    """Infer the series step from the median gap between dates."""
    if len(dates) < 2:
        return Step(days=1)
    gaps = np.array(
        [(b - a).days for a, b in zip(dates, dates[1:])], dtype=np.float64
    )
    gaps = gaps[gaps > 0]
    if len(gaps) == 0:
        return Step(days=1)
    median = float(np.median(gaps))
    for lo, hi, months in _MONTH_SNAPS:
        if lo <= median <= hi:
            return Step(months=months)
    return Step(days=max(1, int(round(median))))


def _add_months(d: datetime.date, months: int) -> datetime.date:
    if relativedelta is not None:
        return d + relativedelta(months=months)
    total = d.month - 1 + months
    year = d.year + total // 12
    month = total % 12 + 1
    # Clamp day to the last valid day of the target month
    for day in (d.day, 30, 29, 28):
        try:
            return datetime.date(year, month, min(d.day, day))
        except ValueError:
            continue
    return datetime.date(year, month, 28)  # pragma: no cover


def future_dates(
    dates: list[datetime.date], horizon: int, step: Step | None = None
) -> list[datetime.date]:
    """``horizon`` dates after ``dates[-1]``, spaced by the series step.

    Month steps are anchored on the last date (Jan 31 -> Feb 29 -> Mar 31).
    """
    if not dates or horizon <= 0:
        return []
    step = step or infer_step(dates)
    last = dates[-1]
    if step.months:
        return [_add_months(last, step.months * k) for k in range(1, horizon + 1)]
    return [
        last + datetime.timedelta(days=step.days * k) for k in range(1, horizon + 1)
    ]


def cap_horizon(horizon: int, series_length: int) -> int:
    """Limit the horizon (in periods) to half the series length, min 1."""
    return max(1, min(int(horizon), series_length // 2))
