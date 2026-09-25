"""Level-shift helpers shared by trend momentum and the change summaries."""

import datetime

import numpy as np

# Points either side of a break used to measure a level shift
JUMP_WINDOW_POINTS = 7

# A level shift across a break must be at least this big (%) to be reported
JUMP_MIN_PCT = 20.0


def format_date(d: datetime.date | str) -> str:
    """Format as e.g. "Mar 3, 2026"."""
    if isinstance(d, str):
        d = datetime.date.fromisoformat(d)
    return f"{d:%b} {d.day}, {d.year}"


def format_short_date(d: datetime.date) -> str:
    """Format as e.g. "Mar 3" (no year)."""
    return f"{d:%b} {d.day}"


def jump_pct(values: np.ndarray, idx: int, left: int, right: int) -> float | None:
    """Level shift (%) between the medians just before and after ``idx``.

    ``left``/``right`` are how many points the segments either side hold, so
    the comparison window never reaches past a neighbouring break.
    """
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


def largest_step_near(values: np.ndarray, idx: int, rising: bool) -> int:
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


def pin_step_indices(values: np.ndarray, break_indices: list[int]) -> list[int]:
    """Move each break with a large level shift onto the step itself.

    Returns one index per input index (same order). Breaks without a
    >= ``JUMP_MIN_PCT`` shift are left where they are.
    """
    n = len(values)
    idxs = sorted({int(i) for i in break_indices if 0 < int(i) < n})
    pinned: dict[int, int] = {}
    for k, idx in enumerate(idxs):
        prev_idx = idxs[k - 1] if k > 0 else 0
        next_idx = idxs[k + 1] if k + 1 < len(idxs) else n
        jump = jump_pct(values, idx, idx - prev_idx, next_idx - idx)
        new = idx
        if jump is not None and abs(jump) >= JUMP_MIN_PCT:
            new = largest_step_near(values, idx, rising=jump > 0)
        pinned[idx] = new if 0 < new < n else idx
    return [pinned.get(int(i), int(i)) for i in break_indices]
