"""In-process pub/sub for real-time progress updates."""

import asyncio
import contextvars
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


class ProgressBus:
    """Simple in-process pub/sub keyed by request_id."""

    def __init__(self) -> None:
        self._subscribers: dict[str, asyncio.Queue[ProgressEvent]] = {}

    def subscribe(self, request_id: str) -> asyncio.Queue[ProgressEvent]:
        """Create and return a queue for *request_id*."""
        queue: asyncio.Queue[ProgressEvent] = asyncio.Queue()
        self._subscribers[request_id] = queue
        return queue

    def unsubscribe(self, request_id: str) -> None:
        """Remove the queue for *request_id*."""
        self._subscribers.pop(request_id, None)

    def emit(
        self,
        request_id: str,
        stage: str,
        progress: float,
        message: str,
    ) -> None:
        """Put an event on the queue if a subscriber exists."""
        queue = self._subscribers.get(request_id)
        if queue is None:
            return
        event = ProgressEvent(
            stage=stage,
            progress=progress,
            message=message,
        )
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
