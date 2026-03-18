"""Reusable watchlist check logic shared by the API endpoint
and the notification scheduler."""

import datetime

from app.data.registry import registry
from app.db import repository as repo
from app.logging_config import get_logger
from app.models.schemas import WatchlistCheckResponse, WatchlistItemResponse
from app.services.aggregation import resample_series
from app.services.cache import CachedFetcher

logger = get_logger(__name__)


async def check_watchlist(
    cache: CachedFetcher | None = None,
) -> WatchlistCheckResponse:
    """Fetch latest data for every watchlist item, check thresholds,
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

            if ts.points:
                latest_value = ts.points[-1].value
                trend_direction = None

                # Simple trend from last 5 points
                if len(ts.points) >= 5:
                    recent = [p.value for p in ts.points[-5:]]
                    if recent[-1] > recent[0] * 1.05:
                        trend_direction = "rising"
                    elif recent[-1] < recent[0] * 0.95:
                        trend_direction = "falling"
                    else:
                        trend_direction = "stable"

                updated = await repo.update_watchlist_item(
                    item.id,
                    last_value=latest_value,
                    last_checked_at=now,
                )

                if updated:
                    triggered = False
                    if (
                        item.threshold_direction
                        and item.threshold_value is not None
                    ):
                        if item.threshold_direction == "above":
                            triggered = (
                                latest_value > item.threshold_value
                            )
                        elif item.threshold_direction == "below":
                            triggered = (
                                latest_value < item.threshold_value
                            )

                    updated.triggered = triggered
                    updated.trend_direction = trend_direction
                    updated_items.append(updated)

                    if triggered:
                        alerts.append(updated)
            else:
                updated_items.append(item)

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
