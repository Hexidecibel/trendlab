"""Background scheduler that periodically checks the watchlist
and sends webhook notifications when thresholds are triggered."""

import asyncio
import datetime

from app.db import repository as repo
from app.logging_config import get_logger
from app.notifications.webhook import send_webhook
from app.services.watchlist_checker import check_watchlist

logger = get_logger(__name__)


class NotificationScheduler:
    """Runs a background loop that checks the watchlist on an
    interval and delivers webhook alerts."""

    def __init__(self) -> None:
        self._task: asyncio.Task | None = None
        self._running: bool = False
        self._last_check: datetime.datetime | None = None
        self._next_check: datetime.datetime | None = None

    # -- public API --------------------------------------------------

    def start(self, app=None) -> None:  # noqa: N803
        """Start the background loop."""
        if self._task is not None:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("NotificationScheduler started")

    async def stop(self) -> None:
        """Cancel the background task and wait for it to finish."""
        self._running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("NotificationScheduler stopped")

    @property
    def running(self) -> bool:
        return self._running and self._task is not None

    @property
    def last_check(self) -> datetime.datetime | None:
        return self._last_check

    @property
    def next_check(self) -> datetime.datetime | None:
        return self._next_check

    # -- internals ---------------------------------------------------

    async def _get_config(self):
        """Fetch notification config from DB each iteration."""
        return await repo.get_notification_config()

    async def _get_interval(self) -> int:
        """Return check interval in seconds."""
        from app.config import settings

        return settings.notification_check_interval

    async def _run_loop(self) -> None:
        """Main scheduler loop."""
        while self._running:
            try:
                interval = await self._get_interval()
                self._next_check = datetime.datetime.now(
                    datetime.UTC
                ) + datetime.timedelta(seconds=interval)

                await asyncio.sleep(interval)

                config = await self._get_config()
                if config is None or not config.enabled:
                    continue

                result = await check_watchlist()
                self._last_check = datetime.datetime.now(
                    datetime.UTC
                )

                if result.alerts:
                    await send_webhook(
                        config.webhook_url,
                        config.channel,
                        result.alerts,
                    )

            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning(
                    "Scheduler iteration failed: %s", exc
                )
                # Back off briefly so we don't spin
                await asyncio.sleep(10)


# Module-level singleton used by the app lifespan
notification_scheduler = NotificationScheduler()
