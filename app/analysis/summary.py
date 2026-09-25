"""Plain-English change summaries built from regimes and structural breaks."""

import datetime

import numpy as np

from app.analysis.trend_metrics import STABLE_PCT_PER_MONTH, slope_pct_per_month
from app.models.schemas import Regime, StructuralBreak, TimeSeries

MAX_SUMMARY_LINES = 4

# A level shift across a break must be at least this big (%) to be reported
JUMP_MIN_PCT = 20.0

# Regimes shorter than this can't support a slope statement
MIN_REGIME_POINTS = 5
MIN_REGIME_DAYS = 28

# Points either side of a break used to measure a level shift
JUMP_WINDOW_POINTS = 7


def format_date(d: datetime.date | str) -> str:
    """Format as e.g. "Mar 3, 2026"."""
    if isinstance(d, str):
        d = datetime.date.fromisoformat(d)
    return f"{d:%b} {d.day}, {d.year}"


def format_rate(pct: float) -> str:
    """Format a % per month rate, e.g. "+8%/mo" or "-1.5%/mo"."""
    if abs(pct) >= 10:
        return f"{pct:+.0f}%/mo"
    text = f"{pct:+.1f}"
    if text.endswith(".0"):
        text = text[:-2]
    return f"{text}%/mo"


def _kind(pct: float) -> str:
    if pct >= STABLE_PCT_PER_MONTH:
        return "rising"
    if pct <= -STABLE_PCT_PER_MONTH:
        return "falling"
    return "stable"


def _slope_line(before: float, after: float, when: str) -> str | None:
    """Describe a change in slope across a break, or None if it's minor."""
    b, a = _kind(before), _kind(after)
    diff = abs(after - before)
    if diff < STABLE_PCT_PER_MONTH:
        return None
    rb, ra = format_rate(before), format_rate(after)

    if b == "rising" and a == "rising":
        if diff < 0.25 * max(abs(before), abs(after)):
            return None
        verb = "slowed" if after < before else "accelerated"
        return f"Growth {verb} from {rb} to {ra} after {when}"
    if b == "falling" and a == "falling":
        if diff < 0.25 * max(abs(before), abs(after)):
            return None
        verb = "deepened" if after < before else "eased"
        return f"Decline {verb} from {rb} to {ra} after {when}"
    if b == "rising" and a == "falling":
        return f"Turned from growth ({rb}) to decline ({ra}) after {when}"
    if b == "falling" and a == "rising":
        return f"Recovered from decline ({rb}) to growth ({ra}) after {when}"
    if b == "stable" and a == "rising":
        return f"Started growing ({ra}) after {when}"
    if b == "stable" and a == "falling":
        return f"Started declining ({ra}) after {when}"
    if b == "rising" and a == "stable":
        return f"Growth flattened out (from {rb} to {ra}) after {when}"
    if b == "falling" and a == "stable":
        return f"Decline levelled off (from {rb} to {ra}) after {when}"
    return None


def _jump_pct(values: np.ndarray, idx: int, left: int, right: int) -> float | None:
    """Level shift (%) between the medians just before and after ``idx``."""
    w = max(1, min(JUMP_WINDOW_POINTS, left, right))
    before = values[max(0, idx - w) : idx]
    after = values[idx : idx + w]
    if len(before) == 0 or len(after) == 0:
        return None
    m0 = float(np.median(before))
    m1 = float(np.median(after))
    if m0 <= 0:
        return None
    pct = (m1 - m0) / m0 * 100.0
    return pct if np.isfinite(pct) else None


def _largest_step_near(values: np.ndarray, idx: int, rising: bool) -> int:
    """Index where the level shift near ``idx`` actually happens.

    CUSUM tends to place a break on the last point *before* a shift, so the
    reported date is pinned to the candidate (within 3 points) with the
    biggest shift between the means of the 7-point windows before and after
    it. A 7-point window always spans a whole weekly cycle, so regular
    weekend dips don't pull the date onto a Saturday.
    """
    n = len(values)
    w = JUMP_WINDOW_POINTS
    best, best_shift = idx, -np.inf
    for j in range(max(1, idx - 3), min(n, idx + 4)):
        before = values[max(0, j - w) : j]
        after = values[j : j + w]
        if len(before) == 0 or len(after) == 0:
            continue
        shift = float(np.mean(after) - np.mean(before))
        shift = shift if rising else -shift
        if shift > best_shift:
            best, best_shift = j, shift
    return best


def build_summary_lines(
    ts: TimeSeries,
    breaks: list[StructuralBreak],
    regimes: list[Regime],
) -> list[str]:
    """Plain-English change lines, most significant first (max 4)."""
    n = len(ts.points)
    if n < 2 or not regimes:
        return []

    values = np.array([p.value for p in ts.points], dtype=np.float64)
    date_index = {p.date: i for i, p in enumerate(ts.points)}

    def seg_len(r: Regime) -> int:
        s = date_index.get(datetime.date.fromisoformat(r.start_date), 0)
        e = date_index.get(datetime.date.fromisoformat(r.end_date), n - 1)
        return e - s + 1

    def long_enough(r: Regime) -> bool:
        days = (
            datetime.date.fromisoformat(r.end_date)
            - datetime.date.fromisoformat(r.start_date)
        ).days
        return seg_len(r) >= MIN_REGIME_POINTS and days >= MIN_REGIME_DAYS

    candidates: list[tuple[float, str]] = []

    for prev, nxt in zip(regimes, regimes[1:]):
        start = datetime.date.fromisoformat(nxt.start_date)
        idx = date_index.get(start)
        if idx is None:
            continue
        when = format_date(start)
        left, right = seg_len(prev), seg_len(nxt)

        jump = _jump_pct(values, idx, left, right)
        if jump is not None and abs(jump) >= JUMP_MIN_PCT:
            verb = "Jumped" if jump > 0 else "Dropped"
            step_idx = _largest_step_near(values, idx, rising=jump > 0)
            step_when = format_date(ts.points[step_idx].date)
            candidates.append(
                (abs(jump), f"{verb} {abs(jump):.0f}% around {step_when}")
            )
            # The level shift is the story; a regime slope straddling a step
            # would misreport it as a trend reversal.
            continue

        if (
            long_enough(prev)
            and long_enough(nxt)
            and prev.slope_pct_per_month is not None
            and nxt.slope_pct_per_month is not None
        ):
            line = _slope_line(prev.slope_pct_per_month, nxt.slope_pct_per_month, when)
            if line:
                score = abs(nxt.slope_pct_per_month - prev.slope_pct_per_month)
                candidates.append((score, line))

    if not candidates:
        # No notable change points: describe the period as a whole
        if len(regimes) == 1:
            pct = regimes[0].slope_pct_per_month
        else:
            pct = slope_pct_per_month([p.date for p in ts.points], values)
        if pct is not None and n >= MIN_REGIME_POINTS:
            kind = _kind(pct)
            if kind == "rising":
                text = f"Steady growth of about {format_rate(pct)} over the period"
            elif kind == "falling":
                text = f"Steady decline of about {format_rate(pct)} over the period"
            else:
                text = f"Broadly flat over the period ({format_rate(pct)})"
            candidates.append((abs(pct), text))

    candidates.sort(key=lambda c: c[0], reverse=True)
    seen: set[str] = set()
    lines: list[str] = []
    for _, text in candidates:
        if text not in seen:
            seen.add(text)
            lines.append(text)
        if len(lines) >= MAX_SUMMARY_LINES:
            break
    return lines
