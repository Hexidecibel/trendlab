"""Fetch event context for anomaly dates via DuckDuckGo and Wikipedia."""

import asyncio
from urllib.parse import quote_plus

import httpx

from app.logging_config import get_logger
from app.models.schemas import EventContext

logger = get_logger(__name__)

# In-memory cache: key = "topic|date" -> list[EventContext]
_cache: dict[str, list[EventContext]] = {}

_TIMEOUT = 5.0
_MAX_DATES = 5


async def _fetch_ddg(
    client: httpx.AsyncClient,
    topic: str,
    date: str,
) -> EventContext | None:
    """Query DuckDuckGo Instant Answer API for a topic+date."""
    q = quote_plus(f"{topic} {date}")
    url = (
        f"https://api.duckduckgo.com/"
        f"?q={q}&format=json&no_html=1"
    )
    try:
        resp = await client.get(url, timeout=_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()

        headline = (
            data.get("Heading")
            or data.get("AbstractText")
            or ""
        )
        if not headline:
            # Try related topics
            related = data.get("RelatedTopics", [])
            if related and isinstance(related[0], dict):
                headline = related[0].get("Text", "")

        if not headline:
            return None

        return EventContext(
            date=date,
            headline=headline[:300],
            source_url=data.get("AbstractURL") or None,
            relevance=data.get("AbstractSource") or None,
        )
    except Exception:
        logger.debug("DDG lookup failed for %s %s", topic, date)
        return None


async def _fetch_wikipedia(
    client: httpx.AsyncClient,
    date: str,
) -> EventContext | None:
    """Fallback: Wikipedia 'On this day' for date context."""
    try:
        # Parse month/day from date string (YYYY-MM-DD)
        parts = date.split("-")
        if len(parts) < 3:
            return None
        month, day = parts[1], parts[2]
        url = (
            f"https://api.wikimedia.org/feed/v1/"
            f"wikipedia/en/onthisday/events/"
            f"{month}/{day}"
        )
        resp = await client.get(url, timeout=_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()

        events = data.get("events", [])
        if not events:
            return None

        event = events[0]
        text = event.get("text", "")
        pages = event.get("pages", [])
        page_url = None
        if pages:
            desktop = pages[0].get("content_urls", {})
            page_url = desktop.get("desktop", {}).get(
                "page", None
            )

        return EventContext(
            date=date,
            headline=text[:300],
            source_url=page_url,
            relevance="Wikipedia: On this day",
        )
    except Exception:
        logger.debug("Wikipedia fallback failed for %s", date)
        return None


async def fetch_event_context(
    topic: str,
    dates: list[str],
) -> list[EventContext]:
    """Fetch event context for anomaly dates.

    Best-effort: returns empty list on any failure.
    Limits to MAX_DATES to avoid excessive requests.
    Results are cached in-memory by topic+date.
    """
    if not dates:
        return []

    limited = dates[:_MAX_DATES]
    results: list[EventContext] = []
    to_fetch: list[str] = []

    # Check cache first
    for d in limited:
        key = f"{topic}|{d}"
        if key in _cache:
            results.extend(_cache[key])
        else:
            to_fetch.append(d)

    if not to_fetch:
        return results

    try:
        async with httpx.AsyncClient() as client:
            tasks = []
            for d in to_fetch:
                tasks.append(_fetch_single(client, topic, d))
            fetched = await asyncio.gather(
                *tasks, return_exceptions=True
            )

            for d, result in zip(to_fetch, fetched):
                key = f"{topic}|{d}"
                if isinstance(result, EventContext):
                    _cache[key] = [result]
                    results.append(result)
                else:
                    _cache[key] = []
    except Exception:
        logger.debug(
            "Event context fetch failed for %s", topic
        )

    return results


async def _fetch_single(
    client: httpx.AsyncClient,
    topic: str,
    date: str,
) -> EventContext | None:
    """Try DDG first, fall back to Wikipedia."""
    result = await _fetch_ddg(client, topic, date)
    if result:
        return result
    return await _fetch_wikipedia(client, date)
