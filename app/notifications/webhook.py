"""Webhook sender for notification alerts."""

import datetime

import httpx

from app.logging_config import get_logger
from app.models.schemas import WatchlistItemResponse

logger = get_logger(__name__)


def _format_alert_line(alert: WatchlistItemResponse) -> str:
    """Format a single alert into a human-readable line."""
    direction = alert.threshold_direction or "threshold"
    value = alert.last_value if alert.last_value is not None else "?"
    threshold = alert.threshold_value if alert.threshold_value is not None else "?"
    return (
        f"- {alert.name} ({alert.source}/{alert.query}): "
        f"{value} is {direction} {threshold}"
    )


def _build_payload(
    channel: str,
    alerts: list[WatchlistItemResponse],
) -> dict:
    """Build channel-aware webhook payload."""
    lines = [_format_alert_line(a) for a in alerts]
    count = len(alerts)
    text = (
        f"\U0001f514 TrendLab Alert: {count} "
        f"threshold{'s' if count != 1 else ''} triggered\n"
        + "\n".join(lines)
    )

    if channel == "slack":
        return {"text": text}
    elif channel == "discord":
        return {"content": text}
    else:
        return {
            "alerts": [
                {
                    "name": a.name,
                    "source": a.source,
                    "query": a.query,
                    "last_value": a.last_value,
                    "threshold_direction": a.threshold_direction,
                    "threshold_value": a.threshold_value,
                    "trend_direction": a.trend_direction,
                }
                for a in alerts
            ],
            "timestamp": datetime.datetime.now(
                datetime.UTC
            ).isoformat(),
        }


async def send_webhook(
    url: str,
    channel: str,
    alerts: list[WatchlistItemResponse],
) -> bool:
    """POST alerts to the webhook URL.

    Returns True on success, False on failure. Errors are
    logged but never raised.
    """
    payload = _build_payload(channel, alerts)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            logger.info(
                "Webhook sent successfully (%d alerts)", len(alerts)
            )
            return True
    except Exception as exc:
        logger.warning("Webhook delivery failed: %s", exc)
        return False
