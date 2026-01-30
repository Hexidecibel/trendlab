import datetime
from abc import ABC, abstractmethod

from app.models.schemas import TimeSeries


class DataAdapter(ABC):
    name: str
    description: str

    @abstractmethod
    async def fetch(
        self,
        query: str,
        start: datetime.date | None = None,
        end: datetime.date | None = None,
    ) -> TimeSeries: ...
