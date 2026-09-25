"""Reusable watchlist check logic shared by the API endpoint
and the notification scheduler.

Each check fetches the latest data for a watched query, runs the same trend
analysis the chart uses, and evaluates the item's alert:

- ``threshold``: the latest value is above/below a number
- ``trend_flip``: the trend direction (rising / falling / stable) differs
  from the one stored at the previous check
- ``slope``: the trend slope (``analysis.trend.momentum_pct_per_month``)
  crossed ``slope_threshold`` % per month since the previous check

Direction and slope are stored on every check so the next one can compare.
The first check only records a baseline for the trend alerts.
"""

import datetime

from app.data.registry import registry
from app.db import repository as repo
from app.logging_config import get_logger
from app.models.schemas import WatchlistCheckResponse, WatchlistItemResponse
from app.services.aggregation import resample_series
from app.services.cache import CachedFetcher

logger = get_logger(__name__)


def format_slope(pct: float) -> str:
    """e.g. "+5%/mo", "-2.5%/mo"."""
    text = f"{pct:+.1f}"
    if text.endswith(".0"):
        text = text[:-2]
    return f"{text}%/mo"


def format_value(v: float) -> str:
    """Compact number for alert messages: 45.0M, 1.2K, 0.35."""
    a = abs(v)
    if a >= 1e9:
        return f"{v / 1e9:.1f}B"
    if a >= 1e6:
        return f"{v / 1e6:.1f}M"
    if a >= 1e4:
        return f"{v / 1e3:.1f}K"
    if a >= 100:
        return f"{v:,.0f}"
    if a >= 1:
        return f"{v:.2f}".rstrip("0").rstrip(".")
    return f"{v:.4g}"


def evaluate_alert(
    item: WatchlistItemResponse,
    latest_value: float,
    direction: str | None,
    slope: float | None,
) -> tuple[bool, str | None]:
    """Whether ``item``'s alert fires for this check, plus a readable message.

    ``item`` carries the state stored at the *previous* check
    (``last_direction``, ``last_slope``); ``direction``/``slope`` are the
    values just computed.
    """
    alert_type = item.alert_type
    if alert_type is None and item.threshold_direction:
        alert_type = "threshold"

    if alert_type == "threshold":
        t = item.threshold_value
        if t is None or item.threshold_direction not in ("above", "below"):
            return False, None
        if item.threshold_direction == "above" and latest_value > t:
            return True, f"{format_value(latest_value)} is above {format_value(t)}"
        if item.threshold_direction == "below" and latest_value < t:
            return True, f"{format_value(latest_value)} is below {format_value(t)}"
        return False, None

    if alert_type == "trend_flip":
        prev = item.last_direction
        if prev and direction and prev != direction:
            return True, f"trend flipped from {prev} to {direction}"
        return False, None

    if alert_type == "slope":
        x = item.slope_threshold
        prev = item.last_slope
        if x is None or prev is None or slope is None:
            return False, None
        if prev < x <= slope:
            return True, (
                f"trend slope rose above {format_slope(x)} (now {format_slope(slope)})"
            )
        if prev >= x > slope:
            return True, (
                f"trend slope fell below {format_slope(x)} (now {format_slope(slope)})"
            )
        return False, None

    return False, None


def trend_of(ts) -> tuple[str | None, float | None]:
    """(direction, slope % / month) from the full chart analysis."""
    from app.analysis.engine import analyze

    try:
        trend = analyze(ts).trend
    except Exception as e:  # too short, degenerate, ...
        logger.info("Watchlist trend analysis skipped: %s", e)
        return None, None
    return trend.direction, trend.momentum_pct_per_month


async def check_watchlist(
    cache: CachedFetcher | None = None,
) -> WatchlistCheckResponse:
    """Fetch latest data for every watchlist item, evaluate its alert,
    and return the full status with any triggered alerts.

    If *cache* is ``None`` a default ``CachedFetcher`` is created.
    """
    if cache is None:
        from app.config import settings

        cache = CachedFetcher(ttl_seconds=settings.cache_ttl)

    items = await repo.list_watchlist()
    now = datetime.datetime.now(datetime.UTC)
    updated_items: list[WatchlistItemResponse] = []
    alerts: list[WatchlistItemResponse] = []

    for item in items:
        try:
            adapter = registry.get(item.source)
            ts = await cache.fetch(adapter, item.query)

            if item.resample:
                ts = resample_series(
                    ts,
                    item.resample,
                    method=adapter.aggregation_method,
                    adapter=adapter,
                )

            if not ts.points:
                updated_items.append(item)
                continue

            latest_value = ts.points[-1].value
            direction, slope = trend_of(ts)
            triggered, message = evaluate_alert(item, latest_value, direction, slope)

            updated = await repo.update_watchlist_item(
                item.id,
                last_value=latest_value,
                last_checked_at=now,
                # Keep the previous baseline if this check couldn't tell
                last_direction=direction or item.last_direction,
                last_slope=slope if slope is not None else item.last_slope,
            )
            if updated is None:
                continue
            updated.triggered = triggered
            updated.alert_message = message
            updated.trend_direction = direction or updated.last_direction
            updated_items.append(updated)
            if triggered:
                alerts.append(updated)

        except Exception as e:
            logger.warning(
                "Failed to check watchlist item %s: %s",
                item.id,
                e,
            )
            updated_items.append(item)

    return WatchlistCheckResponse(
        items=updated_items,
        checked_at=now,
        alerts=alerts,
    )
