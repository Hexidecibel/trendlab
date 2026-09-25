"""In-process pub/sub for real-time progress updates."""

import asyncio
import contextvars
import time
from collections import OrderedDict
from dataclasses import asdict, dataclass

from app.logging_config import get_logger

logger = get_logger(__name__)

# Context variable so any function in the call stack can emit
# progress without passing request_id through every signature.
current_request_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "current_request_id", default=None
)


@dataclass
class ProgressEvent:
    stage: str
    progress: float  # 0.0 – 1.0
    message: str

    def to_dict(self) -> dict:
        return asdict(self)


# Events emitted before anyone subscribes are held briefly so a client that
# fires its HTTP request and then opens the WebSocket (the normal order) still
# sees the early stages. Bounded in ids, events per id, and age.
PENDING_MAX_IDS = 256
PENDING_MAX_EVENTS = 32
PENDING_TTL_SECONDS = 60.0


class ProgressBus:
    """Simple in-process pub/sub keyed by request_id."""

    def __init__(self) -> None:
        self._subscribers: dict[str, asyncio.Queue[ProgressEvent]] = {}
        self._pending: OrderedDict[str, tuple[float, list[ProgressEvent]]] = (
            OrderedDict()
        )

    def _prune_pending(self) -> None:
        cutoff = time.monotonic() - PENDING_TTL_SECONDS
        while self._pending:
            _, (created, _events) = next(iter(self._pending.items()))
            if created >= cutoff and len(self._pending) <= PENDING_MAX_IDS:
                break
            self._pending.popitem(last=False)

    def subscribe(self, request_id: str) -> asyncio.Queue[ProgressEvent]:
        """Create and return a queue for *request_id*.

        Any events already emitted for it (see ``PENDING_*``) are replayed
        into the queue first.
        """
        queue: asyncio.Queue[ProgressEvent] = asyncio.Queue()
        self._prune_pending()
        pending = self._pending.pop(request_id, None)
        if pending is not None:
            for event in pending[1]:
                queue.put_nowait(event)
        self._subscribers[request_id] = queue
        return queue

    def unsubscribe(self, request_id: str) -> None:
        """Remove the queue (and any held events) for *request_id*."""
        self._subscribers.pop(request_id, None)
        self._pending.pop(request_id, None)

    def emit(
        self,
        request_id: str,
        stage: str,
        progress: float,
        message: str,
    ) -> None:
        """Put an event on the subscriber's queue, or hold it until one
        subscribes."""
        event = ProgressEvent(
            stage=stage,
            progress=progress,
            message=message,
        )
        queue = self._subscribers.get(request_id)
        if queue is None:
            entry = self._pending.get(request_id)
            if entry is None:
                entry = (time.monotonic(), [])
                self._pending[request_id] = entry
            if len(entry[1]) < PENDING_MAX_EVENTS:
                entry[1].append(event)
            self._prune_pending()
            return
        try:
            queue.put_nowait(event)
        except asyncio.QueueFull:
            logger.warning("Progress queue full for %s", request_id)


# Module-level singleton
progress_bus = ProgressBus()


def emit_progress(stage: str, progress: float, message: str) -> None:
    """Emit a progress event using the current request_id."""
    request_id = current_request_id.get()
    if request_id is None:
        return
    progress_bus.emit(request_id, stage, progress, message)
